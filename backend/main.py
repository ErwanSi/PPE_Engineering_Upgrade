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
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.data_service import DataService
from schemas import StrategyConfig, BacktestRequest, BotCommand, LoginRequest, CredentialsUpdate
from strategy.risk_analysis import RiskAnalyzer
from strategy.cost_model import CostModel
from strategy.signal_generator import SignalGenerator
from strategy.backtester import EventDrivenBacktester
from strategy.optimizer import StrategyOptimizer
from bot.supervisor import BotSupervisor
from bot.auth import verify_user, create_token, verify_token, save_credentials, get_credentials

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
# AUTH HELPERS
# ============================
def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract and verify user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # Support "Bearer <token>" format
    token = authorization.replace("Bearer ", "").strip()
    username = verify_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


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
        f_short = data_service.get_funding_series(request.token, request.short_exchange)
        
        if p_long is None or p_short is None:
            raise HTTPException(status_code=404, detail="Data not found")

        current_config = request.config
        if request.auto_tune:
            optimizer = StrategyOptimizer(data_service)
            best_cfg = optimizer.get_best_config(request.token, request.long_exchange, request.short_exchange, request.config)
            if best_cfg:
                current_config = best_cfg

        backtester = EventDrivenBacktester(current_config)
        result = backtester.run(p_long, p_short, f_long, f_short)
        
        # Add optimized params to result for UI feedback
        result["optimized_params"] = {
            "zscore_entry": current_config.zscore_entry,
            "zscore_exit": current_config.zscore_exit,
            "lookback_hours": current_config.lookback_hours
        }
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
        signal = "ENTER_NEG" if current < -2 else ("ENTER_POS" if current > 2 else "NEUTRAL")

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
# BOT PUBLIC STATUS (no auth needed for dashboard)
# ============================
@app.get("/api/bot/status")
async def bot_public_status():
    """Public bot status for dashboard — limited info, no auth required."""
    return {
        "is_running": bot_supervisor.is_running,
        "mode": getattr(bot_supervisor, 'bot_mode', 'manual'),
        "open_positions": len(bot_supervisor.open_positions),
    }


# ============================
# BOT AUTH ENDPOINTS
# ============================
@app.post("/api/bot/login")
async def bot_login(req: LoginRequest):
    """Authenticate to access bot features."""
    if verify_user(req.username, req.password):
        token = create_token(req.username)
        return {"token": token, "username": req.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/bot/credentials")
async def update_credentials(creds: CredentialsUpdate, user: str = Depends(get_current_user)):
    """Save API keys and wallet addresses."""
    data = {k: v for k, v in creds.dict().items() if v is not None}
    if save_credentials(user, data):
        return {"status": "saved", "message": "Credentials updated successfully"}
    raise HTTPException(status_code=500, detail="Failed to save credentials")


@app.get("/api/bot/credentials")
async def read_credentials(user: str = Depends(get_current_user)):
    """Get masked credentials for the current user."""
    creds = get_credentials(user)
    return {"credentials": creds or {}}


# ============================
# BOT CONTROL ENDPOINTS (Protected)
# ============================
@app.post("/api/bot/command")
async def bot_command(cmd: BotCommand, user: str = Depends(get_current_user)):
    """Control the trading bot. Requires authentication."""
    global bot_supervisor

    if cmd.action == "start":
        if bot_supervisor.is_running:
            return {"status": "already_running"}
        # Pass data_service for live signal computation
        bot_supervisor._data_service = data_service
        await bot_supervisor.start(cmd.config, cmd.pairs)
        return {"status": "started", "mode": bot_supervisor.bot_mode}

    elif cmd.action == "stop":
        await bot_supervisor.stop()
        return {"status": "stopped"}

    elif cmd.action == "status":
        return bot_supervisor.get_status()

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {cmd.action}")


@app.post("/api/bot/mode")
async def set_bot_mode(body: dict, user: str = Depends(get_current_user)):
    """Switch between manual and auto mode."""
    mode = body.get("mode", "manual")
    if mode not in ("manual", "auto"):
        raise HTTPException(status_code=400, detail="Mode must be 'manual' or 'auto'")
    bot_supervisor.set_mode(mode)
    return {"mode": mode}


@app.get("/api/bot/auto-pairs")
async def get_auto_pairs(user: str = Depends(get_current_user)):
    """Get top 3 pairs recommended for auto mode."""
    bot_supervisor._data_service = data_service
    pairs = bot_supervisor.get_auto_pairs()
    return {"pairs": pairs}


@app.get("/api/bot/positions")
async def get_positions(user: str = Depends(get_current_user)):
    """Get current open positions."""
    return {"positions": bot_supervisor.get_positions()}


@app.get("/api/bot/logs")
async def get_bot_logs(limit: int = 100, user: str = Depends(get_current_user)):
    """Get recent bot activity logs."""
    return {"logs": bot_supervisor.get_logs(limit)}


@app.get("/api/bot/history")
async def get_bot_history(user: str = Depends(get_current_user)):
    """Get historical bot performance summary."""
    return {
        "performance": bot_supervisor.get_performance_history(),
        "total_positions_closed": len(bot_supervisor.closed_positions),
        "is_running": bot_supervisor.is_running,
    }


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
            status["performance"] = bot_supervisor.get_performance_history()
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
