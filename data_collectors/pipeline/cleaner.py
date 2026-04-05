import logging
import os
import glob
import re
from dataclasses import dataclass
from typing import Tuple, List
import numpy as np
import pandas as pd

# --- CONFIGURATION ---
@dataclass(frozen=True)
class Config:
    # Dossiers d'entrée (relatifs à la racine du projet)
    PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
    DIR_PRICES = [
        os.path.join(PROJECT_ROOT, "data", "raw", "binance_prices_5m_sync"), 
        os.path.join(PROJECT_ROOT, "data", "raw", "hyperliquid_prices_5m_sync"),
        os.path.join(PROJECT_ROOT, "data", "raw", "paradex_prices_5m_sync"), 
        os.path.join(PROJECT_ROOT, "data", "raw", "extended_prices_5m_sync")
    ]
    
    DIR_FUNDING = [
        os.path.join(PROJECT_ROOT, "data", "raw", "binance_funding_data"), 
        os.path.join(PROJECT_ROOT, "data", "raw", "hyperliquid_funding_data"),
        os.path.join(PROJECT_ROOT, "data", "raw", "paradex_funding_data"), 
        os.path.join(PROJECT_ROOT, "data", "raw", "extended_funding_data")
    ]
    
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")

    # --- FILTRES ---
    MAX_MISSING_PCT: float = 0.20 
    MIN_EXCHANGES_FOR_ARB: int = 2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class DataPipelinePro:
    def __init__(self):
        if not os.path.exists(Config.OUTPUT_DIR): 
            os.makedirs(Config.OUTPUT_DIR)

    def _detect_exchange(self, filename: str) -> str:
        u = filename.upper()
        if "BINANCE" in u: return "binance"
        if "HYPERLIQUID" in u: return "hyperliquid"
        if "PARADEX" in u: return "paradex"
        if "EXTENDED" in u: return "extended"
        return "unknown"

    def _clean_token_name(self, filename: str) -> str:
        """
        Normalisateur Universel.
        Gère BTC-USD-PERP -> BTC et 1000PEPE -> PEPE.
        """
        name = os.path.basename(filename).replace(".parquet", "")
        for prefix in ["BINANCE_", "HYPERLIQUID_", "PARADEX_", "EXTENDED_"]:
            name = name.replace(prefix, "")
        
        s = name.upper()

        # 1. FILTRE ANTI-OPTIONS
        if re.search(r'-\d{2,}', s) or re.search(r'-\d+C$', s) or re.search(r'-\d+P$', s):
            return "IGNORE_OPTION"
        if '_' in s and any(c.isdigit() for c in s): return "IGNORE_OPTION"

        # 2. NETTOYAGE (Double Peeling)
        if s.endswith("-PERP"): s = s[:-5]
        elif s.endswith("_PERP"): s = s[:-5]
        elif s.endswith("PERP"): s = s[:-4]

        for quote in ["-USD", "/USD", "USDT", "USDC", "BUSD", "USD"]:
            if s.endswith(quote):
                s = s[:-len(quote)]
                break

        if s.startswith("1000") and len(s) > 4 and s[4:].isalpha(): s = s[4:]
        elif s.startswith("100") and len(s) > 3 and s[3:].isalpha(): s = s[3:]
        elif s.startswith("K") and s[1:] in ["SHIB", "BONK", "LUNC", "PEPE"]: s = s[1:]
        elif s.startswith("M") and s[1:] in ["MOG", "PEPE"]: s = s[1:]
        elif s.startswith("1M") and len(s) > 2: s = s[2:]

        return s.replace("-", "").replace("_", "")

    def load_data(self, folders: List[str], val_col: str, time_unit: str) -> pd.DataFrame:
        """Charge, normalise et prépare les DataFrames."""
        logger.info(f"Chargement des données : {val_col} ({time_unit})...")
        dfs = []
        files = []
        
        for d in folders:
            if os.path.exists(d): 
                raw_files = glob.glob(os.path.join(d, "*.parquet"))
                # On exclut les fichiers 1m de Paradex
                files.extend([x for x in raw_files if "_1m" not in x])

        for f in files:
            try:
                token = self._clean_token_name(f)
                if token == "IGNORE_OPTION": continue
                exchange = self._detect_exchange(f)
                
                df = pd.read_parquet(f)
                
                # Mapping colonnes
                cols_map = {
                    'close_price': 'val', 'markPrice': 'val', 'Close': 'val', 'c': 'val', 'price': 'val',
                    'fundingRate': 'val', 'funding_rate': 'val'
                }
                df = df.rename(columns=cols_map)
                
                if 'val' not in df.columns: continue
                
                # Gestion Temps
                if 'timestamp_ms' in df.columns:
                    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
                elif 'datetime' not in df.columns:
                    continue

                # --- CORRECTION DES TAUX (Funding Only) ---
                if 'funding' in val_col.lower():
                    if exchange == 'binance':
                        df = df.sort_values('datetime')
                        if len(df) > 5:
                            # Détection dynamique 4h vs 8h
                            df['diff_hours'] = df['datetime'].diff().dt.total_seconds() / 3600
                            is_4h = (df['diff_hours'] >= 3.5) & (df['diff_hours'] <= 4.5)
                            divisors = np.where(is_4h, 4.0, 8.0)
                            df['val'] = df['val'] / divisors
                        else:
                            df['val'] = df['val'] / 8.0
                    
                    elif exchange == 'paradex':
                        # Paradex est en base 8h, on veut du 1h
                        df['val'] = df['val'] / 8.0

                # Snapping Temporel (Arrondi)
                if time_unit == '5min': 
                    df['datetime'] = df['datetime'].dt.floor('5min')
                else: 
                    df['datetime'] = df['datetime'].dt.floor('h')
                
                # Formatage strict
                df = df[['datetime', 'val']].copy()
                df['exchange'] = exchange
                df['token'] = token
                df['val'] = df['val'].astype('float32')
                
                # Dédoublonnage local (au cas où le fichier source ait des doublons)
                df = df.drop_duplicates(subset=['datetime'])
                
                dfs.append(df)
            except Exception:
                continue
            
        if not dfs: return pd.DataFrame()
        
        # Fusion verticale de tous les petits bouts
        return pd.concat(dfs, ignore_index=True)

    def generate_matrices(self, df: pd.DataFrame, freq: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        logger.info("Pivot et génération des matrices...")
        
        # 1. PIVOT AVEC ALIGNEMENT STRICT
        # C'est ici que la magie opère. pivot_table force l'alignement des dates.
        pivot = df.pivot_table(index='datetime', columns=['token', 'exchange'], values='val')
        
        # 2. RÉÉCHANTILLONNAGE
        # On remplit les trous temporels légers (ex: une minute manquante)
        pivot = pivot.resample(freq).asfreq()
        
        # --- MATRICE 1 : ALL (Données brutes alignées) ---
        # On ne fait PAS de ffill() infini ici. Juste localement (limit=3) pour boucher les micros-trous.
        # Si Hyperliquid s'arrête en septembre, il restera NaN en novembre.
        matrix_all = pivot.ffill(limit=3) 
        
        # --- MATRICE 2 : STRICT (Intersection Propre) ---
        # On ne garde que les lignes où il y a assez de données
        # On rejette les colonnes (Tokens) qui sont vides à plus de 20%
        missing_pct = pivot.isna().mean()
        to_drop = missing_pct[missing_pct > Config.MAX_MISSING_PCT]
        matrix_strict = pivot.drop(columns=to_drop.index)
        
        # IMPORTANT : On coupe les dates où tout le monde n'est pas là
        matrix_strict = matrix_strict.dropna(how='all') 
        
        # --- MATRICE 3 : ARBITRAGE (Sélection) ---
        base_matrix_arb = matrix_strict 
        
        # On ne garde que les tokens présents sur au moins 2 exchanges
        all_tokens = base_matrix_arb.columns.get_level_values('token')
        token_counts = all_tokens.value_counts()
        valid_arb_tokens = token_counts[token_counts >= Config.MIN_EXCHANGES_FOR_ARB].index
        
        matrix_arb = base_matrix_arb.loc[:, base_matrix_arb.columns.get_level_values('token').isin(valid_arb_tokens)]

        return matrix_all, matrix_strict, matrix_arb

    def run(self):
        # 1. PRIX
        df_p = self.load_data(Config.DIR_PRICES, 'price', '5min')
        if not df_p.empty:
            p_all, p_strict, p_arb = self.generate_matrices(df_p, '5min')
            
            # Sauvegarde propre avec index DateTime explicite
            p_all.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_PRICES_5M_ALL.parquet"))
            p_strict.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_PRICES_5M_STRICT.parquet"))
            p_arb.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_PRICES_5M_ARBITRAGE.parquet"))
            
            # Export CSV de debug (facultatif mais utile pour vérif manuelle)
            # p_arb.tail(100).to_csv(os.path.join(Config.OUTPUT_DIR, "DEBUG_LAST_PRICES.csv"))
            
            logger.info(f"✅ PRIX : {p_arb.shape[1]} paires alignées.")

        # 2. FUNDING
        df_f = self.load_data(Config.DIR_FUNDING, 'fundingRate', 'h')
        if not df_f.empty:
            f_all, f_strict, f_arb = self.generate_matrices(df_f, '1h')
            
            f_all.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_FUNDING_1H_ALL.parquet"))
            f_strict.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_FUNDING_1H_STRICT.parquet"))
            f_arb.to_parquet(os.path.join(Config.OUTPUT_DIR, "MASTER_FUNDING_1H_ARBITRAGE.parquet"))
            
            logger.info(f"✅ FUNDING : {f_arb.shape[1]} paires alignées.")

if __name__ == "__main__":
    DataPipelinePro().run()