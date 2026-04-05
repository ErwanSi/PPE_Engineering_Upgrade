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
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "hyperliquid_prices_5m_sync")
    LOOKBACK_MONTHS: int = 6

    CHUNK_MS: int = 24 * 3600 * 1000  # 1 day
    GLOBAL_RATE_LIMIT_PER_SECOND: float = 0.33
    REQUEST_TIMEOUT: int = 15

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
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens < 1:
                wait_needed = (1 - self.tokens) / self.rate
                self.tokens = 0
                self.last_update += wait_needed
            else:
                wait_needed = 0
                self.tokens -= 1
        if wait_needed > 0:
            await asyncio.sleep(wait_needed)


class HyperliquidPriceFetcher:
    def __init__(self):
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.rate_limiter = TokenBucket(Config.GLOBAL_RATE_LIMIT_PER_SECOND)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return start_ts, end_ts

    async def get_universe(self, session: aiohttp.ClientSession) -> List[str]:
        try:
            await self.rate_limiter.acquire()
            async with session.post(Config.BASE_URL, json={"type": "meta"}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [c["name"] for c in data.get("universe", [])]
        except Exception:
            pass
        return []

    async def fetch_full_history(self, session: aiohttp.ClientSession, coin: str) -> List[Dict]:
        all_data = []
        curr_start = self.start_ts

        while curr_start < self.end_ts:
            curr_end = min(curr_start + Config.CHUNK_MS, self.end_ts)

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": "5m",
                    "startTime": curr_start,
                    "endTime": curr_end
                }
            }

            while True:
                await self.rate_limiter.acquire()
                try:
                    async with session.post(Config.BASE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                        if resp.status == 429:
                            await asyncio.sleep(30)
                            continue

                        if resp.status == 200:
                            data = await resp.json()
                            if data:
                                all_data.extend(data)
                            break
                        else:
                            await asyncio.sleep(5)
                            continue

                except Exception:
                    await asyncio.sleep(1)
                    continue

            curr_start = curr_end + 1

        return all_data

    def process_and_save(self, coin: str, raw_data: List[Dict]):
        if not raw_data:
            return
        try:
            df = pd.DataFrame(raw_data)
            df['timestamp_ms'] = df['t'].astype('int64')
            df['close_price'] = df['c'].astype(float)

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = coin
            df = df.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')

            path = os.path.join(Config.OUTPUT_DIR, f"{coin}.parquet")
            df[['datetime', 'timestamp_ms', 'market', 'close_price']].to_parquet(path, index=False)

            logger.info(f"Saved {coin}: {len(df)} candles")
        except Exception as e:
            logger.error(f"Error saving {coin}: {e}")

    async def run(self):
        logger.info("Starting Hyperliquid 5m Price Sync (6 months)...")
        async with aiohttp.ClientSession() as session:
            coins = await self.get_universe(session)
            if not coins:
                return

            total = len(coins)
            for i, coin in enumerate(coins):
                path = os.path.join(Config.OUTPUT_DIR, f"{coin}.parquet")
                if os.path.exists(path):
                    if os.path.getsize(path) > 10000:
                        continue

                logger.info(f"[{i+1}/{total}] Downloading {coin}...")
                data = await self.fetch_full_history(session, coin)
                self.process_and_save(coin, data)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(HyperliquidPriceFetcher().run())