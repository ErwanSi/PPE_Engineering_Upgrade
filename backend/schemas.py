from pydantic import BaseModel
from typing import Optional, List, Dict

class StrategyConfig(BaseModel):
    zscore_entry: float = 2.0
    zscore_exit: float = 0.5
    lookback_hours: int = 168
    max_leverage: float = 3.0
    max_position_usd: float = 10000.0
    delta_tolerance: float = 0.02
    rebalance_margin_pct: float = 0.15
    maker_fee_bps: float = 2.0
    taker_fee_bps: float = 5.0
    gas_fee_usd: float = 0.5
    slippage_bps: float = 1.5

class BacktestRequest(BaseModel):
    token: str
    long_exchange: str
    short_exchange: str
    config: StrategyConfig = StrategyConfig()

class BotCommand(BaseModel):
    action: str  # start, stop, status
    config: Optional[StrategyConfig] = None
    pairs: Optional[List[Dict[str, str]]] = None  # [{"token":"BTC","long":"extended","short":"binance"}]
