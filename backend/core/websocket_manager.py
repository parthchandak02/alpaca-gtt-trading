"""WebSocket Manager for real-time price updates.

Manages WebSocket connections and broadcasts price updates to subscribed clients.
"""

import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and price subscriptions."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.client_subscriptions: dict[
            str, set[str]
        ] = {}  # client_id -> set of symbols
        self.symbol_subscribers: dict[str, set[str]] = {}  # symbol -> set of client_ids
        self._lock = asyncio.Lock()
        logger.info("WebSocket Manager initialized")

    async def connect(self, websocket: WebSocket, client_id: str):
        """Register WebSocket connection (connection should already be accepted)."""
        async with self._lock:
            self.active_connections[client_id] = websocket
            self.client_subscriptions[client_id] = set()
            logger.info(
                f"WebSocket client connected: {client_id} (total: {len(self.active_connections)})"
            )

        # Send welcome message
        await self.send_to_client(
            client_id,
            {
                "type": "connected",
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def disconnect(self, client_id: str):
        """Remove client connection and cleanup subscriptions."""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]

            # Remove from symbol subscriptions
            if client_id in self.client_subscriptions:
                symbols = self.client_subscriptions[client_id].copy()
                for symbol in symbols:
                    await self._unsubscribe(client_id, symbol)
                del self.client_subscriptions[client_id]

            logger.info(
                f"WebSocket client disconnected: {client_id} (remaining: {len(self.active_connections)})"
            )

    async def subscribe(self, client_id: str, symbols: list[str]):
        """Subscribe client to price updates for symbols."""
        async with self._lock:
            if client_id not in self.client_subscriptions:
                self.client_subscriptions[client_id] = set()

            for symbol in symbols:
                symbol_upper = symbol.upper()
                self.client_subscriptions[client_id].add(symbol_upper)

                if symbol_upper not in self.symbol_subscribers:
                    self.symbol_subscribers[symbol_upper] = set()
                self.symbol_subscribers[symbol_upper].add(client_id)

            logger.info(
                f"Client {client_id} subscribed to: {symbols} (total subscriptions: {self.get_subscription_count()})"
            )

    async def _unsubscribe(self, client_id: str, symbol: str):
        """Unsubscribe client from symbol (internal, assumes lock held)."""
        symbol_upper = symbol.upper()

        if client_id in self.client_subscriptions:
            self.client_subscriptions[client_id].discard(symbol_upper)

        if symbol_upper in self.symbol_subscribers:
            self.symbol_subscribers[symbol_upper].discard(client_id)
            if not self.symbol_subscribers[symbol_upper]:
                del self.symbol_subscribers[symbol_upper]

    async def unsubscribe(self, client_id: str, symbols: list[str]):
        """Unsubscribe client from price updates for symbols."""
        async with self._lock:
            for symbol in symbols:
                await self._unsubscribe(client_id, symbol)
            logger.info(f"Client {client_id} unsubscribed from: {symbols}")

    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific client."""
        if client_id not in self.active_connections:
            return

        websocket = self.active_connections[client_id]
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.debug(
                f"Error sending to client {client_id}: {e} (client may have disconnected)"
            )
            # Don't log as error for normal disconnections
            # Only disconnect if it's a real error (not just client closed)
            try:
                await self.disconnect(client_id)
            except Exception:
                pass  # Already disconnected

    async def broadcast_prices(self, prices: dict[str, dict]):
        """Broadcast price updates to subscribed clients."""
        if not prices:
            return

        # Group prices by client
        client_updates: dict[str, dict[str, dict]] = {}

        async with self._lock:
            for symbol, price_data in prices.items():
                symbol_upper = symbol.upper()
                if symbol_upper in self.symbol_subscribers:
                    for client_id in self.symbol_subscribers[symbol_upper]:
                        if client_id not in client_updates:
                            client_updates[client_id] = {}
                        client_updates[client_id][symbol_upper] = price_data

        # Send updates to each client
        for client_id, client_prices in client_updates.items():
            await self.send_to_client(
                client_id,
                {
                    "type": "price_update",
                    "data": client_prices,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        if client_updates:
            logger.debug(
                f"Broadcasted prices to {len(client_updates)} client(s) for {len(prices)} symbol(s)"
            )

    async def send_heartbeat(self, client_id: str):
        """Send heartbeat to keep connection alive."""
        await self.send_to_client(
            client_id, {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
        )

    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)

    def get_subscription_count(self) -> int:
        """Get total number of symbol subscriptions."""
        return sum(len(symbols) for symbols in self.client_subscriptions.values())


# Global WebSocket manager instance
ws_manager = WebSocketManager()
