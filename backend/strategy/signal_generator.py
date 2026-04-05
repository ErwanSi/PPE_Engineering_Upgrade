"""
Phase 3 — Z-Score Signal Generator
Adaptive statistical signal based on the spread of funding rates.
Z = (X_t - μ) / σ
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple


class SignalGenerator:
    """
    Generates trading signals based on Z-Score of the funding rate spread.
    
    - Z < -entry_threshold → LONG signal (funding abnormally low)
    - Z > +entry_threshold → SHORT signal (funding abnormally high)  
    - |Z| < exit_threshold → EXIT signal (return to equilibrium)
    """

    def __init__(self, lookback_hours: int = 168, entry_threshold: float = 2.0, exit_threshold: float = 0.5):
        self.lookback = lookback_hours
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def compute_funding_spread(self, f_long: pd.Series, f_short: pd.Series) -> Optional[pd.Series]:
        """
        Compute net funding spread: what you earn per hour.
        Long position pays f_long, short position receives f_short.
        Net = -f_long + f_short = f_short - f_long
        """
        if f_long is None or f_short is None:
            return None

        combined = pd.concat([f_long, f_short], axis=1).dropna()
        if combined.empty:
            return None

        spread = combined.iloc[:, 1] - combined.iloc[:, 0]
        spread.name = "funding_spread"
        return spread

    def compute_zscore(self, f_long: pd.Series, f_short: pd.Series) -> Optional[pd.Series]:
        """
        Compute rolling Z-Score of the funding spread.
        Z_t = (X_t - μ_rolling) / σ_rolling
        """
        spread = self.compute_funding_spread(f_long, f_short)
        if spread is None or len(spread) < self.lookback:
            return None

        rolling_mean = spread.rolling(window=self.lookback).mean()
        rolling_std = spread.rolling(window=self.lookback).std()

        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)

        zscore = (spread - rolling_mean) / rolling_std
        zscore.name = "zscore"
        return zscore.dropna()

    def get_signal(self, zscore: float) -> str:
        """
        Determine signal from a single Z-Score value.
        """
        if zscore < -self.entry_threshold:
            return "LONG"  # Funding abnormally low → expect increase
        elif zscore > self.entry_threshold:
            return "SHORT"  # Funding abnormally high → expect decrease
        elif abs(zscore) < self.exit_threshold:
            return "EXIT"  # Return to equilibrium
        else:
            return "HOLD"  # Between thresholds, maintain position

    def generate_signals(self, f_long: pd.Series, f_short: pd.Series) -> Optional[pd.DataFrame]:
        """
        Generate full signal series with Z-Score, funding spread, and signals.
        """
        spread = self.compute_funding_spread(f_long, f_short)
        zscore = self.compute_zscore(f_long, f_short)

        if spread is None or zscore is None:
            return None

        # Align on common index
        common_idx = spread.index.intersection(zscore.index)

        df = pd.DataFrame({
            "funding_spread": spread.loc[common_idx],
            "zscore": zscore.loc[common_idx],
        })

        df["signal"] = df["zscore"].apply(self.get_signal)

        # Detect signal transitions
        df["signal_change"] = df["signal"] != df["signal"].shift(1)
        df["entry"] = df["signal_change"] & df["signal"].isin(["LONG", "SHORT"])
        df["exit"] = df["signal_change"] & (df["signal"] == "EXIT")

        return df

    def current_state(self, f_long: pd.Series, f_short: pd.Series) -> Dict[str, Any]:
        """
        Get the current signal state.
        """
        zscore_series = self.compute_zscore(f_long, f_short)
        spread = self.compute_funding_spread(f_long, f_short)

        if zscore_series is None or spread is None:
            return {"error": "Insufficient data"}

        current_z = float(zscore_series.iloc[-1])
        current_spread = float(spread.iloc[-1])
        signal = self.get_signal(current_z)

        return {
            "zscore": round(current_z, 4),
            "funding_spread": round(current_spread, 6),
            "signal": signal,
            "entry_threshold": self.entry_threshold,
            "exit_threshold": self.exit_threshold,
            "lookback_hours": self.lookback,
            "zscore_mean_7d": round(float(zscore_series.tail(168).mean()), 4),
            "zscore_std_7d": round(float(zscore_series.tail(168).std()), 4),
        }
