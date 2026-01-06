"""Background tasks for the application."""

import asyncio
import logging
from datetime import datetime

from alpaca_client import AlpacaClient
from database import get_db
from gtt_service import GTTService
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# Timeout for Alpaca API calls in background tasks (15 seconds - more lenient than HTTP endpoints)
ALPACA_API_TIMEOUT = 15.0

# Global Alpaca client for checking market status
_alpaca_client: AlpacaClient | None = None

# Track when daily summary was last sent
_last_summary_date: str | None = None

# Daily summary time window (in UTC)
# US market closes at 4:00 PM EST = 21:00 UTC (winter) / 20:00 UTC (summer)
# We send summary between 21:00-21:30 UTC to catch both DST scenarios
DAILY_SUMMARY_START_HOUR_UTC = 20  # 8 PM UTC (covers summer: 4 PM EDT)
DAILY_SUMMARY_END_HOUR_UTC = 22    # 10 PM UTC (covers winter: 4 PM EST + buffer)


def set_alpaca_client_for_monitoring(client: AlpacaClient):
    """Set the Alpaca client for market status checks."""
    global _alpaca_client
    _alpaca_client = client


async def price_monitoring_loop():
    """Background task for price monitoring and order triggering.

    Uses fixed 60-second polling interval to avoid overloading Alpaca API.
    This ensures we stay well within rate limits (200 requests/minute).
    """
    global _alpaca_client, _last_summary_date

    logger.info("=" * 80)
    logger.info("🚀 GTT PRICE MONITORING SERVICE STARTED")
    logger.info("=" * 80)

    # Fixed polling interval: 60 seconds (to avoid overloading API)
    poll_interval = 60
    logger.info(f"⏰ Price monitoring configured: checking every {poll_interval}s")

    while True:
        try:
            await asyncio.sleep(poll_interval)

            # Get database session
            db = next(get_db())
            try:
                service = GTTService(db)
                logger.info("-" * 80)
                logger.info("🔍 PRICE MONITORING CYCLE STARTED")
                logger.info("-" * 80)
                
                # Check if it's time to send daily summary (time-based, not transition-based)
                # This is more reliable than detecting market close transitions
                now_utc = datetime.utcnow()
                today_date = now_utc.strftime("%Y-%m-%d")
                current_hour = now_utc.hour
                
                # Send daily summary if:
                # 1. Within the summary time window (8 PM - 10 PM UTC covers EST/EDT market close)
                # 2. Haven't sent today yet
                # 3. Market is actually closed (to avoid sending during extended hours)
                should_send_summary = (
                    DAILY_SUMMARY_START_HOUR_UTC <= current_hour < DAILY_SUMMARY_END_HOUR_UTC
                    and _last_summary_date != today_date
                )
                
                if should_send_summary:
                    # Double-check market is closed before sending
                    market_is_closed = True
                    try:
                        if _alpaca_client:
                            market_clock = await asyncio.wait_for(
                                run_in_threadpool(_alpaca_client.get_market_clock),
                                timeout=2.0,
                            )
                            market_is_closed = not market_clock.get("is_open", False)
                    except Exception:
                        pass  # If we can't check, assume closed (we're in the right time window)
                    
                    if market_is_closed:
                        logger.info(f"📊 Daily summary time ({current_hour}:00 UTC) - sending trading summary")
                        try:
                            from core.daily_summary_service import send_enhanced_daily_summary
                            
                            await asyncio.wait_for(
                                run_in_threadpool(
                                    send_enhanced_daily_summary, db, _alpaca_client
                                ),
                                timeout=15.0,
                            )
                            _last_summary_date = today_date
                            logger.info("✅ Daily trading summary sent successfully")
                        except TimeoutError:
                            logger.error("❌ Timeout sending daily summary")
                        except Exception as e:
                            logger.error(f"❌ Error sending daily summary: {e}")
                # Check for corporate actions first (may cancel orders)
                # Wrap blocking calls with timeout protection
                try:
                    await asyncio.wait_for(
                        run_in_threadpool(service.check_corporate_actions),
                        timeout=ALPACA_API_TIMEOUT,
                    )
                except TimeoutError:
                    logger.error(
                        f"❌ Timeout checking corporate actions (exceeded {ALPACA_API_TIMEOUT}s)"
                    )

                # Then check prices and trigger orders
                try:
                    # Get pending orders symbols before calling check_and_trigger_orders
                    from models import GTTOrder, OrderStatus

                    pending_orders = (
                        db.query(GTTOrder)
                        .filter(GTTOrder.status == OrderStatus.PENDING)
                        .all()
                    )
                    symbols_to_monitor = (
                        list(set([order.symbol for order in pending_orders]))
                        if pending_orders
                        else []
                    )

                    # Subscribe to symbols via WebSocket for real-time updates
                    if symbols_to_monitor:
                        try:
                            from core.alpaca_websocket_client import (
                                get_alpaca_ws_client,
                            )

                            ws_client = get_alpaca_ws_client()
                            await ws_client.subscribe_symbols(symbols_to_monitor)
                        except Exception as e:
                            logger.debug(
                                f"Error subscribing to WebSocket symbols (non-critical): {e}"
                            )

                    await asyncio.wait_for(
                        run_in_threadpool(service.check_and_trigger_orders),
                        timeout=ALPACA_API_TIMEOUT,
                    )

                    # Broadcast prices to WebSocket clients after price check completes
                    # Prices are now in cache, so we can read them and broadcast
                    if symbols_to_monitor:
                        try:
                            from core.price_broadcaster import PriceBroadcaster

                            # Get latest prices from cache using centralized service
                            from core.price_cache_service import PriceCacheService

                            cached_prices = PriceCacheService.get_prices(
                                symbols_to_monitor
                            )
                            # Filter out None values
                            cached_prices = {
                                k: v for k, v in cached_prices.items() if v is not None
                            }

                            if cached_prices:
                                # Get market status
                                is_market_open = False
                                try:
                                    if _alpaca_client:
                                        market_clock = await asyncio.wait_for(
                                            run_in_threadpool(
                                                _alpaca_client.get_market_clock
                                            ),
                                            timeout=2.0,
                                        )
                                        is_market_open = market_clock.get(
                                            "is_open", False
                                        )
                                except Exception:
                                    pass

                                # Broadcast prices to WebSocket clients
                                await PriceBroadcaster.broadcast_prices(
                                    cached_prices, is_market_open
                                )
                        except Exception as e:
                            logger.debug(
                                f"Error broadcasting prices to WebSocket (non-critical): {e}"
                            )

                except TimeoutError:
                    logger.error(
                        f"❌ Timeout checking and triggering orders (exceeded {ALPACA_API_TIMEOUT}s)"
                    )

                # Finally update order statuses from Alpaca cache (lower frequency sync)
                # This runs every price check cycle, but cache refresh is rate-limited internally
                try:
                    await asyncio.wait_for(
                        run_in_threadpool(service.update_order_statuses),
                        timeout=ALPACA_API_TIMEOUT,
                    )
                except TimeoutError:
                    logger.error(
                        f"❌ Timeout updating order statuses (exceeded {ALPACA_API_TIMEOUT}s)"
                    )

                logger.info("✅ Price monitoring cycle completed")
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("🛑 Price monitoring cancelled - shutting down")
            break
        except Exception as e:
            logger.error(f"❌ Error in price monitoring loop: {e}")
