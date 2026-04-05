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
    BASE_URL: str = "https://fapi.binance.com"
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "binance_prices_5m_sync")
    LOOKBACK_MONTHS: int = 6

    LIMIT_KLINES: int = 1500
    GLOBAL_RATE_LIMIT_PER_SECOND: float = 4.0
    MAX_CONCURRENT_SYMBOLS: int = 20
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


class BinancePriceFetcher:
    def __init__(self):
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        self.start_ts, self.end_ts = self._get_time_window()
        self.rate_limiter = TokenBucket(Config.GLOBAL_RATE_LIMIT_PER_SECOND)
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_SYMBOLS)

    def _get_time_window(self):
        now = datetime.now(timezone.utc)
        end_dt = now
        start_dt = end_dt - timedelta(days=Config.LOOKBACK_MONTHS * 30)
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f"Time window: {start_dt.isoformat()} -> {end_dt.isoformat()}")
        return start_ts, end_ts

    async def get_symbols(self, session: aiohttp.ClientSession) -> List[str]:
        url = f"{Config.BASE_URL}/fapi/v1/exchangeInfo"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [
                    s["symbol"] for s in data["symbols"]
                    if s["contractType"] == "PERPETUAL" and s["status"] == "TRADING"
                ]
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {e}")
            return []

    async def fetch_klines(self, session: aiohttp.ClientSession, symbol: str) -> List[List]:
        all_data = []
        curr_start = self.start_ts

        while curr_start < self.end_ts:
            params = {
                "symbol": symbol,
                "interval": "5m",
                "startTime": curr_start,
                "endTime": self.end_ts,
                "limit": Config.LIMIT_KLINES
            }

            await self.rate_limiter.acquire()

            for attempt in range(Config.MAX_RETRIES):
                try:
                    async with session.get(
                        f"{Config.BASE_URL}/fapi/v1/klines",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                    ) as resp:
                        if resp.status in [418, 429]:
                            retry_after = int(resp.headers.get("Retry-After", 60))
                            logger.warning(f"Rate Limit on {symbol}. Pause {retry_after}s.")
                            await asyncio.sleep(retry_after)
                            continue

                        if resp.status != 200:
                            logger.error(f"HTTP {resp.status} for {symbol}")
                            return all_data

                        chunk = await resp.json()
                        if not chunk:
                            return all_data

                        all_data.extend(chunk)

                        last_open_time = chunk[-1][0]
                        if last_open_time >= self.end_ts - 300000:
                            return all_data

                        curr_start = last_open_time + 1
                        break

                except Exception as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        logger.error(f"Error fetching {symbol}: {e}")
                        return all_data
                    await asyncio.sleep(1)

        return all_data

    def process_and_save(self, symbol: str, raw_data: List[List]):
        if not raw_data:
            return

        short_name = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol

        try:
            df = pd.DataFrame(raw_data, columns=[
                'T', 'o', 'h', 'l', 'c', 'v', 'Tc', 'q', 'n', 'V', 'Q', 'B'
            ])

            df['timestamp_ms'] = df['T'].astype('int64')
            df['close_price'] = df['c'].astype(float)

            mask = (df['timestamp_ms'] >= self.start_ts) & (df['timestamp_ms'] <= self.end_ts)
            df = df.loc[mask].copy()

            if df.empty:
                return

            df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
            df['market'] = short_name
            df = df.sort_values('timestamp_ms').drop_duplicates('timestamp_ms')

            df_final = df[['datetime', 'timestamp_ms', 'market', 'close_price']]
            file_path = os.path.join(Config.OUTPUT_DIR, f"{short_name}.parquet")
            df_final.to_parquet(file_path, index=False)

            logger.info(f"Saved {short_name}: {len(df_final)} candles")

        except Exception as e:
            logger.error(f"Processing error {symbol}: {e}")

    async def worker(self, session: aiohttp.ClientSession, symbol: str):
        async with self.semaphore:
            short_name = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
            file_path = os.path.join(Config.OUTPUT_DIR, f"{short_name}.parquet")

            if os.path.exists(file_path):
                return

            data = await self.fetch_klines(session, symbol)
            self.process_and_save(symbol, data)

    async def run(self):
        logger.info("Starting Binance 5m Price Sync (6 months)...")

        async with aiohttp.ClientSession() as session:
            symbols = await self.get_symbols(session)
            if not symbols:
                logger.error("No symbols found.")
                return

            logger.info(f"Found {len(symbols)} pairs. Rate: {Config.GLOBAL_RATE_LIMIT_PER_SECOND} req/s")

            tasks = [self.worker(session, s) for s in symbols]
            await asyncio.gather(*tasks)

        logger.info("Sync completed.")


if __name__ == "__main__":
    asyncio.run(BinancePriceFetcher().run())