# 🏛 Architecture Détaillée du Projet : Crypto Funding Rate Arbitrage Engine

Ce document présente une exploration complète, couche par couche et code par code, de l'architecture du projet d'arbitrage de taux de financement crypto (Funding Rate Arbitrage Engine).

## 1. Vue d'Ensemble du Flux de Données et Composants

L'application repose sur un trio technologique : **Next.js (Frontend)**, **FastAPI (Backend)**, et **Redis (Base de données en mémoire pour le Live)**. Les données historiques sont quant à elles stockées dans des fichiers optimisés **Parquet**.

Le flux se sépare en deux temps :
1. **Temps Réel (Live)** : Les scripts "collectors" publient constament toutes les X secondes sur Redis. FastAPI les lit et les sert au Frontend via API REST et WebSockets.
2. **Historique (Backtest)** : Les extracteurs récupèrent les données sur 6 mois, les alignent et les stockent sous format Parquet. Le Backend utilise la librairie Pandas pour faire des statistiques dessus (ADF, Cointégration) afin d'optimiser la stratégie.

---

## 2. Le Backend (FastAPI) -- Dossier `backend/`

Le Backend agit en tant que chef d'orchestre. C'est ici que réside la véritable **intelligence** du moteur de trading.

### 2.1 Le Point d'Entrée : `main.py`
Fichier : `backend/main.py`
C'est le routeur principal. Il initialise l'application avec un cycle de vie `lifespan` qui démarre/arrête le `BotSupervisor`.
- **Routes Live** : `/api/live` lit directement le cache Redis via `DataService` et calcule instantanément le "Spread" (meilleur short vs meilleur long) et l'APR annualisé.
- **Routes Historiques** : `/api/historical/*` fournit les graphes de prix et de funding au frontend.
- **Routes Stratégie** : Appellent le moteur quantitatif (analyse de stationnarité, backtest, optimisation par Grid Search).
- **Routes Bot** : `/api/bot/command`, `/api/bot/status` gèrent le contrôle du bot métier. Ce contrôle est restreint par un JWT.
- **WebSockets** : `/ws/live` et `/ws/bot` envoient respectivement les taux de financement en direct ainsi que le statut en temps réel au dashboard sans que le client ait besoin de rafraîchir.

### 2.2 Accès aux Données : `services/data_service.py`
Expose une abstraction unifiée pour `main.py` et le moteur pour obtenir les données :
- Gère la connexion avec *Redis* pour retransmette les dictionnaires de flux des Data Collectors.
- Gère la lecture des fichiers *Pandas DataFrame* depuis les fichiers parquet générés pour fournir la Time Series nécessaire aux backtests.

### 2.3 Le Cerveau Statistique : `strategy/`
Ce dossier contient la stratégie "Event-Driven" de notre système d'arbitrage (delta-neutre) :
- `risk_analysis.py` : (Phase 1) Met en oeuvre les tests purement quantiques comme l'**ADF** (Augmented Dickey-Fuller) ou **Engle-Granger**. Le but est de s'assurer de la stationnarité d'un spread et d'éliminer les faux signaux (Risk filtering).
- `cost_model.py` : (Phase 2) Applique de manière réaliste les contraintes du marché réel : Taker Fees, Maker Fees, Slippage induit par l'Orderbook, Gas fees du réseau Starknet.
- `signal_generator.py` : (Phase 3) Génère un **Z-Score rolling** sur les taux de funding. Si le Z-Score franchit un seuil critique (ex: > 2.0), un signal d'entrée `ENTER_POS` / `ENTER_NEG` est généré, signalant que le funding va très probablement régreser vers sa moyenne de manière profitable. Si `< 0.5`, le système décide d'une sortie (`EXIT`).
- `rebalancer.py` : (Phase 4) Est sollicité en continu afin de s'assurer de la neutralité "delta". Puisque nous avons un LONG sur A, et un SHORT sur B, si les prix bougent violemment, le système se déséquilibre. Le rebalancer gère les ajustements en volume.
- `backtester.py` & `optimizer.py` : (Phase 5) Simulent le comportement historique (en repassant bougie par bougie les données passées avec slippage inclus). `optimizer.py` itère des combinaisons pour un ajustement automatique des variables optimales (Grid Searching Loop).

