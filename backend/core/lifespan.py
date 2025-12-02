"""Application lifespan management (startup/shutdown)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from alpaca_client import AlpacaClient
from config import settings
from database import Base, engine
from fastapi import FastAPI

from .alpaca_websocket_client import get_alpaca_ws_client
from .background_tasks import price_monitoring_loop
from .dependencies import set_alpaca_client

logger = logging.getLogger(__name__)

# Global task reference
price_monitor_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global price_monitor_task

    # Startup
    logger.info("Starting up...")
    logger.info(f"Trading mode: {'PAPER' if settings.use_paper_trading else 'LIVE'}")
    logger.info(f"Database: {settings.database_url}")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Initialize Alpaca client
    alpaca_client = AlpacaClient()
    set_alpaca_client(alpaca_client)
    logger.info("Alpaca client initialized")

    # Set Alpaca client for background monitoring (for market status checks)
    from .background_tasks import set_alpaca_client_for_monitoring

    set_alpaca_client_for_monitoring(alpaca_client)

    # Refresh assets cache on startup (in background to avoid blocking)
    try:
        from asset_cache import refresh_assets_cache

        logger.info("Scheduling assets cache refresh in background...")
        # Run in background thread/task to allow fast startup
        asyncio.create_task(asyncio.to_thread(refresh_assets_cache))
    except Exception as e:
        logger.warning(f"Failed to schedule assets cache refresh: {e}")

    # Start Alpaca WebSocket client for real-time prices and order updates
    alpaca_ws_client = get_alpaca_ws_client()
    await alpaca_ws_client.start()
    logger.info("Alpaca WebSocket client started for real-time market data")

    # Start background price monitoring task (fallback/backup)
    price_monitor_task = asyncio.create_task(price_monitoring_loop())
    logger.info(
        "Price monitoring task started - will check GTT orders every 60s (fixed interval to avoid API overload)"
    )

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop WebSocket client
    alpaca_ws_client = get_alpaca_ws_client()
    await alpaca_ws_client.stop()
    logger.info("Alpaca WebSocket client stopped")

    # Stop price monitoring task
    if price_monitor_task:
        price_monitor_task.cancel()
        try:
            await price_monitor_task
        except asyncio.CancelledError:
            pass
