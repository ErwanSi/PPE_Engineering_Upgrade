import asyncio
import logging
import os
import aiohttp
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict

# --- CONFIGURATION ---
class Config:
    BASE_URL = "https://fapi.binance.com"
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "binance_funding_data")
    LOOKBACK_MONTHS = 6

    # Rate Limit Safeguards
    MAX_CONCURRENT_REQUESTS = 10
    DEFAULT_WEIGHT_LIMIT = 2400

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class SmartBinanceFetcher:
    def __init__(self):
        self.start_ts, self.end_ts = self._get_time_window()
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)
        self.current_weight_usage = 0
        self.weight_limit = Config.DEFAULT_WEIGHT_LIMIT

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    async def fetch_funding(self, session: aiohttp.ClientSession, symbol: str):
        """Fetch full funding history with pagination (1000 records per page)."""
        async with self.semaphore:
            short_symbol = symbol.removesuffix("USDT")
            file_path = os.path.join(Config.DATA_DIR, f"BINANCE_{short_symbol}.parquet")

            if os.path.exists(file_path):
                return

            # Pre-flight weight check
            if self.current_weight_usage > (self.weight_limit * 0.95):
                logger.warning("Weight limit near 95%. Pausing 10s...")
                await asyncio.sleep(10)

            all_records = []
            current_start = self.start_ts

            while current_start < self.end_ts:
                params = {
                    "symbol": symbol,
                    "startTime": current_start,
                    "endTime": self.end_ts,
                    "limit": 1000
                }

                try:
                    url = f"{Config.BASE_URL}/fapi/v1/fundingRate"
                    async with session.get(url, params=params) as resp:
                        if resp.status == 418:
                            logger.critical("IP BANNED (418). STOPPING.")
                            raise SystemExit("IP BANNED")

                        if resp.status == 429:
                            retry_after = int(resp.headers.get("Retry-After", 60))
                            logger.warning(f"429 Rate Limit. Sleeping {retry_after}s.")
                            await asyncio.sleep(retry_after)
                            continue

                        if resp.status != 200:
                            logger.error(f"HTTP {resp.status} for {symbol}")
                            break

                        data_json = await resp.json()

                        # Track weight usage
                        used_weight = resp.headers.get('x-mbx-used-weight-1m')
                        if used_weight:
                            self.current_weight_usage = int(used_weight)

                        if not data_json:
                            break

                        all_records.extend(data_json)

                        # Pagination: if we got exactly 1000, there may be more
                        if len(data_json) < 1000:
                            break

                        # Move start to after the last record
                        last_ts = max(int(r['fundingTime']) for r in data_json)
                        current_start = last_ts + 1

                except Exception as e:
                    logger.error(f"Exception for {symbol}: {e}")
                    break

            await self._save_parquet(short_symbol, all_records)

    async def _save_parquet(self, short_symbol: str, data: List[Dict]):
        if not data:
            return

        try:
            df = pd.DataFrame(data)
            df['timestamp_ms'] = df['fundingTime'].astype('int64')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'])

            # Filter to our window
            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df_final = df.loc[mask].copy()

            if df_final.empty:
                return

            df_final['datetime'] = pd.to_datetime(df_final['timestamp_ms'], unit='ms')
            df_final['market'] = short_symbol
            df_final = df_final.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')

            file_path = os.path.join(Config.DATA_DIR, f"BINANCE_{short_symbol}.parquet")
            df_final[['datetime', 'timestamp_ms', 'market', 'fundingRate']].to_parquet(file_path, index=False)
            logger.info(f"Saved: {short_symbol} ({len(df_final)} records)")

        except Exception as e:
            logger.error(f"Processing error {short_symbol}: {e}")

    async def run(self):
        logger.info("Starting Binance Funding Sync (6 months)...")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{Config.BASE_URL}/fapi/v1/exchangeInfo") as r:
                    r.raise_for_status()
                    info = await r.json()

                    symbols = [
                        s["symbol"] for s in info["symbols"]
                        if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT"
                    ]

                    limits = info.get('rateLimits', [])
                    for l in limits:
                        if l['rateLimitType'] == 'REQUEST_WEIGHT' and l['interval'] == 'MINUTE':
                            self.weight_limit = l['limit']
                            logger.info(f"API Weight Limit: {self.weight_limit}/min")
            except Exception as e:
                logger.critical(f"Failed to fetch exchange info: {e}")
                return

            logger.info(f"Processing {len(symbols)} symbols...")
            tasks = [self.fetch_funding(session, s) for s in symbols]
            await asyncio.gather(*tasks)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(SmartBinanceFetcher().run())