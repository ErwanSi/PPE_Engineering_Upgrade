"""
Crypto Funding Rate Arbitrage Engine — FastAPI Backend
Main entry point with all API routes.
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.data_service import DataService
from schemas import StrategyConfig, BacktestRequest, BotCommand
from strategy.risk_analysis import RiskAnalyzer
from strategy.cost_model import CostModel
from strategy.signal_generator import SignalGenerator
from strategy.backtester import EventDrivenBacktester
from strategy.optimizer import StrategyOptimizer
from bot.supervisor import BotSupervisor

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Globals ---
data_service: DataService = None
bot_supervisor: BotSupervisor = None
ws_clients: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global data_service, bot_supervisor
    data_service = DataService()
    bot_supervisor = BotSupervisor()
    yield
    if bot_supervisor and bot_supervisor.is_running:
        await bot_supervisor.stop()


app = FastAPI(
    title="Funding Rate Arbitrage Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================
# MODELS
# ============================
# Models are now in schemas.py


# ============================
# LIVE DATA ENDPOINTS
# ============================
@app.get("/api/live")
async def get_live_data(search: str = "", min_exchanges: int = 2):
    """Get live funding rates from Redis."""
    try:
        rates = data_service.get_live_rates()
        results = []

        for token, exchanges in rates.items():
            if search and search.upper() not in token.upper():
                continue

            row = {"token": token, "exchanges": exchanges, "nb_exchanges": len(exchanges)}

            if len(exchanges) >= 2:
                sorted_rates = sorted(exchanges.items(), key=lambda x: x[1])
                best_long = sorted_rates[0]
                best_short = sorted_rates[-1]
                spread_h = best_short[1] - best_long[1]

                row["best_long"] = {"exchange": best_long[0], "rate": best_long[1]}
                row["best_short"] = {"exchange": best_short[0], "rate": best_short[1]}
                row["spread_hourly"] = spread_h
                row["apr"] = spread_h * 24 * 365
            else:
                row["spread_hourly"] = 0
                row["apr"] = 0

            if len(exchanges) >= min_exchanges:
                results.append(row)

        results.sort(key=lambda x: x.get("apr", 0), reverse=True)
        return {"data": results, "count": len(results), "timestamp": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# HISTORICAL DATA ENDPOINTS
# ============================
@app.get("/api/historical/tokens")
async def get_available_tokens():
    """List all tokens available in historical data."""
    try:
        tokens = data_service.get_available_tokens()
        return {"tokens": tokens}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/exchanges")
async def get_token_exchanges(token: str):
    """List exchanges available for a given token."""
    try:
        exchanges = data_service.get_token_exchanges(token)
        return {"token": token, "exchanges": exchanges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/funding")
async def get_funding_data(token: str, exchange: str):
    """Get historical funding rate data for a token/exchange pair."""
    try:
        df = data_service.get_funding_series(token, exchange)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        return {
            "data": df.reset_index().to_dict(orient="records"),
            "count": len(df)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/prices")
async def get_price_data(token: str, exchange: str):
    """Get historical price data for a token/exchange pair."""
    try:
        df = data_service.get_price_series(token, exchange)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        return {
            "data": df.reset_index().to_dict(orient="records"),
            "count": len(df)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/data-quality")
async def get_data_quality():
    """Get data quality metrics: density, coverage, listing dates."""
    try:
        quality = data_service.get_data_quality()
        return quality
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/scanner")
async def scan_opportunities():
    """Scan all pairs for best historical funding arbitrage opportunities."""
    try:
        results = data_service.scan_opportunities()
        return {"opportunities": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# STRATEGY / ANALYSIS ENDPOINTS
# ============================
@app.post("/api/strategy/analyze")
async def analyze_pair(request: BacktestRequest):
    """Run risk analysis (ADF, Cointeg, Hedge Ratio) on a pair."""
    try:
        p_long = data_service.get_price_series(request.token, request.long_exchange)
        p_short = data_service.get_price_series(request.token, request.short_exchange)

        if p_long is None or p_short is None:
            raise HTTPException(status_code=404, detail="Price data not found")

        analyzer = RiskAnalyzer()
        result = analyzer.full_analysis(p_long, p_short)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategy/backtest")
async def run_backtest(request: BacktestRequest):
    """Run event-driven backtest."""
    try:
        p_long = data_service.get_price_series(request.token, request.long_exchange)
        p_short = data_service.get_price_series(request.token, request.short_exchange)
        f_long = data_service.get_funding_series(request.token, request.long_exchange)
        f_short = data_service.get_funding_series(request.token, short_exchange := request.short_exchange) # Fix for scoping if needed

        if p_long is None or p_short is None:
            raise HTTPException(status_code=404, detail="Data not found")

        backtester = EventDrivenBacktester(request.config)
        result = backtester.run(p_long, p_short, f_long, f_short)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategy/optimize")
async def optimize_strategy(request: BacktestRequest):
    """Run parameter optimization (Grid Search) for a pair."""
    try:
        optimizer = StrategyOptimizer(data_service)
        results = optimizer.run_optimization(
            request.token, 
            request.long_exchange, 
            request.short_exchange,
            request.config
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategy/zscore")
async def get_live_zscore(token: str, long_exchange: str, short_exchange: str,
                          lookback: int = 168):
    """Compute current Z-Score for a pair using recent data."""
    try:
        f_long = data_service.get_funding_series(token, long_exchange)
        f_short = data_service.get_funding_series(token, short_exchange)

        if f_long is None or f_short is None:
            raise HTTPException(status_code=404, detail="Funding data not found")

        sig = SignalGenerator(lookback_hours=lookback)
        zscore_series = sig.compute_zscore(f_long, f_short)

        if zscore_series is None or zscore_series.empty:
            raise HTTPException(status_code=404, detail="Insufficient data for Z-Score")

        current = float(zscore_series.iloc[-1])
        signal = "LONG" if current < -2 else ("SHORT" if current > 2 else "NEUTRAL")

        return {
            "token": token,
            "pair": f"{long_exchange}/{short_exchange}",
            "zscore_current": current,
            "signal": signal,
            "zscore_history": zscore_series.tail(100).reset_index().to_dict(orient="records")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# BOT CONTROL ENDPOINTS
# ============================
@app.post("/api/bot/command")
async def bot_command(cmd: BotCommand):
    """Control the trading bot."""
    global bot_supervisor

    if cmd.action == "start":
        if bot_supervisor.is_running:
            return {"status": "already_running"}
        await bot_supervisor.start(cmd.config, cmd.pairs)
        return {"status": "started", "mode": os.getenv("BOT_MODE", "manual")}

    elif cmd.action == "stop":
        await bot_supervisor.stop()
        return {"status": "stopped"}

    elif cmd.action == "status":
        return bot_supervisor.get_status()

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {cmd.action}")


@app.get("/api/bot/positions")
async def get_positions():
    """Get current open positions."""
    return {"positions": bot_supervisor.get_positions()}


@app.get("/api/bot/logs")
async def get_bot_logs(limit: int = 100):
    """Get recent bot activity logs."""
    return {"logs": bot_supervisor.get_logs(limit)}


# ============================
# WEBSOCKET FOR REAL-TIME
# ============================
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket for real-time rate updates."""
    await websocket.accept()
    ws_clients.append(websocket)

    try:
        while True:
            rates = data_service.get_live_rates()
            await websocket.send_json({"type": "rates", "data": rates})
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        ws_clients.remove(websocket)


@app.websocket("/ws/bot")
async def websocket_bot(websocket: WebSocket):
    """WebSocket for bot status updates."""
    await websocket.accept()

    try:
        while True:
            status = bot_supervisor.get_status()
            await websocket.send_json({"type": "bot_status", "data": status})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True
    )
