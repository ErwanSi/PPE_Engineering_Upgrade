import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict

import aiohttp
import pandas as pd

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    BASE_URL: str = "https://api.starknet.extended.exchange"
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "extended_funding_data")
    LOOKBACK_MONTHS: int = 6

    LIMIT_PER_REQUEST: int = 10000
    MAX_CONCURRENT_REQUESTS: int = 10
    REQUEST_TIMEOUT: int = 15

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ExtendedFundingFetcher:
    def __init__(self):
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    async def get_markets(self, session: aiohttp.ClientSession) -> List[str]:
        url = f"{Config.BASE_URL}/api/v1/info/markets"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                market_list = data.get("data", [])
                return [m.get("name") for m in market_list if m.get("name")]
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def fetch_funding_history(self, session: aiohttp.ClientSession, market: str) -> List[Dict]:
        url = f"{Config.BASE_URL}/api/v1/info/{market}/funding"

        params = {
            "startTime": self.start_ts,
            "endTime": self.end_ts,
            "limit": Config.LIMIT_PER_REQUEST
        }

        async with self.semaphore:
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                    if resp.status == 429:
                        logger.warning(f"Rate Limit hit for {market}. Retrying in 5s...")
                        await asyncio.sleep(5)
                        return await self.fetch_funding_history(session, market)

                    resp.raise_for_status()
                    json_resp = await resp.json()
                    return json_resp.get("data", [])

            except Exception as e:
                logger.error(f"Error fetching {market}: {e}")
                return []

    def process_and_save(self, market: str, raw_data: List[Dict]):
        if not raw_data:
            return

        try:
            df = pd.DataFrame(raw_data)

            if 'T' not in df.columns or 'f' not in df.columns:
                logger.error(f"Invalid data format for {market}. Columns: {list(df.columns)}")
                return

            df = df.rename(columns={'T': 'timestamp_ms', 'f': 'fundingRate'})
            df['timestamp_ms'] = df['timestamp_ms'].astype('int64')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')

            # Filter window
            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = market

            df_final = df[['datetime', 'timestamp_ms', 'market', 'fundingRate']].sort_values('timestamp_ms')
            df_final = df_final.drop_duplicates('timestamp_ms')

            file_path = os.path.join(Config.DATA_DIR, f"{market}.parquet")
            df_final.to_parquet(file_path, index=False)
            logger.info(f"Saved {market}: {len(df_final)} records")

        except Exception as e:
            logger.error(f"Processing error {market}: {e}")

    async def run_pipeline(self):
        logger.info("Starting Extended Exchange Funding Sync (6 months)...")

        async with aiohttp.ClientSession() as session:
            markets = await self.get_markets(session)
            if not markets:
                logger.critical("No markets found. Exiting.")
                return

            logger.info(f"Found {len(markets)} markets.")

            tasks = []
            for market in markets:
                async def task_wrapper(m):
                    data = await self.fetch_funding_history(session, m)
                    self.process_and_save(m, data)

                tasks.append(task_wrapper(market))

            await asyncio.gather(*tasks)

        logger.info("Sync completed.")


if __name__ == "__main__":
    fetcher = ExtendedFundingFetcher()
    asyncio.run(fetcher.run_pipeline())