import logging
import time
import requests
import redis
import re
from dataclasses import dataclass
from typing import Optional, Dict

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Endpoints
    URL_PREMIUM = "https://fapi.binance.com/fapi/v1/premiumIndex"
    URL_INFO = "https://fapi.binance.com/fapi/v1/fundingInfo"
    
    EXCHANGE_NAME: str = "binance"
    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 300

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- NORMALISATION ---
def normalize_symbol(raw_symbol: str) -> Optional[str]:
    if not raw_symbol: return None
    s = raw_symbol.upper()
    
    if re.search(r'-\d{2,}', s) or re.search(r'-\d+C$', s) or re.search(r'-\d+P$', s): return None
    if '_' in s and any(c.isdigit() for c in s): return None 

    for suffix in ["USDT", "USDC", "BUSD", "_PERP"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
            
    if s.startswith("1000") and len(s) > 4 and s[4:].isalpha(): s = s[4:]
    elif s.startswith("100") and len(s) > 3 and s[3:].isalpha(): s = s[3:]
    elif s.startswith("K") and s[1:] in ["SHIB", "BONK", "LUNC", "PEPE"]: s = s[1:]
    
    return s.replace("-", "").replace("_", "")

class BinanceLive:
    def __init__(self):
        try:
            self.r = redis.Redis(
                host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=Config.REDIS_DB, 
                decode_responses=True, socket_keepalive=True
            )
            self.r.ping()
            logger.info("✅ Connecté à Redis.")
        except Exception as e:
            logger.critical(f"❌ Erreur Redis: {e}")
            raise SystemExit(1)
            
        self.intervals_map = {} # Cache local {Symbol: IntervalHours}

    def update_intervals_map(self):
        """Récupère les intervalles de funding (4h vs 8h) pour chaque paire."""
        try:
            resp = requests.get(Config.URL_INFO, timeout=Config.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                count = 0
                for item in data:
                    sym = item.get('symbol')
                    interval = item.get('fundingIntervalHours', 8) # Par défaut 8h
                    if sym:
                        self.intervals_map[sym] = interval
                        if interval != 8: count += 1
                logger.info(f"ℹ️ Map des intervalles mise à jour ({len(self.intervals_map)} paires). {count} paires spéciales (4h).")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de maj les intervalles : {e}")

    def run(self):
        logger.info(f"🚀 Service Binance Live démarré.")
        
        # Premier chargement de la map
        self.update_intervals_map()
        last_map_update = time.time()

        while True:
            start_time = time.time()
            
            # Mise à jour de la map toutes les 6 heures (peu probable que ça change souvent)
            if time.time() - last_map_update > 21600:
                self.update_intervals_map()
                last_map_update = time.time()

            try:
                # Récupération des taux
                resp = requests.get(Config.URL_PREMIUM, timeout=Config.REQUEST_TIMEOUT)
                
                if resp.status_code == 429:
                    logger.warning("⚠️ Rate Limit 429. Pause 60s.")
                    time.sleep(60)
                    continue
                
                if resp.status_code == 200:
                    data = resp.json()
                    pipe = self.r.pipeline()
                    count = 0
                    
                    for item in data:
                        raw_sym = item.get('symbol')
                        raw_rate = item.get('lastFundingRate')
                        
                        if not raw_sym or raw_rate is None: continue
                        
                        token = normalize_symbol(raw_sym)
                        if token:
                            # 1. Récupération de l'intervalle spécifique
                            interval = self.intervals_map.get(raw_sym, 8)
                            
                            # 2. Calcul du facteur (ex: 100/8=12.5 ou 100/4=25.0)
                            scale_factor = 100.0 / interval
                            
                            # 3. Calcul final
                            rate_pct_hourly = float(raw_rate) * scale_factor
                            
                            pipe.hset(token, Config.EXCHANGE_NAME, str(rate_pct_hourly))
                            count += 1
                            
                    pipe.execute()
                    logger.info(f"✅ Binance: {count} taux mis à jour.")
                
            except Exception as e:
                logger.error(f"Erreur boucle: {e}")
                time.sleep(5)

            elapsed = time.time() - start_time
            time.sleep(max(0, Config.UPDATE_INTERVAL_SECONDS - elapsed))

if __name__ == "__main__":
    BinanceLive().run()