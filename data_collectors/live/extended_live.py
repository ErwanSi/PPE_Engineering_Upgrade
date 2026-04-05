import logging
import time
import requests
import redis
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    API_URL: str = "https://api.starknet.extended.exchange/api/v1/info/markets"
    EXCHANGE_NAME: str = "extended"
    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 60
    SCALE_FACTOR: float = 100.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- NORMALISATION ---
def normalize_symbol(raw_symbol: str) -> Optional[str]:
    if not raw_symbol: return None
    s = raw_symbol.upper()
    
    # 1. Filtre Anti-Options / Futures Datés
    if re.search(r'-\d{2,}', s) or re.search(r'-\d+C$', s) or re.search(r'-\d+P$', s):
        return None

    # 2. Nettoyage Suffixes
    for suffix in ["-PERP", "_PERP", "PERP", "-USD", "/USD", "USDT", "USDC", "USD", "BUSD"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break

    # 3. Nettoyage Préfixes
    if s.startswith("1000") and len(s) > 4 and s[4:].isalpha(): s = s[4:]
    elif s.startswith("100") and len(s) > 3 and s[3:].isalpha(): s = s[3:]
    elif s.startswith("1M") and len(s) > 2: s = s[2:] # Extended specifique: 1MPEPE
    elif s.startswith("K") and s[1:] in ["SHIB", "BONK", "LUNC", "PEPE"]: s = s[1:]

    return s.replace("-", "").replace("_", "")

class ExtendedFundingService:
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

    def fetch_markets(self) -> Optional[List[Dict[str, Any]]]:
        try:
            response = requests.get(Config.API_URL, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            json_data = response.json()
            return json_data.get("data", [])
        except requests.RequestException as e:
            logger.error(f"⚠️ Erreur API Extended: {e}")
            return None
        except ValueError:
            logger.error("⚠️ Erreur décodage JSON.")
            return None

    def update_redis(self, markets: List[Dict[str, Any]]):
        if not markets: return

        pipe = self.redis_client.pipeline()
        count = 0

        for market in markets:
            try:
                raw_token = market.get("assetName")
                market_stats = market.get("marketStats")
                
                if not raw_token or not market_stats: continue

                # Normalisation du nom
                token = normalize_symbol(raw_token)
                if not token: continue # Token rejeté (Option ou invalide)

                raw_funding = market_stats.get("fundingRate")
                
                if raw_funding is not None:
                    funding_rate = float(raw_funding)
                    funding_pct = funding_rate * Config.SCALE_FACTOR
                    pipe.hset(token, Config.EXCHANGE_NAME, str(funding_pct))
                    count += 1
                    
            except (ValueError, TypeError):
                continue

        if count > 0:
            try:
                pipe.execute()
                logger.info(f"🔄 Redis mis à jour : {count} taux Extended.")
            except redis.RedisError as e:
                logger.error(f"❌ Erreur Pipeline Redis: {e}")

    def run_forever(self):
        logger.info(f"🚀 Service Extended démarré.")
        while True:
            start_time = time.time()
            try:
                markets_data = self.fetch_markets()
                if markets_data:
                    self.update_redis(markets_data)
            except Exception as e:
                logger.error(f"🔥 Erreur boucle: {e}")

            elapsed = time.time() - start_time
            time.sleep(max(0, Config.UPDATE_INTERVAL_SECONDS - elapsed))

if __name__ == "__main__":
    service = ExtendedFundingService()
    service.run_forever()