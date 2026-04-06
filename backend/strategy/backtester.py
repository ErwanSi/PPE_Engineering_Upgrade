"""
Phase 5 — Event-Driven Backtester
Hour-by-hour simulation applying risk rules, costs, and signals.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from strategy.signal_generator import SignalGenerator
from strategy.cost_model import CostModel


@dataclass
class BacktestTrade:
    entry_time: str
    exit_time: str
    token: str
    long_exchange: str
    short_exchange: str
    direction: str  # "long_spread" or "short_spread"
    entry_zscore: float
    exit_zscore: float
    funding_pnl_pct: float
    cost_pct: float
    net_pnl_pct: float
    duration_hours: int


class EventDrivenBacktester:
    """
    Backtester that simulates hour-by-hour execution:
    1. Compute Z-Score → detect signal
    2. Evaluate profitability BEFORE opening
    3. Collect funding and track liquidation risk
    4. Close on Z-Score return to equilibrium
    """

    def __init__(self, config=None):
        if config is None:
            from main import StrategyConfig
            config = StrategyConfig()

        self.signal_gen = SignalGenerator(
            lookback_hours=config.lookback_hours,
            entry_threshold=config.zscore_entry,
            exit_threshold=config.zscore_exit
        )
        self.cost_model = CostModel()
        self.max_leverage = config.max_leverage
        self.taker_fee_bps = config.taker_fee_bps
        self.slippage_bps = config.slippage_bps
        self.gas_fee_usd = config.gas_fee_usd
        self.max_position_usd = config.max_position_usd

    def run(self, p_long: pd.Series, p_short: pd.Series,
            f_long: pd.Series, f_short: pd.Series,
            long_exchange: str = "exchange_a",
            short_exchange: str = "exchange_b") -> Dict[str, Any]:
        """
        Run the full event-driven backtest.
        """
        # Infer exchange names from series names if available
        if hasattr(p_long, 'name') and p_long.name:
            long_exchange = str(p_long.name) if isinstance(p_long.name, str) else long_exchange
        if hasattr(p_short, 'name') and p_short.name:
            short_exchange = str(p_short.name) if isinstance(p_short.name, str) else short_exchange

        # Generate signals
        signals = self.signal_gen.generate_signals(f_long, f_short)
        if signals is None or signals.empty:
            return {"error": "Insufficient data for Z-Score computation"}

        # Prepare funding spread (hourly)
        funding_spread = self.signal_gen.compute_funding_spread(f_long, f_short)
        if funding_spread is None:
            return {"error": "Cannot compute funding spread"}

        # Align all data on common hourly index
        zscore = signals["zscore"]

        # Run simulation
        trades: List[BacktestTrade] = []
        equity_curve = []
        cumulative_pnl = 0.0
        position_open = False
        entry_time = None
        entry_zscore = 0.0
        direction = ""
        position_funding = 0.0

        # Passive (Hold) logic: open at first hour, hold till end.
        mean_spread = float(funding_spread.mean())
        passive_direction = 1 if mean_spread > 0 else -1
        passive_cumulative_pnl = 0.0
        # Roundtrip cost for passive (once)
        passive_cost_pct = self.cost_model.roundtrip_cost_bps(long_exchange, short_exchange, slippage_bps=self.slippage_bps) / 100

        # Hourly iteration
        for ts in zscore.index:
            z = float(zscore.loc[ts])
            signal = self.signal_gen.get_signal(z)
            current_spread = float(funding_spread.loc[ts])
            sma_3h = float(signals.loc[ts, "sma_3h"]) if "sma_3h" in signals.columns else current_spread

            # --- Passive PnL Update ---
            if ts in funding_spread.index:
                hourly_p = current_spread * passive_direction
                passive_cumulative_pnl += (hourly_p * 100) # to pct

            # === ENTRY LOGIC ===
            if not position_open and signal in ["LONG", "SHORT"]:
                # Trend Filter: Only enter if spread confirms the direction relative to 3h SMA
                trend_confirmed = False
                if signal == "LONG" and current_spread <= sma_3h:
                    trend_confirmed = True
                elif signal == "SHORT" and current_spread >= sma_3h:
                    trend_confirmed = True

                if trend_confirmed:
                    # phase 2: Check profitability before opening
                    recent_spread = funding_spread.loc[:ts].tail(24)
                    if len(recent_spread) > 0:
                        expected_hourly_yield_bps = float(recent_spread.mean()) * 10000  # decimal to bps
                        
                        if signal == "SHORT":  # For SHORT signal, we expect profit from -spread
                            expected_hourly_yield_bps = -expected_hourly_yield_bps
                            
                        expected_total_yield = expected_hourly_yield_bps * 168  # ~7 days hold estimate instead of 2 days

                        rt_cost = self.cost_model.roundtrip_cost_bps(long_exchange, short_exchange,
                                                                       slippage_bps=self.slippage_bps)

                        # removed strict profitability gate so backtest actually demonstrates the fee burn
                        position_open = True
                        entry_time = ts
                        entry_zscore = z
                        direction = signal
                        position_funding = 0.0

            # === FUNDING COLLECTION ===
            elif position_open:
                if ts in funding_spread.index:
                    hourly_funding = float(funding_spread.loc[ts])
                    if direction == "SHORT": # If short the spread, we earn -spread
                        hourly_funding = -hourly_funding
                    position_funding += hourly_funding

                # === EXIT LOGIC (Trend-Following Arbitrage) ===
                # We stay as long as funding is positive for us OR Z-score is still in our favor.
                # We only exit if funding flips AND Z-score has returned from its extreme.
                should_exit = False
                if direction == "LONG":
                    # We are Long the spread. We exit if funding becomes negative AND spread is back to normal
                    if hourly_funding < 0 and z > 0.0:
                        should_exit = True
                elif direction == "SHORT":
                    # We are Short the spread. We exit if funding becomes negative AND spread is back to normal
                    if hourly_funding < 0 and z < 0.0:
                        should_exit = True

                if should_exit:
                    # Close position
                    cost_bps = self.cost_model.roundtrip_cost_bps(long_exchange, short_exchange,
                                                                    slippage_bps=self.slippage_bps)
                    cost_pct = cost_bps / 100
                    funding_pnl = position_funding * 100  # to pct
                    net_pnl = funding_pnl - cost_pct
                    duration = int((ts - entry_time).total_seconds() / 3600) if entry_time else 0

                    trade = BacktestTrade(
                        entry_time=str(entry_time),
                        exit_time=str(ts),
                        token="",
                        long_exchange=long_exchange,
                        short_exchange=short_exchange,
                        direction=direction,
                        entry_zscore=round(entry_zscore, 4),
                        exit_zscore=round(z, 4),
                        funding_pnl_pct=round(funding_pnl, 4),
                        cost_pct=round(cost_pct, 4),
                        net_pnl_pct=round(net_pnl, 4),
                        duration_hours=duration
                    )
                    trades.append(trade)
                    cumulative_pnl += net_pnl
                    position_open = False

            # Current unrealized PnL for the strategy
            strategy_visual_pnl = cumulative_pnl
            if position_open:
                strategy_visual_pnl += (position_funding * 100)

            equity_curve.append({
                "time": str(ts),
                "cumulative_pnl": round(strategy_visual_pnl, 4),
                "passive_pnl": round(passive_cumulative_pnl - passive_cost_pct, 4),
                "zscore": round(z, 4),
                "in_position": position_open
            })

        # === METRICS ===
        if not trades:
            return {
                "trades": [],
                "metrics": {"total_trades": 0, "message": "No trades triggered"},
                "equity_curve": equity_curve[-200:] if len(equity_curve) > 200 else equity_curve
            }

        net_pnls = [t.net_pnl_pct for t in trades]
        winning = [p for p in net_pnls if p > 0]
        losing = [p for p in net_pnls if p <= 0]

        total_duration = sum(t.duration_hours for t in trades)
        avg_duration = total_duration / len(trades) if trades else 0

        # Sharpe Ratio (annualized, assuming hourly data)
        pnl_array = np.array(net_pnls)
        sharpe = (pnl_array.mean() / pnl_array.std() * np.sqrt(365 * 24)) if pnl_array.std() > 0 else 0

        # Max Drawdown
        cum = np.cumsum(pnl_array)
        peak = np.maximum.accumulate(cum)
        drawdowns = cum - peak
        max_dd = float(drawdowns.min()) if len(drawdowns) > 0 else 0

        metrics = {
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(len(winning) / len(trades) * 100, 1),
            "total_pnl_pct": round(cumulative_pnl, 4),
            "avg_pnl_per_trade_pct": round(float(pnl_array.mean()), 4),
            "best_trade_pct": round(float(max(net_pnls)), 4),
            "worst_trade_pct": round(float(min(net_pnls)), 4),
            "avg_duration_hours": round(avg_duration, 1),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 4),
            "profit_factor": (
                round(sum(winning) / abs(sum(losing)), 2)
                if losing and sum(losing) != 0 else float('inf')
            )
        }

        return {
            "trades": [vars(t) for t in trades],
            "metrics": metrics,
            "equity_curve": equity_curve[-5000:] if len(equity_curve) > 5000 else equity_curve
        }
