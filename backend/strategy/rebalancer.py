"""
Phase 4 — Rebalancing Manager
Margin rebalancing (collateral) and Delta rebalancing (neutrality).
"""
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class Position:
    """Represents one side of the arbitrage position."""
    exchange: str
    token: str
    side: str  # "long" or "short"
    size_usd: float
    entry_price: float
    current_price: float = 0.0
    margin: float = 0.0
    leverage: float = 1.0
    unrealized_pnl: float = 0.0
    funding_collected: float = 0.0


@dataclass
class ArbitragePosition:
    """A full arbitrage position (long + short legs)."""
    token: str
    long_pos: Position
    short_pos: Position
    opened_at: str = ""
    total_funding_pnl: float = 0.0
    status: str = "open"  # open, closing, closed


class Rebalancer:
    """
    Handles two types of rebalancing:
    1. Margin Rebalancing — Adjust collateral to maintain healthy leverage
    2. Delta Rebalancing — Maintain market neutrality (Δ ≈ 0)
    """

    def __init__(self, max_leverage: float = 3.0,
                 margin_warning_pct: float = 0.15,
                 delta_tolerance: float = 0.02):
        self.max_leverage = max_leverage
        self.margin_warning_pct = margin_warning_pct
        self.delta_tolerance = delta_tolerance

    # ============================
    # MARGIN REBALANCING
    # ============================
    def check_margin_health(self, position: Position) -> Dict[str, Any]:
        """
        Check if a position's margin is healthy.
        margin_ratio = margin / (size * price)
        If margin_ratio drops below warning threshold: REBALANCE needed.
        """
        if position.current_price <= 0 or position.size_usd <= 0:
            return {"healthy": True, "needs_rebalance": False}

        notional = position.size_usd
        margin_ratio = position.margin / notional if notional > 0 else 1.0
        effective_leverage = notional / position.margin if position.margin > 0 else float('inf')

        # Maintenance margin threshold (simplified)
        maintenance_margin_ratio = 1.0 / self.max_leverage * 0.5  # 50% of initial margin

        needs_rebalance = margin_ratio < self.margin_warning_pct
        near_liquidation = margin_ratio < maintenance_margin_ratio

        return {
            "exchange": position.exchange,
            "side": position.side,
            "margin_ratio": round(margin_ratio, 4),
            "effective_leverage": round(effective_leverage, 2),
            "max_leverage": self.max_leverage,
            "needs_rebalance": needs_rebalance,
            "near_liquidation": near_liquidation,
            "recommended_action": (
                "URGENT: Add margin immediately" if near_liquidation
                else "Margin low -- Consider adding collateral" if needs_rebalance
                else "Healthy"
            )
        }

    def compute_margin_adjustment(self, position: Position) -> float:
        """
        Compute how much margin to ADD to bring leverage back to target.
        target_margin = notional / max_leverage
        adjustment = target_margin - current_margin
        """
        target_margin = position.size_usd / self.max_leverage
        adjustment = target_margin - position.margin
        return max(0, adjustment)

    # ============================
    # DELTA REBALANCING
    # ============================
    def compute_delta(self, arb: ArbitragePosition) -> Dict[str, Any]:
        """
        Compute portfolio delta (net directional exposure).
        Δ = (long_value - short_value) / total_value
        Perfect neutrality: Δ = 0
        """
        long_value = arb.long_pos.size_usd
        short_value = arb.short_pos.size_usd
        total_value = long_value + short_value

        if total_value == 0:
            return {"delta": 0, "needs_rebalance": False}

        delta = (long_value - short_value) / total_value
        needs_rebalance = abs(delta) > self.delta_tolerance

        if needs_rebalance:
            if delta > 0:
                # Too long — need to reduce long or increase short
                adjustment_usd = delta * total_value / 2
                action = f"Reduce LONG by ${adjustment_usd:.2f} or Increase SHORT by ${adjustment_usd:.2f}"
            else:
                adjustment_usd = abs(delta) * total_value / 2
                action = f"Reduce SHORT by ${adjustment_usd:.2f} or Increase LONG by ${adjustment_usd:.2f}"
        else:
            action = "Delta neutral"
            adjustment_usd = 0

        return {
            "delta": round(delta, 6),
            "delta_pct": round(delta * 100, 4),
            "tolerance": self.delta_tolerance,
            "needs_rebalance": needs_rebalance,
            "adjustment_usd": round(adjustment_usd, 2),
            "recommended_action": action,
            "long_value": round(long_value, 2),
            "short_value": round(short_value, 2),
        }

    def full_check(self, arb: ArbitragePosition) -> Dict[str, Any]:
        """Run complete rebalancing check on an arbitrage position."""
        margin_long = self.check_margin_health(arb.long_pos)
        margin_short = self.check_margin_health(arb.short_pos)
        delta = self.compute_delta(arb)

        actions_needed = []
        if margin_long["needs_rebalance"]:
            amount = self.compute_margin_adjustment(arb.long_pos)
            actions_needed.append({
                "type": "margin",
                "exchange": arb.long_pos.exchange,
                "side": "long",
                "add_margin_usd": round(amount, 2)
            })
        if margin_short["needs_rebalance"]:
            amount = self.compute_margin_adjustment(arb.short_pos)
            actions_needed.append({
                "type": "margin",
                "exchange": arb.short_pos.exchange,
                "side": "short",
                "add_margin_usd": round(amount, 2)
            })
        if delta["needs_rebalance"]:
            actions_needed.append({
                "type": "delta",
                "adjustment_usd": delta["adjustment_usd"],
                "current_delta": delta["delta"]
            })

        return {
            "token": arb.token,
            "margin_long": margin_long,
            "margin_short": margin_short,
            "delta": delta,
            "actions_needed": actions_needed,
            "is_healthy": len(actions_needed) == 0
        }
