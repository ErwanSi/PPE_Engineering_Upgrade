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
    BASE_URL: str = "https://api.prod.paradex.trade/v1"
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "paradex_funding_data")
    LOOKBACK_MONTHS: int = 6

    PAGE_SIZE: int = 1000
    REQUEST_TIMEOUT: int = 40
    MAX_RETRIES: int = 8
    GLOBAL_RATE_LIMIT_PER_SECOND: float = 20.0
    MAX_CONCURRENT_MARKETS: int = 5

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


class ParadexFundingFetcher:
    def __init__(self):
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_MARKETS)
        self.rate_limiter = TokenBucket(Config.GLOBAL_RATE_LIMIT_PER_SECOND)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    async def get_all_markets(self, session: aiohttp.ClientSession) -> List[str]:
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

    async def fetch_market_funding(self, session: aiohttp.ClientSession, market: str) -> List[Dict]:
        all_records = []
        next_cursor = None

        base_params = {
            "market": market,
            "start_at": self.start_ts,
            "end_at": self.end_ts,
            "page_size": Config.PAGE_SIZE
        }

        while True:
            params = base_params.copy()
            if next_cursor:
                params["cursor"] = next_cursor

            await self.rate_limiter.acquire()

            for attempt in range(Config.MAX_RETRIES):
                try:
                    async with session.get(
                        f"{Config.BASE_URL}/funding/data",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status == 429:
                            wait_time = (2 ** attempt) + 1
                            logger.warning(f"Rate Limit 429 on {market}. Retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue

                        if resp.status != 200:
                            logger.error(f"HTTP Error {resp.status} for {market}")
                            return all_records

                        data_json = await resp.json()
                        results = data_json.get("results", [])

                        if not results:
                            return all_records

                        all_records.extend(results)
                        next_cursor = data_json.get("next")
                        break

                except Exception as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        logger.error(f"Failed to fetch {market} after retries: {e}")
                        return all_records
                    await asyncio.sleep(1)

            if not next_cursor:
                break

        return all_records

    def process_and_save(self, market: str, raw_data: List[Dict]):
        if not raw_data:
            return

        std_name = market.replace("-PERP", "")

        try:
            df = pd.DataFrame(raw_data)
            df['timestamp_ms'] = df['created_at'].astype('int64')
            df['fundingRate'] = pd.to_numeric(df['funding_rate'], errors='coerce')
            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df = df.set_index('datetime').sort_index()

            # 1H Standard
            df_1h = df.resample('1h').agg({
                'fundingRate': 'mean',
                'timestamp_ms': 'last'
            }).dropna().reset_index()

            df_1h['market'] = std_name
            path_1h = os.path.join(Config.OUTPUT_DIR, f"PARADEX_{std_name}.parquet")
            df_1h[['datetime', 'timestamp_ms', 'market', 'fundingRate']].to_parquet(path_1h, index=False)

            # 1M High-Res
            df_1m = df.resample('1min').agg({
                'fundingRate': 'mean',
                'timestamp_ms': 'last'
            }).dropna().reset_index()

            df_1m['market'] = std_name
            path_1m = os.path.join(Config.OUTPUT_DIR, f"PARADEX_{std_name}_1m.parquet")
            df_1m[['datetime', 'timestamp_ms', 'market', 'fundingRate']].to_parquet(path_1m, index=False)

            logger.info(f"Saved {std_name}: 1H ({len(df_1h)} rows) | 1M ({len(df_1m)} rows)")

        except Exception as e:
            logger.error(f"Data processing error for {market}: {e}")

    async def worker(self, session: aiohttp.ClientSession, market: str):
        async with self.semaphore:
            std_name = market.replace("-PERP", "")

            path_1h = os.path.join(Config.OUTPUT_DIR, f"PARADEX_{std_name}.parquet")
            path_1m = os.path.join(Config.OUTPUT_DIR, f"PARADEX_{std_name}_1m.parquet")

            if os.path.exists(path_1h) and os.path.exists(path_1m):
                return

            logger.info(f"Starting download for {std_name}...")
            data = await self.fetch_market_funding(session, market)
            self.process_and_save(market, data)

    async def run(self):
        logger.info("Starting Paradex Funding Sync (6 months)...")

        async with aiohttp.ClientSession() as session:
            markets = await self.get_all_markets(session)
            if not markets:
                logger.critical("No markets found.")
                return

            logger.info(f"Found {len(markets)} markets.")
            tasks = [self.worker(session, m) for m in markets]
            await asyncio.gather(*tasks)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(ParadexFundingFetcher().run())