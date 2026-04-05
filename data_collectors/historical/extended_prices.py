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
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "extended_prices_5m_sync")
    LOOKBACK_MONTHS: int = 6

    LIMIT_PER_REQ: int = 1000
    MAX_CONCURRENT_REQUESTS: int = 10
    REQUEST_TIMEOUT: int = 15
    MAX_RETRIES: int = 5

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ExtendedPriceFetcher:
    def __init__(self):
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return start_ts, end_ts

    async def get_markets(self, session: aiohttp.ClientSession) -> List[str]:
        url = f"{Config.BASE_URL}/api/v1/info/markets"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [m.get("name") for m in data.get("data", []) if m.get("name")]
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def fetch_candles(self, session: aiohttp.ClientSession, market: str) -> List[Dict]:
        all_data = []
        curr_cursor = self.end_ts

        while True:
            if curr_cursor < self.start_ts:
                break

            params = {
                "interval": "5m",
                "limit": Config.LIMIT_PER_REQ,
                "endTime": curr_cursor
            }

            chunk_fetched = False

            for attempt in range(Config.MAX_RETRIES):
                try:
                    async with session.get(
                        f"{Config.BASE_URL}/api/v1/info/candles/{market}/mark-prices",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status == 429:
                            wait = (2 ** attempt) + 1
                            logger.warning(f"Rate Limit 429 on {market}. Waiting {wait}s.")
                            await asyncio.sleep(wait)
                            continue

                        if resp.status != 200:
                            logger.error(f"HTTP {resp.status} for {market}")
                            return all_data

                        resp_json = await resp.json()
                        data = resp_json.get("data", [])

                        if not data:
                            return all_data

                        valid_chunk = [x for x in data if x['T'] >= self.start_ts]
                        all_data.extend(valid_chunk)

                        sorted_chunk = sorted(data, key=lambda x: x['T'])
                        oldest_ts = sorted_chunk[0]['T']

                        curr_cursor = oldest_ts - 1

                        if sorted_chunk[-1]['T'] < self.start_ts:
                            return all_data

                        chunk_fetched = True
                        break

                except Exception as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        logger.error(f"Error fetching {market}: {e}")
                        return all_data
                    await asyncio.sleep(1)

            if not chunk_fetched:
                break

            await asyncio.sleep(0.05)

        return all_data

    def process_and_save(self, market: str, raw_data: List[Dict]):
        if not raw_data:
            return

        try:
            df = pd.DataFrame(raw_data)
            df['timestamp_ms'] = df['T'].astype('int64')
            df['markPrice'] = df['c'].astype(float)

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = market

            df = df.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')
            df_final = df[['datetime', 'timestamp_ms', 'market', 'markPrice']]

            file_path = os.path.join(Config.OUTPUT_DIR, f"{market}.parquet")
            df_final.to_parquet(file_path, index=False)

            logger.info(f"Saved {market}: {len(df_final)} candles")

        except Exception as e:
            logger.error(f"Processing error {market}: {e}")

    async def worker(self, session: aiohttp.ClientSession, market: str):
        async with self.semaphore:
            file_path = os.path.join(Config.OUTPUT_DIR, f"{market}.parquet")
            if os.path.exists(file_path):
                return

            data = await self.fetch_candles(session, market)
            self.process_and_save(market, data)

    async def run(self):
        logger.info("Starting Extended 5m Price Sync (6 months)...")

        async with aiohttp.ClientSession() as session:
            markets = await self.get_markets(session)
            if not markets:
                logger.error("No markets found.")
                return

            logger.info(f"Found {len(markets)} markets.")

            tasks = [self.worker(session, m) for m in markets]
            await asyncio.gather(*tasks)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(ExtendedPriceFetcher().run())