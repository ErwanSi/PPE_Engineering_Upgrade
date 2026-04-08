"""
Data Service — Bridge between Parquet/Redis and API layer.
"""
import os
import itertools
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
import redis
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed')


class DataService:
    def __init__(self):
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                socket_timeout=2
            )
            self.redis_client.ping()
        except Exception:
            self.redis_client = None

        # Cache for parquet data
        self._cache: Dict[str, pd.DataFrame] = {}

    # ============================
    # LIVE DATA (Redis)
    # ============================
    def get_live_rates(self) -> Dict[str, Dict[str, float]]:
        if not self.redis_client:
            return {}

        try:
            keys = self.redis_client.keys("*")
            if not keys:
                return {}

            pipe = self.redis_client.pipeline()
            for k in keys:
                pipe.hgetall(k)
            results = pipe.execute()

            output = {}
            for token, rates in zip(keys, results):
                parsed = {}
                for exch, val in rates.items():
                    try:
                        parsed[exch] = float(val)
                    except (ValueError, TypeError):
                        continue
                if parsed:
                    output[token] = parsed

            return output
        except Exception:
            return {}

    # ============================
    # HISTORICAL DATA (Parquet)
    # ============================
    def _load_matrix(self, data_type: str) -> Optional[pd.DataFrame]:
        cache_key = data_type
        if cache_key in self._cache:
            return self._cache[cache_key]

        filename = f"MASTER_{data_type}.parquet"
        path = os.path.join(DATA_DIR, filename)

        if not os.path.exists(path):
            return None

        try:
            df = pd.read_parquet(path)
            self._cache[cache_key] = df
            return df
        except Exception:
            return None

    def get_available_tokens(self) -> List[str]:
        df = self._load_matrix("PRICES_5M")
        if df is None:
            return []
        try:
            return sorted(df.columns.get_level_values('token').unique().tolist())
        except Exception:
            return []

    def get_token_exchanges(self, token: str) -> List[str]:
        df_p = self._load_matrix("PRICES_5M")
        df_f = self._load_matrix("FUNDING_1H")
        if df_p is None or df_f is None:
            return []
        try:
            p_subset = df_p.xs(token, axis=1, level='token')
            f_subset = df_f.xs(token, axis=1, level='token')
            # Intersection of columns (exchanges) present in both
            common_exchanges = set(p_subset.columns).intersection(set(f_subset.columns))
            return sorted(list(common_exchanges))
        except (KeyError, Exception):
            return []

    def get_funding_series(self, token: str, exchange: str) -> Optional[pd.Series]:
        df = self._load_matrix("FUNDING_1H")
        if df is None:
            return None
        try:
            return df[(token, exchange)].dropna()
        except (KeyError, Exception):
            return pd.Series(dtype=float)

    def get_price_series(self, token: str, exchange: str) -> Optional[pd.Series]:
        df = self._load_matrix("PRICES_5M")
        if df is None:
            return None
        try:
            return df[(token, exchange)].dropna()
        except (KeyError, Exception):
            return pd.Series(dtype=float)

    def get_data_quality(self) -> Dict[str, Any]:
        df = self._load_matrix("PRICES_5M")
        if df is None:
            return {"error": "Data not found"}

        total_cells = df.size
        missing_cells = int(df.isna().sum().sum())
        density = 100 * (1 - missing_cells / total_cells) if total_cells > 0 else 0

        # Per-token quality
        token_quality = []
        try:
            for token in df.columns.get_level_values('token').unique():
                subset = df.xs(token, axis=1, level='token')
                first_valid = subset.first_valid_index()
                if first_valid is None:
                    continue
                
                token_missing_rates = []
                for exch in subset.columns:
                    s = subset[exch]
                    idx = s.first_valid_index()
                    if idx is not None:
                        token_missing_rates.append(s.loc[idx:].isna().mean())
                
                missing_pct = float(np.mean(token_missing_rates) * 100) if token_missing_rates else 0.0

                last_valid = subset.index[subset.notna().any(axis=1)][-1] if subset.notna().any(axis=1).any() else None

                token_quality.append({
                    "token": token,
                    "exchanges": list(subset.columns),
                    "first_date": str(first_valid) if first_valid else None,
                    "last_date": str(last_valid) if last_valid else None,
                    "missing_pct": round(missing_pct, 2)
                })
        except Exception:
            pass

        return {
            "nb_assets": df.shape[1],
            "total_points": total_cells,
            "density_pct": round(density, 2),
            "date_range": {
                "start": str(df.index.min()),
                "end": str(df.index.max())
            },
            "tokens": token_quality
        }

    def scan_opportunities(self) -> List[Dict]:
        df_f = self._load_matrix("FUNDING_1H")
        df_p = self._load_matrix("PRICES_5M") # Added to check availability
        if df_f is None:
            return []

        mean_rates = df_f.mean()
        results = []

        try:
            # We filter by tokens that have both funding and price data
            f_tokens = set(mean_rates.index.get_level_values('token').unique())
            p_tokens = set(df_p.columns.get_level_values('token').unique()) if df_p is not None else set()
            unique_tokens = f_tokens.intersection(p_tokens)
        except Exception:
            return []

        for token in unique_tokens:
            try:
                # Intersection of exchanges for this token
                f_exch = set(df_f[token].columns)
                p_exch = set(df_p[token].columns)
                exchanges = list(f_exch.intersection(p_exch))
            except KeyError:
                continue

            if len(exchanges) < 2:
                continue

            for l_ex, s_ex in itertools.permutations(exchanges, 2):
                try:
                    net = float(mean_rates[(token, s_ex)] - mean_rates[(token, l_ex)])
                    apr = net * 24 * 365 * 100
                    results.append({
                        "token": token,
                        "long_exchange": l_ex,
                        "short_exchange": s_ex,
                        "hourly_pct": round(net * 100, 6),
                        "apr_pct": round(apr, 2)
                    })
                except Exception:
                    continue

        results.sort(key=lambda x: x["apr_pct"], reverse=True)
        return results
