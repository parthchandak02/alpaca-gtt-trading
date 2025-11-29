"""Alpaca WebSocket client for real-time market data and trade updates.

This module provides reliable WebSocket connections to Alpaca's streaming APIs:
- Market data streams (bars, trades, quotes) for live prices
- Trade updates stream for order status notifications

Features:
- Automatic reconnection with exponential backoff
- Dynamic symbol subscriptions
- Handles both stocks and crypto
- Updates PriceCache database
- Broadcasts to frontend WebSocket clients
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from alpaca.data.enums import DataFeed
from alpaca.data.live import CryptoDataStream, StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca_client import is_crypto_symbol, normalize_crypto_symbol
from config import settings
from core.gtt_order_status_service import GTTOrderStatusService
from core.price_broadcaster import PriceBroadcaster
from core.price_cache_service import PriceCacheService
from database import SessionLocal
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


class AlpacaWebSocketClient:
    """Manages WebSocket connections to Alpaca streaming APIs."""

    def __init__(self):
        """Initialize WebSocket clients for Alpaca streams."""
        self.stock_stream: StockDataStream | None = None
        self.crypto_stream: CryptoDataStream | None = None
        self.trade_updates_stream: TradingStream | None = None

        # Track subscriptions
        self.subscribed_stocks: set[str] = set()
        self.subscribed_crypto: set[str] = set()

        # Connection state
        self._is_connected_stocks = False
        self._is_connected_crypto = False
        self._is_connected_trade_updates = False

        # Reconnection settings
        self._reconnect_delay = 1.0  # Start with 1 second
        self._max_reconnect_delay = 60.0  # Max 60 seconds
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10

        # Tasks
        self._stock_task: asyncio.Task | None = None
        self._crypto_task: asyncio.Task | None = None
        self._trade_updates_task: asyncio.Task | None = None
        self._async_processor_task: asyncio.Task | None = None

        # Async queue for processing updates from sync handlers
        # Queue size limit prevents memory issues if processing falls behind
        self._async_queue: asyncio.Queue | None = None
        self._async_queue_maxsize = 1000  # Max 1000 queued updates

        # Callbacks
        self._on_order_update_callback: Callable | None = None

        logger.info("AlpacaWebSocketClient initialized")

    async def start(self):
        """Start all WebSocket connections."""
        logger.info("Starting Alpaca WebSocket connections...")

        # Create async queue for processing updates from sync handlers
        # Thread-safe queue allows sync handlers to schedule async work
        self._async_queue = asyncio.Queue(maxsize=self._async_queue_maxsize)

        # Start async processor task
        self._async_processor_task = asyncio.create_task(self._process_async_queue())

        # Start stock data stream
        self._stock_task = asyncio.create_task(self._run_stock_stream())

        # Start crypto data stream
        self._crypto_task = asyncio.create_task(self._run_crypto_stream())

        # Start trade updates stream
        self._trade_updates_task = asyncio.create_task(self._run_trade_updates_stream())

        logger.info("All WebSocket streams started")

    async def stop(self):
        """Stop all WebSocket connections."""
        logger.info("Stopping Alpaca WebSocket connections...")

        # Cancel tasks
        for task in [
            self._stock_task,
            self._crypto_task,
            self._trade_updates_task,
            self._async_processor_task,
        ]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Signal queue shutdown
        if self._async_queue:
            await self._async_queue.put(None)  # Sentinel value

        # Close streams (stop() method stops the stream)
        if self.stock_stream:
            try:
                self.stock_stream.stop()
            except Exception as e:
                logger.error(f"Error stopping stock stream: {e}")

        if self.crypto_stream:
            try:
                self.crypto_stream.stop()
            except Exception as e:
                logger.error(f"Error stopping crypto stream: {e}")

        if self.trade_updates_stream:
            try:
                self.trade_updates_stream.stop()
            except Exception as e:
                logger.error(f"Error stopping trade updates stream: {e}")

        logger.info("All WebSocket streams stopped")

    async def subscribe_symbols(self, symbols: list[str]):
        """Subscribe to price updates for symbols.

        Automatically routes to stock or crypto stream based on symbol type.
        """
        if not symbols:
            return

        stock_symbols = []
        crypto_symbols = []

        for symbol in symbols:
            symbol_upper = symbol.upper()
            # Normalize crypto symbols
            if is_crypto_symbol(symbol_upper):
                normalized = normalize_crypto_symbol(symbol_upper)
                if normalized not in self.subscribed_crypto:
                    crypto_symbols.append(normalized)
            else:
                if symbol_upper not in self.subscribed_stocks:
                    stock_symbols.append(symbol_upper)

        # Subscribe to stock symbols
        if stock_symbols and self.stock_stream:
            try:
                # Subscribe with handler function
                for symbol in stock_symbols:
                    self.stock_stream.subscribe_bars(self._on_stock_bar_update, symbol)
                self.subscribed_stocks.update(stock_symbols)
                logger.info(f"Subscribed to stock symbols: {stock_symbols}")
            except Exception as e:
                logger.error(f"Error subscribing to stock symbols {stock_symbols}: {e}")

        # Subscribe to crypto symbols
        if crypto_symbols and self.crypto_stream:
            try:
                # Subscribe with handler function
                for symbol in crypto_symbols:
                    self.crypto_stream.subscribe_bars(
                        self._on_crypto_bar_update, symbol
                    )
                self.subscribed_crypto.update(crypto_symbols)
                logger.info(f"Subscribed to crypto symbols: {crypto_symbols}")
            except Exception as e:
                logger.error(
                    f"Error subscribing to crypto symbols {crypto_symbols}: {e}"
                )

    async def unsubscribe_symbols(self, symbols: list[str]):
        """Unsubscribe from price updates for symbols."""
        if not symbols:
            return

        stock_symbols = []
        crypto_symbols = []

        for symbol in symbols:
            symbol_upper = symbol.upper()
            if is_crypto_symbol(symbol_upper):
                normalized = normalize_crypto_symbol(symbol_upper)
                if normalized in self.subscribed_crypto:
                    crypto_symbols.append(normalized)
            else:
                if symbol_upper in self.subscribed_stocks:
                    stock_symbols.append(symbol_upper)

        # Unsubscribe from stock symbols
        if stock_symbols and self.stock_stream and self._is_connected_stocks:
            try:
                self.stock_stream.unsubscribe_bars(stock_symbols)
                self.subscribed_stocks.difference_update(stock_symbols)
                logger.info(f"Unsubscribed from stock symbols: {stock_symbols}")
            except Exception as e:
                logger.error(
                    f"Error unsubscribing from stock symbols {stock_symbols}: {e}"
                )

        # Unsubscribe from crypto symbols
        if crypto_symbols and self.crypto_stream and self._is_connected_crypto:
            try:
                self.crypto_stream.unsubscribe_bars(crypto_symbols)
                self.subscribed_crypto.difference_update(crypto_symbols)
                logger.info(f"Unsubscribed from crypto symbols: {crypto_symbols}")
            except Exception as e:
                logger.error(
                    f"Error unsubscribing from crypto symbols {crypto_symbols}: {e}"
                )

    def set_order_update_callback(self, callback: Callable):
        """Set callback for order update events."""
        self._on_order_update_callback = callback

    async def _run_stock_stream(self):
        """Run stock data stream with reconnection logic."""
        while True:
            try:
                logger.info("Connecting to Alpaca stock data stream...")

                # Create stream client
                self.stock_stream = StockDataStream(
                    api_key=settings.alpaca_api_key,
                    secret_key=settings.alpaca_secret_key,
                    feed=DataFeed.IEX,  # Use DataFeed.IEX for free tier, DataFeed.SIP for premium
                )

                # Set up handlers - subscribe to bars
                # Note: subscribe_bars takes handler and symbol(s)
                if self.subscribed_stocks:
                    for symbol in self.subscribed_stocks:
                        self.stock_stream.subscribe_bars(
                            self._on_stock_bar_update, symbol
                        )
                else:
                    # Subscribe with handler only (will need to add symbols later)
                    pass

                # Run the stream (blocking call - run in thread pool)
                await run_in_threadpool(self.stock_stream.run)

                self._is_connected_stocks = True
                self._reconnect_attempts = 0
                self._reconnect_delay = 1.0

                logger.info("Stock data stream connected")

            except asyncio.CancelledError:
                logger.info("Stock data stream cancelled")
                break
            except Exception as e:
                self._is_connected_stocks = False
                logger.error(f"Stock data stream error: {e}", exc_info=True)

                # Exponential backoff reconnection
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    self._reconnect_attempts += 1
                    delay = min(
                        self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                        self._max_reconnect_delay,
                    )
                    logger.info(
                        f"Reconnecting stock stream in {delay:.1f}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max reconnection attempts reached for stock stream")
                    await asyncio.sleep(self._max_reconnect_delay)

    async def _run_crypto_stream(self):
        """Run crypto data stream with reconnection logic."""
        while True:
            try:
                logger.info("Connecting to Alpaca crypto data stream...")

                # Create stream client
                self.crypto_stream = CryptoDataStream(
                    api_key=settings.alpaca_api_key,
                    secret_key=settings.alpaca_secret_key,
                )

                # Set up handlers - subscribe to bars
                # Note: subscribe_bars takes handler and symbol(s)
                if self.subscribed_crypto:
                    for symbol in self.subscribed_crypto:
                        self.crypto_stream.subscribe_bars(
                            self._on_crypto_bar_update, symbol
                        )
                else:
                    # Subscribe with handler only (will need to add symbols later)
                    pass

                # Run the stream (blocking call - run in thread pool)
                await run_in_threadpool(self.crypto_stream.run)

                self._is_connected_crypto = True
                logger.info("Crypto data stream connected")

            except asyncio.CancelledError:
                logger.info("Crypto data stream cancelled")
                break
            except Exception as e:
                self._is_connected_crypto = False
                logger.error(f"Crypto data stream error: {e}", exc_info=True)

                # Exponential backoff reconnection
                delay = min(
                    self._reconnect_delay * (2**self._reconnect_attempts),
                    self._max_reconnect_delay,
                )
                logger.info(f"Reconnecting crypto stream in {delay:.1f}s")
                await asyncio.sleep(delay)

    async def _run_trade_updates_stream(self):
        """Run trade updates stream with reconnection logic."""
        while True:
            try:
                logger.info("Connecting to Alpaca trade updates stream...")

                # Create stream client
                from alpaca.trading.client import TradingClient

                trading_client = TradingClient(
                    api_key=settings.alpaca_api_key,
                    secret_key=settings.alpaca_secret_key,
                    paper=settings.use_paper_trading,
                )

                self.trade_updates_stream = TradingStream(
                    api_key=settings.alpaca_api_key,
                    secret_key=settings.alpaca_secret_key,
                    paper=settings.use_paper_trading,
                )

                # Set up handlers - subscribe to trade updates
                # TradingStream uses subscribe_trade_updates method
                self.trade_updates_stream.subscribe_trade_updates(self._on_trade_update)

                # Run the stream (blocking call - run in thread pool)
                await run_in_threadpool(self.trade_updates_stream.run)

                self._is_connected_trade_updates = True
                logger.info("Trade updates stream connected")

            except asyncio.CancelledError:
                logger.info("Trade updates stream cancelled")
                break
            except Exception as e:
                self._is_connected_trade_updates = False
                logger.error(f"Trade updates stream error: {e}", exc_info=True)

                # Exponential backoff reconnection
                delay = min(
                    self._reconnect_delay * (2**self._reconnect_attempts),
                    self._max_reconnect_delay,
                )
                logger.info(f"Reconnecting trade updates stream in {delay:.1f}s")
                await asyncio.sleep(delay)

    async def _on_stock_bar_update(self, bar):
        """Handle stock bar update from Alpaca (async handler)."""
        try:
            symbol = bar.symbol
            price = float(bar.close)
            timestamp = (
                bar.timestamp if hasattr(bar, "timestamp") else datetime.utcnow()
            )

            # Update cache directly since we are async
            await self._update_price_cache(symbol, price, timestamp)
            await self._broadcast_price(symbol, price)

        except Exception as e:
            logger.error(f"Error handling stock bar update: {e}", exc_info=True)

    async def _on_crypto_bar_update(self, bar):
        """Handle crypto bar update from Alpaca (async handler)."""
        try:
            symbol = bar.symbol
            price = float(bar.close)
            timestamp = (
                bar.timestamp if hasattr(bar, "timestamp") else datetime.utcnow()
            )

            # Update cache directly since we are async
            await self._update_price_cache(symbol, price, timestamp)
            await self._broadcast_price(symbol, price)

        except Exception as e:
            logger.error(f"Error handling crypto bar update: {e}", exc_info=True)

    async def _on_trade_update(self, trade_update):
        """Handle trade update from Alpaca (async handler).

        Note: TradingStream handlers are async, so we can process directly.
        """
        try:
            logger.info(f"Trade update received: {trade_update}")

            # Process directly since handler is async
            await self._process_trade_update(trade_update)

        except Exception as e:
            logger.error(f"Error handling trade update: {e}", exc_info=True)

    async def _process_async_queue(self):
        """Process async operations queued from sync handlers.

        This runs in the main event loop and processes updates from
        synchronous WebSocket handlers that run in blocking threads.
        """
        while True:
            try:
                # Wait for item from queue (with timeout for cancellation)
                try:
                    item = await asyncio.wait_for(self._async_queue.get(), timeout=1.0)
                except TimeoutError:
                    continue

                # Sentinel value signals shutdown
                if item is None:
                    break

                op_type, data = item

                if op_type == "price_update":
                    await self._update_price_cache(
                        data["symbol"], data["price"], data["timestamp"]
                    )
                    await self._broadcast_price(data["symbol"], data["price"])
                elif op_type == "trade_update":
                    await self._process_trade_update(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing async queue item: {e}", exc_info=True)

    async def _process_trade_update(self, trade_update):
        """Process trade update asynchronously."""
        try:
            # Extract order information from trade update
            order_id = (
                str(trade_update.order.id)
                if hasattr(trade_update, "order") and hasattr(trade_update.order, "id")
                else None
            )
            event = trade_update.event if hasattr(trade_update, "event") else None

            if not order_id:
                logger.warning(f"Trade update missing order ID: {trade_update}")
                return

            logger.info(f"Processing trade update: order_id={order_id}, event={event}")

            # Update order cache
            await self._update_order_cache(trade_update)

            # Update GTT order statuses
            await self._update_gtt_order_status(order_id, trade_update)

            # Broadcast via SSE to frontend
            await self._broadcast_order_update(order_id, event)

            # Call callback if set
            if self._on_order_update_callback:
                await self._on_order_update_callback(trade_update)

        except Exception as e:
            logger.error(f"Error processing trade update: {e}", exc_info=True)

    async def _update_order_cache(self, trade_update):
        """Update Alpaca order cache from trade update."""
        try:
            from alpaca_order_cache import update_alpaca_order_cache
            from database import SessionLocal

            db = SessionLocal()
            try:
                # Convert trade_update to dict format
                order_data = {
                    "id": str(trade_update.order.id),
                    "status": trade_update.order.status.value
                    if hasattr(trade_update.order.status, "value")
                    else str(trade_update.order.status),
                    "filled_qty": float(trade_update.order.filled_qty)
                    if trade_update.order.filled_qty
                    else 0,
                    "filled_avg_price": float(trade_update.order.filled_avg_price)
                    if trade_update.order.filled_avg_price
                    else None,
                    "submitted_at": trade_update.order.submitted_at.isoformat()
                    if trade_update.order.submitted_at
                    else None,
                    "filled_at": trade_update.order.filled_at.isoformat()
                    if trade_update.order.filled_at
                    else None,
                }

                update_alpaca_order_cache(db, order_data)
                logger.debug(f"Updated order cache for order {order_data['id']}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating order cache: {e}", exc_info=True)

    async def _update_gtt_order_status(self, order_id: str, trade_update):
        """Update GTT order status based on trade update."""
        try:
            from alpaca_client import AlpacaClient

            db = SessionLocal()
            try:
                alpaca_client = AlpacaClient()
                gtt_order = GTTOrderStatusService.update_order_status_from_alpaca_order(
                    db, alpaca_client, order_id
                )
                if gtt_order:
                    logger.info(
                        f"Updated GTT order {gtt_order.id} status from trade update"
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating GTT order status: {e}", exc_info=True)

    async def _broadcast_order_update(self, order_id: str, event: str):
        """Broadcast order update via SSE."""
        try:
            from core.sse_manager import sse_manager

            await sse_manager.broadcast(
                "order_updated", {"order_id": order_id, "event": event}
            )
        except Exception as e:
            logger.debug(f"Error broadcasting order update: {e}")

    async def _update_price_cache(self, symbol: str, price: float, timestamp: datetime):
        """Update price cache in database."""
        PriceCacheService.update_price(symbol, price, timestamp)

    async def _broadcast_price(self, symbol: str, price: float):
        """Broadcast price update to frontend WebSocket clients."""
        try:
            # Get market status (simplified - could cache this)
            is_market_open = False  # Will be updated from market clock if needed

            await PriceBroadcaster.broadcast_prices({symbol: price}, is_market_open)
        except Exception as e:
            logger.debug(f"Error broadcasting price for {symbol}: {e}")


# Global instance
_alpaca_ws_client: AlpacaWebSocketClient | None = None


def get_alpaca_ws_client() -> AlpacaWebSocketClient:
    """Get global Alpaca WebSocket client instance."""
    global _alpaca_ws_client
    if _alpaca_ws_client is None:
        _alpaca_ws_client = AlpacaWebSocketClient()
    return _alpaca_ws_client
