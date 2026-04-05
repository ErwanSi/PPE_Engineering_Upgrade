"""
Wallet Manager — Cross-exchange fund transfers and balance monitoring.
"""
import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WalletManager:
    """
    Manages fund transfers between exchanges for rebalancing.
    Tracks balances and provides transfer recommendations.
    """

    def __init__(self):
        self.transfer_history: List[Dict] = []
        self.balance_snapshots: List[Dict] = []

    async def get_balances(self, executor) -> Dict[str, Dict]:
        """Get current balances across all connected exchanges."""
        balances = await executor.get_all_balances()

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balances": balances,
            "total_usd": sum(b.get("total_usd", 0) for b in balances.values())
        }
        self.balance_snapshots.append(snapshot)

        return snapshot

    def compute_rebalance_transfers(self, balances: Dict[str, Dict],
                                     target_allocation: Dict[str, float] = None) -> List[Dict]:
        """
        Compute required transfers to rebalance funds across exchanges.
        target_allocation: {"binance": 0.5, "extended": 0.5} (proportions)
        """
        if not target_allocation:
            # Default: equal allocation
            n = len(balances)
            if n == 0:
                return []
            target_allocation = {k: 1.0 / n for k in balances.keys()}

        total = sum(b.get("total_usd", 0) for b in balances.values())
        if total == 0:
            return []

        transfers = []
        current = {k: b.get("total_usd", 0) for k, b in balances.items()}
        targets = {k: total * v for k, v in target_allocation.items()}

        # Compute deltas
        deltas = {k: targets.get(k, 0) - current.get(k, 0) for k in set(list(targets.keys()) + list(current.keys()))}

        # Match senders (negative delta) with receivers (positive delta)
        senders = [(k, -v) for k, v in deltas.items() if v < 0]
        receivers = [(k, v) for k, v in deltas.items() if v > 0]

        senders.sort(key=lambda x: x[1], reverse=True)
        receivers.sort(key=lambda x: x[1], reverse=True)

        si, ri = 0, 0
        while si < len(senders) and ri < len(receivers):
            s_name, s_amount = senders[si]
            r_name, r_amount = receivers[ri]

            transfer_amount = min(s_amount, r_amount)

            if transfer_amount > 1.0:  # Min $1 transfer
                transfers.append({
                    "from": s_name,
                    "to": r_name,
                    "amount_usd": round(transfer_amount, 2),
                    "status": "pending"
                })

            senders[si] = (s_name, s_amount - transfer_amount)
            receivers[ri] = (r_name, r_amount - transfer_amount)

            if senders[si][1] < 1.0:
                si += 1
            if receivers[ri][1] < 1.0:
                ri += 1

        return transfers

    async def execute_transfer(self, from_exchange: str, to_exchange: str,
                                amount_usd: float, executor) -> Dict[str, Any]:
        """
        Execute a fund transfer between exchanges.
        NOTE: This typically requires withdrawal from one exchange and deposit to another.
        This is a MANUAL process for most exchanges — we log the recommendation.
        """
        transfer = {
            "from": from_exchange,
            "to": to_exchange,
            "amount_usd": round(amount_usd, 2),
            "status": "recommended",  # Most exchanges require manual withdrawal
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instructions": (
                f"1. Withdraw ${amount_usd:.2f} USDT from {from_exchange}\n"
                f"2. Deposit to {to_exchange} wallet\n"
                f"3. Confirm receipt and update bot"
            )
        }

        self.transfer_history.append(transfer)
        logger.info(f"Transfer recommendation: ${amount_usd:.2f} from {from_exchange} to {to_exchange}")

        return transfer

    def get_transfer_history(self, limit: int = 50) -> List[Dict]:
        return self.transfer_history[-limit:]

    def get_balance_history(self, limit: int = 100) -> List[Dict]:
        return self.balance_snapshots[-limit:]
