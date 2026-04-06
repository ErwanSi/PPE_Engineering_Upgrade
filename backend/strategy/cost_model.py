"""
Phase 2 — Cost Model
Models real-world transaction costs: Maker/Taker fees, Bid-Ask spread, Slippage, Gas.
Condition: E[Funding Yield] > Transaction Costs + Gas Fees
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ExchangeFees:
    """Fee structure per exchange (in basis points unless noted)."""
    maker_bps: float
    taker_bps: float
    funding_interval_hours: float  # 8h for Binance, 1h for Hyperliquid, etc.
    has_gas: bool = False
    gas_estimate_usd: float = 0.0


# Default fee structures (mid-tier user, no discounts)
EXCHANGE_FEES = {
    "binance": ExchangeFees(maker_bps=2.0, taker_bps=5.0, funding_interval_hours=8.0),
    "hyperliquid": ExchangeFees(maker_bps=1.0, taker_bps=3.5, funding_interval_hours=1.0),
    "extended": ExchangeFees(maker_bps=1.0, taker_bps=3.5, funding_interval_hours=1.0,
                              has_gas=True, gas_estimate_usd=0.2),
    "paradex": ExchangeFees(maker_bps=0.0, taker_bps=2.0, funding_interval_hours=1.0,
                             has_gas=True, gas_estimate_usd=0.2),
}


class CostModel:
    """
    Computes the total round-trip cost of opening and closing an arbitrage position.
    """

    def __init__(self, custom_fees: Dict[str, ExchangeFees] = None):
        self.fees = custom_fees or EXCHANGE_FEES

    def get_fees(self, exchange: str) -> ExchangeFees:
        return self.fees.get(exchange, ExchangeFees(maker_bps=5.0, taker_bps=10.0, funding_interval_hours=8.0))

    def entry_cost_bps(self, long_exchange: str, short_exchange: str,
                        use_maker: bool = False, slippage_bps: float = 3.0) -> float:
        """
        Total cost to OPEN the position (one-way).
        Cost = Fee_long + Fee_short + Slippage_long + Slippage_short
        """
        long_fees = self.get_fees(long_exchange)
        short_fees = self.get_fees(short_exchange)

        fee_type = "maker_bps" if use_maker else "taker_bps"
        long_fee = getattr(long_fees, fee_type)
        short_fee = getattr(short_fees, fee_type)

        return long_fee + short_fee + 2 * slippage_bps

    def roundtrip_cost_bps(self, long_exchange: str, short_exchange: str,
                            use_maker: bool = False, slippage_bps: float = 3.0) -> float:
        """
        Total cost to OPEN + CLOSE the position (round-trip).
        """
        return 2 * self.entry_cost_bps(long_exchange, short_exchange, use_maker, slippage_bps)

    def gas_cost_usd(self, long_exchange: str, short_exchange: str) -> float:
        """Total gas cost for the round-trip."""
        long_gas = self.get_fees(long_exchange).gas_estimate_usd if self.get_fees(long_exchange).has_gas else 0
        short_gas = self.get_fees(short_exchange).gas_estimate_usd if self.get_fees(short_exchange).has_gas else 0
        return 2 * (long_gas + short_gas)  # Open + Close

    def is_profitable(self, expected_funding_yield_bps: float, long_exchange: str,
                       short_exchange: str, position_size_usd: float,
                       use_maker: bool = False, slippage_bps: float = 3.0) -> Dict[str, Any]:
        """
        Phase 2 condition: E[Funding Yield] > Transaction Costs + Gas Fees
        Returns detailed breakdown.
        """
        rt_cost_bps = self.roundtrip_cost_bps(long_exchange, short_exchange, use_maker, slippage_bps)
        gas_usd = self.gas_cost_usd(long_exchange, short_exchange)
        gas_bps = (gas_usd / position_size_usd) * 10000 if position_size_usd > 0 else 0

        total_cost_bps = rt_cost_bps + gas_bps
        net_yield_bps = expected_funding_yield_bps - total_cost_bps
        is_profitable = net_yield_bps > 0

        return {
            "expected_yield_bps": round(expected_funding_yield_bps, 2),
            "roundtrip_fees_bps": round(rt_cost_bps, 2),
            "gas_cost_usd": round(gas_usd, 2),
            "gas_cost_bps": round(gas_bps, 2),
            "total_cost_bps": round(total_cost_bps, 2),
            "net_yield_bps": round(net_yield_bps, 2),
            "is_profitable": is_profitable,
            "breakeven_hours": (
                round(total_cost_bps / expected_funding_yield_bps, 1)
                if expected_funding_yield_bps > 0 else float('inf')
            ),
            "interpretation": (
                f"✅ Profitable — Net yield: {net_yield_bps:.1f} bps"
                if is_profitable
                else f"🔴 Not profitable — Cost ({total_cost_bps:.1f} bps) > Yield ({expected_funding_yield_bps:.1f} bps)"
            )
        }

    def summary(self, long_exchange: str, short_exchange: str) -> Dict[str, Any]:
        """Get fee summary for a pair of exchanges."""
        return {
            "long_exchange": {
                "name": long_exchange,
                "maker_bps": self.get_fees(long_exchange).maker_bps,
                "taker_bps": self.get_fees(long_exchange).taker_bps,
                "has_gas": self.get_fees(long_exchange).has_gas,
                "gas_usd": self.get_fees(long_exchange).gas_estimate_usd,
            },
            "short_exchange": {
                "name": short_exchange,
                "maker_bps": self.get_fees(short_exchange).maker_bps,
                "taker_bps": self.get_fees(short_exchange).taker_bps,
                "has_gas": self.get_fees(short_exchange).has_gas,
                "gas_usd": self.get_fees(short_exchange).gas_estimate_usd,
            },
            "entry_cost_taker_bps": round(self.entry_cost_bps(long_exchange, short_exchange), 2),
            "roundtrip_cost_taker_bps": round(self.roundtrip_cost_bps(long_exchange, short_exchange), 2),
            "total_gas_usd": round(self.gas_cost_usd(long_exchange, short_exchange), 2),
        }
