"""
Bot Supervisor — Main loop that orchestrates signals, execution, and monitoring.
Supports modes: manual (signals only), paper (simulated), live (real execution).
"""
import asyncio
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from bot.executor import Executor
from bot.wallet_manager import WalletManager
from strategy.signal_generator import SignalGenerator
from strategy.rebalancer import Rebalancer
from strategy.cost_model import CostModel

logger = logging.getLogger(__name__)


class BotSupervisor:
    """
    The main bot controller. Runs a continuous loop:
    1. Check signals for configured pairs
    2. Evaluate profitability
    3. Execute trades (if auto mode)
    4. Monitor positions and rebalance
    5. Close on exit signals
    """

    def __init__(self):
        self.is_running = False
        self.mode = os.getenv("BOT_MODE", "manual")  # manual, paper, live
        self.executor = Executor()
        self.wallet_manager = WalletManager()
        self.cost_model = CostModel()
        self.rebalancer = Rebalancer()

        # State
        self.config = None
        self.tracked_pairs: List[Dict] = []
        self.open_positions: List[Dict] = []
        self.activity_log: List[Dict] = []
        self.signals_history: List[Dict] = []
        self._task: Optional[asyncio.Task] = None

    def log(self, level: str, message: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message
        }
        self.activity_log.append(entry)
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-500:]

        getattr(logger, level.lower(), logger.info)(message)

    async def start(self, config=None, pairs: List[Dict] = None):
        """Start the bot loop."""
        if self.is_running:
            return

        self.config = config
        if pairs:
            self.tracked_pairs = pairs

        self.is_running = True
        self.log("info", f"Bot started in {self.mode} mode. Tracking {len(self.tracked_pairs)} pairs.")

        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the bot loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.log("info", "Bot stopped.")

    async def _run_loop(self):
        """Main bot loop."""
        interval = int(os.getenv("BOT_CHECK_INTERVAL_SECONDS", 60))

        while self.is_running:
            try:
                await self._check_cycle()
            except Exception as e:
                self.log("error", f"Cycle error: {e}")

            await asyncio.sleep(interval)

    async def _check_cycle(self):
        """One full check cycle."""
        for pair in self.tracked_pairs:
            token = pair.get("token", "")
            long_ex = pair.get("long", "")
            short_ex = pair.get("short", "")

            if not token or not long_ex or not short_ex:
                continue

            try:
                # 1. Generate signal
                signal_state = self._compute_signal(pair)
                if not signal_state:
                    continue

                self.signals_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "token": token,
                    "pair": f"{long_ex}/{short_ex}",
                    **signal_state
                })

                signal = signal_state.get("signal", "HOLD")

                # 2. Check if we have an open position for this pair
                existing = self._find_position(token, long_ex, short_ex)

                if existing and signal == "EXIT":
                    await self._handle_exit(token, long_ex, short_ex)

                elif not existing and signal in ["LONG", "SHORT"]:
                    # Check profitability
                    profitability = self.cost_model.is_profitable(
                        expected_funding_yield_bps=abs(signal_state.get("funding_spread", 0)) * 100 * 48,
                        long_exchange=long_ex,
                        short_exchange=short_ex,
                        position_size_usd=10000
                    )

                    if profitability["is_profitable"]:
                        await self._handle_entry(token, long_ex, short_ex, signal)
                    else:
                        self.log("info", f"Signal {signal} for {token} but not profitable: {profitability['interpretation']}")

                # 3. Check rebalancing for open positions
                if existing:
                    await self._check_rebalance(existing)

            except Exception as e:
                self.log("error", f"Error checking {token}: {e}")

        # Trim signals history
        if len(self.signals_history) > 5000:
            self.signals_history = self.signals_history[-2500:]

    def _compute_signal(self, pair: Dict) -> Optional[Dict]:
        """Compute signal for a pair. Returns None if insufficient data."""
        # In production, this would query live data from data_service
        # For now, return a placeholder that the frontend can override
        return {
            "signal": "HOLD",
            "zscore": 0.0,
            "funding_spread": 0.0,
        }

    def _find_position(self, token: str, long_ex: str, short_ex: str) -> Optional[Dict]:
        for pos in self.open_positions:
            if (pos["token"] == token and
                pos["long_exchange"] == long_ex and
                pos["short_exchange"] == short_ex):
                return pos
        return None

    async def _handle_entry(self, token: str, long_ex: str, short_ex: str, signal: str):
        """Handle a new entry signal."""
        size_usd = float(os.getenv("MAX_POSITION_SIZE_USD", 10000))

        if self.mode == "manual":
            self.log("info", f"📡 SIGNAL: {signal} {token} on {long_ex}/{short_ex} — Size: ${size_usd}")
            self.open_positions.append({
                "token": token,
                "long_exchange": long_ex,
                "short_exchange": short_ex,
                "signal": signal,
                "size_usd": size_usd,
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "status": "signal_only",
                "funding_collected": 0.0
            })

        elif self.mode == "paper":
            self.log("info", f"📝 PAPER TRADE: {signal} {token} on {long_ex}/{short_ex}")
            self.open_positions.append({
                "token": token,
                "long_exchange": long_ex,
                "short_exchange": short_ex,
                "signal": signal,
                "size_usd": size_usd,
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "status": "paper",
                "funding_collected": 0.0
            })

        elif self.mode == "live":
            self.log("info", f"🚀 LIVE TRADE: {signal} {token} on {long_ex}/{short_ex}")
            result = await self.executor.open_arbitrage(token, long_ex, short_ex, size_usd)
            self.open_positions.append({
                "token": token,
                "long_exchange": long_ex,
                "short_exchange": short_ex,
                "signal": signal,
                "size_usd": size_usd,
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "status": "live",
                "execution": result,
                "funding_collected": 0.0
            })

    async def _handle_exit(self, token: str, long_ex: str, short_ex: str):
        """Handle an exit signal."""
        pos = self._find_position(token, long_ex, short_ex)
        if not pos:
            return

        if self.mode == "live" and pos["status"] == "live":
            result = await self.executor.close_arbitrage(token, long_ex, short_ex)
            self.log("info", f"🔒 CLOSED {token}: {result}")

        self.log("info", f"EXIT {token} on {long_ex}/{short_ex} — Funding PnL: {pos.get('funding_collected', 0):.4f}")
        self.open_positions.remove(pos)

    async def _check_rebalance(self, position: Dict):
        """Check if position needs rebalancing."""
        # Simplified check — in production, query real margin data
        pass

    # ============================
    # STATUS / QUERY METHODS
    # ============================
    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "mode": self.mode,
            "tracked_pairs": len(self.tracked_pairs),
            "open_positions": len(self.open_positions),
            "total_signals": len(self.signals_history),
            "last_check": (
                self.signals_history[-1]["timestamp"]
                if self.signals_history else None
            ),
            "positions": self.open_positions,
            "recent_signals": self.signals_history[-10:]
        }

    def get_positions(self) -> List[Dict]:
        return self.open_positions

    def get_logs(self, limit: int = 100) -> List[Dict]:
        return self.activity_log[-limit:]
