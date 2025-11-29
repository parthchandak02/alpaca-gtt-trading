"""Price Broadcaster for WebSocket clients.

Integrates with background price monitoring to broadcast updates.
"""

import logging

from core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class PriceBroadcaster:
    """Broadcasts price updates to WebSocket subscribers."""

    @staticmethod
    async def broadcast_prices(
        prices: dict[str, float | None], is_market_open: bool = False
    ):
        """
        Broadcast price updates to WebSocket clients.

        Args:
            prices: Dict mapping symbol -> price
            is_market_open: Current market status
        """
        if not prices:
            return

        # Format prices for WebSocket message
        formatted_prices = {}
        from datetime import datetime

        timestamp = datetime.utcnow().isoformat()

        for symbol, price in prices.items():
            if price is not None:
                formatted_prices[symbol] = {
                    "price": price,
                    "timestamp": timestamp,
                    "is_market_open": is_market_open,
                }

        if formatted_prices:
            await ws_manager.broadcast_prices(formatted_prices)
            logger.debug(
                f"Broadcasted prices for {len(formatted_prices)} symbols to WebSocket clients"
            )
