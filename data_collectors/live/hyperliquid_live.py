import logging
import json
import redis
import requests
import time
import re
from dataclasses import dataclass
from typing import Optional

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    API_URL: str = "https://api.hyperliquid.xyz/info"
    EXCHANGE_NAME: str = "hyperliquid"
    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 60
    SCALE_FACTOR: float = 100.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- NORMALISATION ---
def normalize_symbol(raw_symbol: str) -> Optional[str]:
    if not raw_symbol: return None
    s = raw_symbol.upper()
    
    # 1. Filtre
    if re.search(r'-\d{2,}', s) or re.search(r'-\d+C$', s) or re.search(r'-\d+P$', s):
        return None

    # 2. Suffixes
    for suffix in ["USDT", "USDC", "-USD", "USD", "_PERP", "-PERP"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break

    # 3. Préfixes
    if s.startswith("1000") and len(s) > 4 and s[4:].isalpha(): s = s[4:]
    elif s.startswith("100") and len(s) > 3 and s[3:].isalpha(): s = s[3:]
    elif s.startswith("K") and s[1:] in ["SHIB", "BONK", "PEPE"]: s = s[1:]
    
    return s.replace("-", "").replace("_", "")

class HyperliquidLive:
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True,
                socket_keepalive=True
            )
            self.redis_client.ping()
            logger.info("✅ Connecté à Redis.")
        except redis.ConnectionError as e:
            logger.critical(f"❌ Echec connexion Redis: {e}")
            raise SystemExit(1)

    def fetch_data(self) -> Optional[list]:
        payload = {"type": "predictedFundings"}
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(
                Config.API_URL, 
                headers=headers, 
                data=json.dumps(payload),
                timeout=Config.REQUEST_TIMEOUT
            )
            if response.status_code == 429:
                logger.warning("⚠️ Rate Limit Hyperliquid (429).")
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"⚠️ Erreur API: {e}")
            return None

    def update_redis(self, data: list):
        if not data: return
        pipe = self.redis_client.pipeline()
        count = 0
        for item in data:
            try:
                raw_token = item[0]
                venues = item[1]
                for v in venues:
                    if v[0] == "HlPerp":
                        token = normalize_symbol(raw_token)
                        if not token: continue # Token rejeté
                        
                        raw_rate = float(v[1]["fundingRate"])
                        rate_pct = raw_rate * Config.SCALE_FACTOR
                        pipe.hset(token, Config.EXCHANGE_NAME, str(rate_pct))
                        count += 1
            except Exception:
                continue

        if count > 0:
            try:
                pipe.execute()
                logger.info(f"✅ Hyperliquid: {count} updates.")
            except redis.RedisError as e:
                logger.error(f"❌ Erreur Redis: {e}")

    def run_forever(self):
        logger.info(f"🚀 Service Hyperliquid démarré.")
        while True:
            start_time = time.time()
            try:
                data = self.fetch_data()
                if data: self.update_redis(data)
            except Exception as e:
                logger.error(f"🔥 Erreur boucle: {e}")

            elapsed = time.time() - start_time
            time.sleep(max(0, Config.UPDATE_INTERVAL_SECONDS - elapsed))

if __name__ == "__main__":
    HyperliquidLive().run_forever()