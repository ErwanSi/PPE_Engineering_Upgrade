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
    BASE_URL: str = "https://api.hyperliquid.xyz/info"
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "hyperliquid_funding_data")
    LOOKBACK_MONTHS: int = 6

    GLOBAL_RATE_LIMIT_PER_SECOND: float = 0.4
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 5

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class TokenBucket:
    def __init__(self, rate_per_second: float):
        self.rate = rate_per_second
        self.capacity = 1.0
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            new_tokens = elapsed * self.rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)

            if self.tokens >= 1:
                self.tokens -= 1
                return
            else:
                wait_needed = (1 - self.tokens) / self.rate
                self.tokens = 0
                self.last_update += wait_needed

        await asyncio.sleep(wait_needed)


class HyperliquidFundingFetcher:
    def __init__(self):
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.rate_limiter = TokenBucket(Config.GLOBAL_RATE_LIMIT_PER_SECOND)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    async def get_all_coins(self, session: aiohttp.ClientSession) -> List[str]:
        payload = {"type": "meta"}
        try:
            await self.rate_limiter.acquire()
            async with session.post(Config.BASE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [coin["name"] for coin in data.get("universe", [])]
        except Exception as e:
            logger.error(f"Failed to fetch metadata: {e}")
            return []

    async def fetch_funding_history(self, session: aiohttp.ClientSession, coin: str) -> List[Dict]:
        all_records = []
        curr_start = self.start_ts

        while curr_start < self.end_ts:
            payload = {
                "type": "fundingHistory",
                "coin": coin,
                "startTime": curr_start,
                "endTime": self.end_ts
            }

            await self.rate_limiter.acquire()

            for attempt in range(Config.MAX_RETRIES):
                try:
                    async with session.post(
                        Config.BASE_URL, json=payload,
                        timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status == 429:
                            wait_time = (2 ** attempt) + 10
                            logger.warning(f"Rate Limit (429) on {coin}. Pause {wait_time}s.")
                            await asyncio.sleep(wait_time)
                            continue

                        if resp.status != 200:
                            logger.error(f"HTTP {resp.status} for {coin}")
                            return all_records

                        data = await resp.json()

                        if not data:
                            return all_records

                        all_records.extend(data)

                        last_time = data[-1]['time']
                        if last_time >= self.end_ts - 3600000:
                            return all_records

                        curr_start = last_time + 1

                        if len(data) < 2:
                            return all_records

                        break

                except Exception as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        logger.error(f"Error fetching {coin}: {e}")
                        return all_records
                    await asyncio.sleep(1)

        return all_records

    def process_and_save(self, coin: str, raw_data: List[Dict]):
        if not raw_data:
            return

        try:
            df = pd.DataFrame(raw_data)
            df['timestamp_ms'] = df['time'].astype('int64')
            df['fundingRate'] = df['fundingRate'].astype(float)
            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = coin

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df = df.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')
            df_final = df[['datetime', 'timestamp_ms', 'market', 'fundingRate']]

            file_path = os.path.join(Config.DATA_DIR, f"HYPERLIQUID_{coin}.parquet")
            df_final.to_parquet(file_path, index=False)
            logger.info(f"Saved {coin}: {len(df_final)} rows")

        except Exception as e:
            logger.error(f"Processing error {coin}: {e}")

    async def run(self):
        logger.info(f"Starting Hyperliquid Funding Sync (6 months, {Config.GLOBAL_RATE_LIMIT_PER_SECOND} req/s)...")

        async with aiohttp.ClientSession() as session:
            coins = await self.get_all_coins(session)
            if not coins:
                return

            logger.info(f"Found {len(coins)} assets.")

            for i, coin in enumerate(coins):
                file_path = os.path.join(Config.DATA_DIR, f"HYPERLIQUID_{coin}.parquet")
                if os.path.exists(file_path):
                    continue

                logger.info(f"[{i+1}/{len(coins)}] Processing {coin}...")
                data = await self.fetch_funding_history(session, coin)
                self.process_and_save(coin, data)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(HyperliquidFundingFetcher().run())