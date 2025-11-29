"""Asset information routes."""

import asyncio
import logging
from datetime import datetime

from alpaca_client import is_crypto_symbol
from core.dependencies import AlpacaClientDep
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from rate_limiter import rate_limit_alpaca_call
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["assets"])

# Timeout for Alpaca API calls (8 seconds - fail before frontend's 10s timeout)
ALPACA_API_TIMEOUT = 8.0


@router.get("/assets/search")
async def search_assets(
    q: str,
    limit: int = 10,
    asset_type: str | None = Query(
        None, description="Filter by asset type: 'crypto' or 'stock'"
    ),
):
    """Search for assets by symbol or name.

    Args:
        q: Search query (symbol or name)
        limit: Maximum number of results
        asset_type: Optional filter - 'crypto' to show only crypto, 'stock' to show only stocks
    """
    try:
        if not q or len(q) < 1:
            return []

        query = q.upper()

        # Load from cache
        from asset_cache import load_assets_cache

        assets_cache = load_assets_cache()

        results = []
        count = 0

        # Helper to check if asset matches filter
        def matches_filter(symbol: str) -> bool:
            if asset_type is None:
                return True
            asset_type_lower = asset_type.lower()
            is_crypto = is_crypto_symbol(symbol)
            if asset_type_lower == "crypto":
                return is_crypto
            if asset_type_lower == "stock":
                return not is_crypto
            return True  # Unknown filter type, return all

        # First pass: exact symbol match or starts with
        for symbol, data in assets_cache.items():
            if not matches_filter(symbol):
                continue
            if symbol.startswith(query):
                results.append(data)
                count += 1
                if count >= limit:
                    break

        # If we need more results, look for name matches
        if count < limit:
            for symbol, data in assets_cache.items():
                if not matches_filter(symbol):
                    continue
                # Skip if already added
                if symbol.startswith(query):
                    continue

                if query in data.get("name", "").upper():
                    results.append(data)
                    count += 1
                    if count >= limit:
                        break

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asset")
async def get_asset_info_query(
    symbol: str = Query(..., description="Symbol (supports crypto with / separator)"),
    db: Session = Depends(get_db),
    alpaca_client: AlpacaClientDep = ...,
):
    """Get asset information using query parameter.

    This endpoint supports symbols with '/' separator (e.g., BTC/USD).
    Use this for crypto symbols instead of the path parameter version.
    """
    return await _get_asset_info_impl(symbol, alpaca_client, db)


@router.get("/asset/{symbol}")
async def get_asset_info(
    symbol: str, db: Session = Depends(get_db), alpaca_client: AlpacaClientDep = ...
):
    """Get asset information.

    Note: For crypto symbols with '/' (e.g., BTC/USD), use query parameter instead:
    /api/asset?symbol=BTC/USD
    """
    return await _get_asset_info_impl(symbol, alpaca_client, db)


async def _get_asset_info_impl(
    symbol: str, alpaca_client: AlpacaClientDep, db: Session
):
    """Get asset information including company name, fractional trading status, and current price.

    Uses run_in_threadpool to offload blocking Alpaca SDK calls from event loop.
    Wrapped with timeout to prevent hanging requests through Cloudflare Tunnel.
    """
    try:
        symbol_upper = symbol.upper()

        # First try cache (fast, no API call needed)
        from asset_cache import load_assets_cache

        assets_cache = load_assets_cache()
        asset_data = None

        if symbol_upper in assets_cache:
            asset_data = assets_cache[symbol_upper]
        else:
            # Fallback to direct API call (with rate limiting and timeout)
            try:
                # Rate limit before making API call
                await rate_limit_alpaca_call()

                asset_info = await asyncio.wait_for(
                    run_in_threadpool(alpaca_client.get_asset_info, symbol_upper),
                    timeout=ALPACA_API_TIMEOUT,
                )
                if not asset_info:
                    raise HTTPException(
                        status_code=404, detail=f"Asset {symbol} not found"
                    )
                asset_data = asset_info
            except TimeoutError:
                logger.error(
                    f"Timeout fetching asset info for {symbol_upper}: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
                )
                # Return minimal data from cache if available, or raise error
                raise HTTPException(
                    status_code=504,
                    detail=f"Asset info fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
                )

        # Get current/last price from cache first (fast)
        # Get current price from cache using centralized service
        from core.price_cache_service import PriceCacheService

        current_price = PriceCacheService.get_price(symbol_upper)

        # If no cached price, try to get latest price (with rate limiting and timeout)
        if current_price is None:
            try:
                # Rate limit before making API call
                await rate_limit_alpaca_call()

                logger.debug(
                    f"Fetching latest price for {symbol_upper} (crypto: {is_crypto_symbol(symbol_upper)})"
                )
                latest_price = await asyncio.wait_for(
                    run_in_threadpool(alpaca_client.get_latest_price, symbol_upper),
                    timeout=ALPACA_API_TIMEOUT,
                )
                if latest_price:
                    logger.debug(f"Got price for {symbol_upper}: {latest_price}")
                    current_price = latest_price
                    # Update cache using centralized service
                    from core.price_cache_service import PriceCacheService

                    PriceCacheService.update_price(
                        symbol_upper, latest_price, datetime.utcnow()
                    )
                else:
                    logger.warning(f"No price returned for {symbol_upper}")
            except TimeoutError:
                logger.warning(
                    f"Timeout fetching price for {symbol_upper} - using cached data if available"
                )
                # Don't fail the whole request if price fetch times out
            except Exception as e:
                logger.error(
                    f"Error fetching price for {symbol_upper}: {e}", exc_info=True
                )
                # Don't fail the whole request if price fetch fails

        return {
            "symbol": asset_data.get("symbol", symbol_upper),
            "name": asset_data.get("name", symbol_upper),
            "exchange": asset_data.get("exchange", ""),
            "class": asset_data.get("class", ""),
            "tradable": asset_data.get("tradable", True),
            "fractionable": asset_data.get("fractionable", False),
            "current_price": current_price,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in _get_asset_info_impl for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
