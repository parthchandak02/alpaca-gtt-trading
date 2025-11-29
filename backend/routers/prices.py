"""Price-related routes."""

import asyncio
import logging
from datetime import datetime, timedelta

from core.dependencies import AlpacaClientDep
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from gtt_service import GTTService
from rate_limiter import rate_limit_alpaca_call
from schemas import PriceResponse, PricesResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["prices"])

# Reduced timeout for Alpaca API calls (15 seconds - faster failover to cache)
# This ensures we return cached data quickly if API is slow
ALPACA_API_TIMEOUT = 15.0

# Cache freshness threshold - consider cache stale after 60 seconds
CACHE_STALE_THRESHOLD = timedelta(seconds=60)


@router.get("/prices", response_model=PricesResponse)
async def get_prices(
    symbols: str = None,
    db: Session = Depends(get_db),
    alpaca_client: AlpacaClientDep = ...,
):
    """Get current prices for symbols.

    Optimized to return cached prices immediately while fetching fresh prices in background.
    This prevents timeouts when API calls are slow.
    """
    try:
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
        else:
            # Get symbols from all active GTT orders
            service = GTTService(db)
            gtt_orders = service.get_all_gtt_orders()
            symbol_list = list(set([order.symbol for order in gtt_orders]))

        if not symbol_list:
            return PricesResponse(prices=[])

        # Load cached prices first (fast path) using centralized service
        from core.price_cache_service import PriceCacheService

        cached_prices = PriceCacheService.get_prices(symbol_list)
        cached_timestamps = {}
        now = datetime.utcnow()
        for symbol in symbol_list:
            price_data = PriceCacheService.get_price_with_timestamp(symbol)
            if price_data:
                cached_timestamps[symbol] = price_data.get("timestamp") or now
            else:
                cached_timestamps[symbol] = now
        # Filter out None prices
        cached_prices = {k: v for k, v in cached_prices.items() if v is not None}

        # Determine if we need fresh prices (cache is stale or missing)
        need_fresh_prices = False
        if not cached_prices:
            need_fresh_prices = True
        else:
            # Check if any cached prices are stale
            for symbol, timestamp in cached_timestamps.items():
                if now - timestamp > CACHE_STALE_THRESHOLD:
                    need_fresh_prices = True
                    break

        # Try to get market status (non-blocking, fast timeout)
        is_market_open = False
        try:
            await rate_limit_alpaca_call()
            market_clock = await asyncio.wait_for(
                run_in_threadpool(alpaca_client.get_market_clock),
                timeout=2.0,  # Very short timeout for market status
            )
            is_market_open = market_clock.get("is_open", False)
        except (TimeoutError, Exception) as e:
            logger.debug(f"Market clock fetch failed (non-critical): {e}")
            # Use cached market status or default to closed

        # If we have fresh cached prices, return them immediately
        # Fetch fresh prices in background if needed
        if cached_prices and not need_fresh_prices:
            # Return cached prices immediately
            price_responses = [
                PriceResponse(
                    symbol=symbol,
                    price=price,
                    timestamp=cached_timestamps.get(symbol, now),
                    is_market_open=is_market_open,
                )
                for symbol, price in cached_prices.items()
            ]

            # Fetch fresh prices in background (fire and forget)
            if len(symbol_list) > 0:
                asyncio.create_task(
                    _refresh_prices_background(alpaca_client, symbol_list)
                )

            return PricesResponse(prices=price_responses)

        # Need fresh prices - try to fetch with timeout
        prices = {}
        try:
            await rate_limit_alpaca_call()
            prices = await asyncio.wait_for(
                run_in_threadpool(alpaca_client.get_latest_prices, symbol_list),
                timeout=ALPACA_API_TIMEOUT,
            )
        except TimeoutError:
            logger.warning(
                f"Timeout fetching prices for {len(symbol_list)} symbols - using cache"
            )
            prices = {}
        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            prices = {}

        # Update cache with fresh prices (if we got any)
        if prices:
            try:
                from core.price_cache_service import PriceCacheService

                PriceCacheService.update_prices(prices, datetime.utcnow())
            except Exception as e:
                logger.error(f"Error updating price cache: {e}", exc_info=True)

        # Build response - prefer fresh prices, fallback to cache
        price_responses = []
        if prices:
            # Use fresh API prices
            price_responses = [
                PriceResponse(
                    symbol=symbol,
                    price=price,
                    timestamp=datetime.utcnow(),
                    is_market_open=is_market_open,
                )
                for symbol, price in prices.items()
                if price is not None
            ]
        else:
            # Fallback to cached prices
            for symbol in symbol_list:
                if symbol in cached_prices:
                    price_responses.append(
                        PriceResponse(
                            symbol=symbol,
                            price=cached_prices[symbol],
                            timestamp=cached_timestamps.get(symbol, now),
                            is_market_open=is_market_open,
                        )
                    )

        return PricesResponse(prices=price_responses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _refresh_prices_background(alpaca_client, symbol_list: list):
    """Background task to refresh prices without blocking the request."""
    try:
        # Create new database session for background task
        db = next(get_db())
        try:
            await rate_limit_alpaca_call()
            prices = await asyncio.wait_for(
                run_in_threadpool(alpaca_client.get_latest_prices, symbol_list),
                timeout=ALPACA_API_TIMEOUT,
            )

            if prices:
                # Update cache in background using centralized service
                from core.price_cache_service import PriceCacheService

                PriceCacheService.update_prices(prices, datetime.utcnow())
                logger.debug(
                    f"Background price refresh completed for {len(prices)} symbols"
                )
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Background price refresh failed (non-critical): {e}")
