"""
Bot Executor — Places orders on exchanges via CCXT.
Supports manual mode (signal only) and auto mode (execution).
"""
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExchangeConnector:
    """
    Unified exchange connector using CCXT.
    Handles order placement, position queries, and balance management.
    """

    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.exchange = None
        self._initialize()

    def _initialize(self):
        try:
            import ccxt
            config = {
                'apiKey': os.getenv(f"{self.exchange_name.upper()}_API_KEY", ""),
                'secret': os.getenv(f"{self.exchange_name.upper()}_API_SECRET", ""),
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            }

            exchange_map = {
                "binance": ccxt.binance,
                "hyperliquid": ccxt.hyperliquid if hasattr(ccxt, 'hyperliquid') else None,
            }

            exchange_cls = exchange_map.get(self.exchange_name)
            if exchange_cls:
                self.exchange = exchange_cls(config)
                logger.info(f"Connected to {self.exchange_name}")
            else:
                logger.warning(f"Exchange {self.exchange_name} not supported via CCXT, using REST fallback")

        except Exception as e:
            logger.error(f"Failed to initialize {self.exchange_name}: {e}")

    def is_connected(self) -> bool:
        return self.exchange is not None and bool(
            self.exchange.apiKey if self.exchange else False
        )

    async def get_balance(self) -> Dict[str, float]:
        if not self.exchange:
            return {}
        try:
            balance = self.exchange.fetch_balance()
            return {
                "total_usd": float(balance.get("total", {}).get("USDT", 0)),
                "free_usd": float(balance.get("free", {}).get("USDT", 0)),
                "used_usd": float(balance.get("used", {}).get("USDT", 0)),
            }
        except Exception as e:
            logger.error(f"Balance fetch error on {self.exchange_name}: {e}")
            return {}

    async def get_positions(self) -> List[Dict]:
        if not self.exchange:
            return []
        try:
            positions = self.exchange.fetch_positions()
            return [
                {
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "size": float(p["contracts"]),
                    "notional": float(p.get("notional", 0)),
                    "pnl": float(p.get("unrealizedPnl", 0)),
                    "leverage": float(p.get("leverage", 1)),
                    "margin": float(p.get("initialMargin", 0)),
                    "liquidation_price": float(p.get("liquidationPrice", 0)),
                }
                for p in positions
                if float(p.get("contracts", 0)) > 0
            ]
        except Exception as e:
            logger.error(f"Position fetch error on {self.exchange_name}: {e}")
            return []

    async def place_order(self, symbol: str, side: str, amount_usd: float,
                          order_type: str = "market") -> Optional[Dict]:
        """
        Place an order. Side: 'buy' or 'sell'.
        amount_usd is converted to contract size using current price.
        """
        if not self.exchange:
            return {"error": "Exchange not connected"}

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            quantity = amount_usd / current_price

            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=quantity
            )

            logger.info(f"Order placed on {self.exchange_name}: {side} {quantity:.6f} {symbol}")

            return {
                "id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "amount": quantity,
                "price": current_price,
                "status": order.get("status"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Order error on {self.exchange_name}: {e}")
            return {"error": str(e)}

    async def close_position(self, symbol: str) -> Optional[Dict]:
        """Close an existing position by placing an opposite order."""
        if not self.exchange:
            return {"error": "Exchange not connected"}

        try:
            positions = await self.get_positions()
            for pos in positions:
                if pos["symbol"] == symbol and pos["size"] > 0:
                    close_side = "sell" if pos["side"] == "long" else "buy"
                    return await self.place_order(symbol, close_side, pos["notional"])

            return {"status": "no_position_found"}

        except Exception as e:
            return {"error": str(e)}


class Executor:
    """
    High-level executor that manages pairs of exchanges for arbitrage.
    """

    def __init__(self):
        self.connectors: Dict[str, ExchangeConnector] = {}
        self.order_history: List[Dict] = []

    def get_connector(self, exchange: str) -> ExchangeConnector:
        if exchange not in self.connectors:
            self.connectors[exchange] = ExchangeConnector(exchange)
        return self.connectors[exchange]

    async def open_arbitrage(self, token: str, long_exchange: str, short_exchange: str,
                              size_usd: float) -> Dict[str, Any]:
        """
        Open an arbitrage position:
        - BUY (long) on long_exchange
        - SELL (short) on short_exchange
        """
        symbol = f"{token}/USDT"

        long_conn = self.get_connector(long_exchange)
        short_conn = self.get_connector(short_exchange)

        long_order = await long_conn.place_order(symbol, "buy", size_usd)
        short_order = await short_conn.place_order(symbol, "sell", size_usd)

        result = {
            "action": "open_arbitrage",
            "token": token,
            "long": {"exchange": long_exchange, "order": long_order},
            "short": {"exchange": short_exchange, "order": short_order},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.order_history.append(result)
        return result

    async def close_arbitrage(self, token: str, long_exchange: str, short_exchange: str) -> Dict[str, Any]:
        """Close both legs of an arbitrage position."""
        symbol = f"{token}/USDT"

        long_conn = self.get_connector(long_exchange)
        short_conn = self.get_connector(short_exchange)

        long_close = await long_conn.close_position(symbol)
        short_close = await short_conn.close_position(symbol)

        result = {
            "action": "close_arbitrage",
            "token": token,
            "long_close": long_close,
            "short_close": short_close,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.order_history.append(result)
        return result

    async def get_all_balances(self) -> Dict[str, Dict]:
        result = {}
        for name, conn in self.connectors.items():
            result[name] = await conn.get_balance()
        return result

    async def get_all_positions(self) -> Dict[str, List]:
        result = {}
        for name, conn in self.connectors.items():
            result[name] = await conn.get_positions()
        return result
