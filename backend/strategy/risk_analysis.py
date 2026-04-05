"""
Phase 1 — Risk Analysis
ADF Stationarity Test, Engle-Granger Cointegration, Hedge Ratio (β)
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant


class RiskAnalyzer:
    """
    Analyses the basis risk between two price series:
    - ADF test: is the spread stationary (mean-reverting)?
    - Engle-Granger cointegration: stable long-term linear relationship?
    - Hedge Ratio β: optimal hedge to minimize portfolio variance.
    
    Spread_t = P_long,t - β * P_short,t
    """

    def adf_test(self, series: pd.Series, name: str = "Series") -> Dict[str, Any]:
        """
        Augmented Dickey-Fuller test for stationarity.
        H0: Series has a unit root (non-stationary)
        H1: Series is stationary (mean-reverting)
        """
        clean = series.dropna()
        if len(clean) < 20:
            return {"name": name, "error": "Insufficient data (<20 points)"}

        result = adfuller(clean, autolag='AIC')

        return {
            "name": name,
            "test_statistic": round(float(result[0]), 4),
            "p_value": round(float(result[1]), 6),
            "lags_used": int(result[2]),
            "n_observations": int(result[3]),
            "critical_values": {k: round(float(v), 4) for k, v in result[4].items()},
            "is_stationary": result[1] < 0.05,
            "interpretation": (
                "✅ Stationary (mean-reverting) — Safe for arbitrage"
                if result[1] < 0.05
                else "⚠️ Non-stationary — Basis risk is HIGH"
            )
        }

    def cointegration_test(self, p_long: pd.Series, p_short: pd.Series) -> Dict[str, Any]:
        """
        Engle-Granger two-step cointegration test.
        Tests whether there exists a stable linear relationship: P_long = α + β * P_short + ε
        where ε is stationary.
        """
        # Align series on common index
        common = pd.concat([p_long, p_short], axis=1).dropna()
        if len(common) < 50:
            return {"error": "Insufficient overlapping data (<50 points)"}

        y = common.iloc[:, 0].values
        x = common.iloc[:, 1].values

        score, pvalue, crit_values = coint(y, x)

        return {
            "test_statistic": round(float(score), 4),
            "p_value": round(float(pvalue), 6),
            "critical_values": {
                "1%": round(float(crit_values[0]), 4),
                "5%": round(float(crit_values[1]), 4),
                "10%": round(float(crit_values[2]), 4),
            },
            "is_cointegrated": pvalue < 0.05,
            "interpretation": (
                "✅ Cointegrated — Stable long-term relationship exists"
                if pvalue < 0.05
                else "⚠️ Not cointegrated — Prices may diverge"
            )
        }

    def compute_hedge_ratio(self, p_long: pd.Series, p_short: pd.Series) -> Dict[str, Any]:
        """
        OLS regression: P_long = α + β * P_short
        β is the optimal hedge ratio that minimizes spread variance.
        """
        common = pd.concat([p_long, p_short], axis=1).dropna()
        if len(common) < 50:
            return {"error": "Insufficient data (<50 points)"}

        y = common.iloc[:, 0].values
        x = add_constant(common.iloc[:, 1].values)

        model = OLS(y, x).fit()
        beta = float(model.params[1])
        alpha = float(model.params[0])
        r_squared = float(model.rsquared)

        # Compute spread
        spread = common.iloc[:, 0] - beta * common.iloc[:, 1]

        return {
            "beta": round(beta, 6),
            "alpha": round(alpha, 6),
            "r_squared": round(r_squared, 4),
            "spread_mean": round(float(spread.mean()), 4),
            "spread_std": round(float(spread.std()), 4),
            "spread_current": round(float(spread.iloc[-1]), 4),
            "interpretation": (
                f"Hedge ratio β = {beta:.4f} — For every 1 unit long, short {beta:.4f} units"
            )
        }

    def compute_spread_series(self, p_long: pd.Series, p_short: pd.Series, beta: float) -> Optional[pd.Series]:
        """Compute the spread: S_t = P_long,t - β * P_short,t"""
        common = pd.concat([p_long, p_short], axis=1).dropna()
        if common.empty:
            return None
        return common.iloc[:, 0] - beta * common.iloc[:, 1]

    def full_analysis(self, p_long: pd.Series, p_short: pd.Series) -> Dict[str, Any]:
        """Run complete Phase 1 risk analysis."""
        # 1. ADF on individual series
        adf_long = self.adf_test(p_long, "Price (Long)")
        adf_short = self.adf_test(p_short, "Price (Short)")

        # 2. Hedge Ratio
        hedge = self.compute_hedge_ratio(p_long, p_short)
        beta = hedge.get("beta", 1.0)

        # 3. ADF on spread
        spread = self.compute_spread_series(p_long, p_short, beta)
        adf_spread = self.adf_test(spread, "Spread") if spread is not None else {"error": "No spread"}

        # 4. Cointegration
        coint_result = self.cointegration_test(p_long, p_short)

        # Overall verdict
        spread_stationary = adf_spread.get("is_stationary", False)
        is_cointegrated = coint_result.get("is_cointegrated", False)

        if spread_stationary and is_cointegrated:
            verdict = "✅ SAFE — Spread is mean-reverting and prices are cointegrated"
            risk_level = "LOW"
        elif spread_stationary or is_cointegrated:
            verdict = "⚠️ MODERATE — Partial evidence of stability"
            risk_level = "MEDIUM"
        else:
            verdict = "🔴 HIGH RISK — No statistical evidence of stability"
            risk_level = "HIGH"

        return {
            "adf_long": adf_long,
            "adf_short": adf_short,
            "adf_spread": adf_spread,
            "cointegration": coint_result,
            "hedge_ratio": hedge,
            "verdict": verdict,
            "risk_level": risk_level,
            "spread_series": (
                spread.tail(200).reset_index().rename(columns={0: "spread"}).to_dict(orient="records")
                if spread is not None else []
            )
        }
