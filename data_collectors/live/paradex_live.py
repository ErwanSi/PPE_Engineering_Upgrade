import json
import logging
import time
import redis
import websocket
import re

# --- CONFIGURATION ---
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
EXCHANGE_NAME = "paradex"
WS_URL = "wss://ws.api.prod.paradex.trade/v1?/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- NORMALISATION STANDARDISÉE ---
def normalize_symbol(raw_symbol):
    """
    Transforme :
    - KBONK-USD-PERP -> BONK
    - BTC-USD-PERP -> BTC
    """
    if not raw_symbol: return None
    s = raw_symbol.upper()
    
    # 1. Filtre Anti-Options (Paradex ne liste pas d'options PERP mais sait-on jamais)
    # Cherche motif date ou option (-C, -P)
    if re.search(r'-\d{2,}', s) or re.search(r'-\d+C$', s) or re.search(r'-\d+P$', s):
        return None

    # 2. Nettoyage Suffixes (D'abord PERP, puis USD)
    if s.endswith("-PERP"): s = s[:-5]
    elif s.endswith("PERP"): s = s[:-4]
    
    # Si après retrait de PERP il reste -USD (ex: BTC-USD), on l'enlève
    if s.endswith("-USD"): s = s[:-4]
    elif s.endswith("USD"): s = s[:-3]

    # 3. Nettoyage Préfixes (Multiplicateurs)
    # Cas spécifique kSHIB, kBONK, kPEPE, kLUNC
    if s.startswith("K") and s[1:] in ["SHIB", "BONK", "LUNC", "PEPE"]: 
        s = s[1:]
    # Cas spécifique 1000PEPE (rare sur Paradex mais possible)
    elif s.startswith("1000") and len(s) > 4: 
        s = s[4:]

    # 4. Nettoyage Final (Tirets résiduels)
    return s.replace("-", "").replace("_", "")

class ParadexLive:
    def __init__(self):
        try:
            self.r = redis.Redis(
                host=REDIS_HOST, 
                port=REDIS_PORT, 
                db=REDIS_DB, 
                decode_responses=True
            )
            self.r.ping()
            logger.info("✅ Paradex: Redis connecté.")
        except Exception as e:
            logger.critical(f"Redis Error: {e}")
            raise SystemExit(1)

    def on_open(self, ws):
        logger.info("🟢 Paradex WS Connected.")
        # Abonnement au flux global
        ws.send(json.dumps({"jsonrpc": "2.0", "method": "subscribe", "params": {"channel": "funding_data.ALL"}, "id": 1}))

    def on_message(self, ws, message):
        try:
            resp = json.loads(message)
            # Vérification structure
            if "params" in resp and "data" in resp["params"]:
                d = resp["params"]["data"]
                
                raw_market = d.get("market")
                raw_rate = d.get("funding_rate")
                
                if raw_market and raw_rate is not None:
                    # Normalisation
                    token = normalize_symbol(raw_market)
                    if not token: return # Token rejeté
                    
                    # Taux (Paradex donne un décimal instantané -> %)
                    rate_pct = float(raw_rate) * 100 / 8
                    
                    self.r.hset(token, EXCHANGE_NAME, str(rate_pct))
                    
        except Exception:
            pass

    def on_error(self, ws, error):
        logger.error(f"WS Error: {error}")

    def on_close(self, ws, a, b):
        logger.warning("Paradex WS Closed.")

    def run(self):
        logger.info("🚀 Paradex Live Started.")
        while True:
            try:
                ws = websocket.WebSocketApp(
                    WS_URL, 
                    on_open=self.on_open, 
                    on_message=self.on_message, 
                    on_error=self.on_error, 
                    on_close=self.on_close
                )
                ws.run_forever()
            except Exception as e:
                logger.error(f"Crash: {e}")
            

if __name__ == "__main__":
    ParadexLive().run()