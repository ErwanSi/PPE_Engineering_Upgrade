import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import aiohttp
import pandas as pd

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    BASE_URL: str = "https://api.prod.paradex.trade/v1"
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "paradex_prices_5m_sync")
    LOOKBACK_MONTHS: int = 6

    CHUNK_HOURS: int = 50
    CHUNK_MS: int = CHUNK_HOURS * 3600 * 1000
    GLOBAL_RATE_LIMIT_PER_SECOND: float = 20.0
    MAX_CONCURRENT_MARKETS: int = 10
    REQUEST_TIMEOUT: int = 15
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
        self.capacity = rate_per_second
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


class ParadexPriceFetcher:
    def __init__(self):
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.rate_limiter = TokenBucket(Config.GLOBAL_RATE_LIMIT_PER_SECOND)
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_MARKETS)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return start_ts, end_ts

    async def get_markets(self, session: aiohttp.ClientSession) -> List[str]:
        url = f"{Config.BASE_URL}/markets"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                results = data.get("results", [])
                return [m["symbol"] for m in results if "PERP" in m.get("symbol", "")]
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def fetch_candles(self, session: aiohttp.ClientSession, market: str) -> List[List[Any]]:
        all_data = []
        curr_start = self.start_ts

        while curr_start < self.end_ts:
            curr_end = min(curr_start + Config.CHUNK_MS, self.end_ts)

            params = {
                "symbol": market,
                "resolution": "5",
                "start_at": curr_start,
                "end_at": curr_end
            }

            await self.rate_limiter.acquire()

            for attempt in range(Config.MAX_RETRIES):
                try:
                    async with session.get(
                        f"{Config.BASE_URL}/markets/klines",
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
                        results = resp_json.get("results", [])

                        if not results:
                            break

                        all_data.extend(results)
                        break

                except Exception as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        logger.error(f"Error fetching {market}: {e}")
                        return all_data
                    await asyncio.sleep(1)

            curr_start = curr_end + 1

        return all_data

    def process_and_save(self, market: str, raw_data: List[List[Any]]):
        if not raw_data:
            return

        std_name = market.replace("-PERP", "")

        try:
            df = pd.DataFrame(raw_data, columns=[
                'timestamp_ms', 'Open', 'High', 'Low', 'Close', 'Volume'
            ])

            df['timestamp_ms'] = df['timestamp_ms'].astype('int64')
            df['markPrice'] = df['Close'].astype(float)

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = std_name

            df = df.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')
            df_final = df[['datetime', 'timestamp_ms', 'market', 'markPrice']]

            file_path = os.path.join(Config.OUTPUT_DIR, f"{std_name}.parquet")
            df_final.to_parquet(file_path, index=False)

            logger.info(f"Saved {std_name}: {len(df_final)} candles")

        except Exception as e:
            logger.error(f"Processing error {market}: {e}")

    async def worker(self, session: aiohttp.ClientSession, market: str):
        async with self.semaphore:
            std_name = market.replace("-PERP", "")
            file_path = os.path.join(Config.OUTPUT_DIR, f"{std_name}.parquet")

            if os.path.exists(file_path):
                return

            data = await self.fetch_candles(session, market)
            self.process_and_save(market, data)

    async def run(self):
        logger.info("Starting Paradex 5m Price Sync (6 months)...")

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
    asyncio.run(ParadexPriceFetcher().run())