### 2.4 Le Bot d'Exécution : `bot/`
Ce dossier interagit litéralement sur les Marchés (via CCXT ou APIs natives DEX).
- `supervisor.py` : C'est la boucle infinie de la machine à état (State Machine). Il évalue via `signal_generator` l'état (Z-Score) d'une paire suivie pour décider d'ouvrir ou de clôturer des positions (via `executor.py`). Il possède un mode **manual** (l'utilisateur choisit les paires) et un mode **auto** (il scannera les pires live data pour piocher le top APR en temps réel).
- `executor.py` : Traduit les ordres abstraits de `supervisor` en vraies requêtes Post API. Gère la parallélisation d'un trade (entrer Short et Long en même temps pour éviter un écart temporel de Delta de Prix).
- `auth.py` : Sécurisation de l'accès à ce package, chiffrage des API Keys des exchanges.

---

## 3. Le Frontend (Next.js) -- Dossier `frontend/`

Application construite en Single Page App avec App Router Next.js, interrogeant continuellement le Backend via API (REST et WS).

### 3.1 Architecture du code Frontend (`src/app/`)
- `page.tsx` (Dashboard) : Affiche l'historique et les résumés très denses pour la prise de décision, en invoquant les routes globales FastAPI backend.
- `live/page.tsx` : Matrice avec connexion WebSocket affichant l'état des orderbooks et spreads entre Binance / Hyperliquid / Paradex / Extended toutes les 15 secondes max.
- `strategy/page.tsx` : Interface graphique du "Labo Stratégie". Sorte de Terminal Bloomberg allégé permettant à un Quant / Trader de lancer les `backtester.py` et jouer manuellement sur l'impact de SMA, Z-Score, fees, etc...
- `bot/page.tsx` & `bot-portfolio/` : Panel de contrôle (Authentifié) avec courbes d'équités rafraîchies en Live qui affiche ce que fait le processus Python natif (`supervisor.py`) en tâche de fond.

---

## 4. Pipeline de Data (Data Collectors) -- Dossier `data_collectors/`

Le sang de l'application : l'ingestion brute depuis les L1 / L2 / CEX.

### 4.1 Collecte Historical (`data_collectors/historical/`)
Contient par exemple `binance_funding.py` ou `hyperliquid_prices.py`. Ces scripts sont complexes car contraints aux Rate Limits :
- Implémentent du Rate Limiting (Token Buckets, Semaphores Asynchrone) pour extraire jusqu'à 6 mois d'historique 1h/5m.
- Implémentent une pagination par curseur par API.

### 4.2 L'ETL des données (`data_collectors/pipeline/`)
- `cleaner.py` : Ce script normalisateur est fondamental. Puisque Binance donne des Funding Rates chaque 8H mais Paradex tous les 1H, qu'il existe des bougies orphelines, etc... `cleaner.py` s'assure d'aligner la temporalité (Time Indexation commune) et de stocker les colonnes dans un contrat de structure clair `(datetime, market, value)` exporté de manière optimisée sous Parquets.

### 4.3 Streaming Live (`data_collectors/live/`)
- `*_live.py` scripts se déclenchent de manière isolée et tournent en "Cron Job" continu comme Daemons.
- Ils interrogent (via WebSockets pour Paradex, Polling REST strict pour Binance) la valeur immédiate du funding à cet instant T afin de pousser cette mise à jour avec `redis.set(token_name, rate)`.

---

## Conclusions

Ce projet est une pile robuste de "Quantitative Engineering".
- **Robuste aux données** grâce aux data pipelines et Redis.
- **Réactif aux marchés** grâce à l'architecture Event-Driven FastAPI vs WebSockets Next.js.
- **Asynchrone et modulaire** avec la stricte séparation (Stratégie pure / Exécution CCXT / Statistiques ADF / UI Client).
