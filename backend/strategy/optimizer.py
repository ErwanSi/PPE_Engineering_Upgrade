import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from strategy.backtester import EventDrivenBacktester

class StrategyOptimizer:
    """
    Runs dynamic grid search to find optimal Z-score and Lookback parameters.
    Ranks by Sharpe Ratio.
    """
    
    def __init__(self, data_service):
        self.data_service = data_service

    def run_optimization(self, token: str, long_exchange: str, short_exchange: str, base_config: Any) -> List[Dict[str, Any]]:
        # Fetch data once
        p_long = self.data_service.get_price_series(token, long_exchange)
        p_short = self.data_service.get_price_series(token, short_exchange)
        f_long = self.data_service.get_funding_series(token, long_exchange)
        f_short = self.data_service.get_funding_series(token, short_exchange)

        if p_long is None or p_short is None or f_long is None or f_short is None:
            return []

        # Define Grid
        z_entries = [1.5, 2.0, 2.5, 3.0]
        z_exits = [0.0, 0.5]
        lookbacks = [72, 168, 336]
        
        results = []
        
        # We use a copy of the base config to keep fee settings etc
        from schemas import StrategyConfig

        for z_entry in z_entries:
            for z_exit in z_exits:
                for lb in lookbacks:
                    # Skip if exit >= entry
                    if z_exit >= z_entry: continue
                    
                    test_config = StrategyConfig(**base_config.dict())
                    test_config.zscore_entry = z_entry
                    test_config.zscore_exit = z_exit
                    test_config.lookback_hours = lb
                    
                    backtester = EventDrivenBacktester(test_config)
                    res = backtester.run(p_long, p_short, f_long, f_short)
                    
                    if "metrics" in res and res["metrics"].get("total_trades", 0) > 0:
                        m = res["metrics"]
                        results.append({
                            "params": {
                                "zscore_entry": z_entry,
                                "zscore_exit": z_exit,
                                "lookback_hours": lb
                            },
                            "sharpe": m.get("sharpe_ratio", 0),
                            "pnl": m.get("total_pnl_pct", 0),
                            "trades": m.get("total_trades", 0),
                            "win_rate": m.get("win_rate", 0)
                        })
        
        # Sort by Sharpe then PnL
        results.sort(key=lambda x: (x["sharpe"], x["pnl"]), reverse=True)
        return results[:5]

    def get_best_config(self, token: str, long_exchange: str, short_exchange: str, base_config: Any) -> Optional[Any]:
        """Finds the single best config for a pair."""
        results = self.run_optimization(token, long_exchange, short_exchange, base_config)
        if not results:
            return None
        
        best = results[0]["params"]
        from schemas import StrategyConfig
        new_cfg = StrategyConfig(**base_config.dict())
        new_cfg.zscore_entry = best["zscore_entry"]
        new_cfg.zscore_exit = best["zscore_exit"]
        new_cfg.lookback_hours = best["lookback_hours"]
        return new_cfg
