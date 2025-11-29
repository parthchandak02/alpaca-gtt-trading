"""Historical market data routes."""

import asyncio
import logging

from core.dependencies import AlpacaClientDep
from fastapi import APIRouter, HTTPException, Query
from rate_limiter import rate_limit_alpaca_call
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["historical"])

# Timeout for Alpaca API calls (8 seconds - fail before frontend's 10s timeout)
ALPACA_API_TIMEOUT = 8.0


@router.get("/historical-bars/{symbol}")
async def get_historical_bars(
    symbol: str,
    days: int = 30,
    timeframe: str = "Day",
    alpaca_client: AlpacaClientDep = ...,
):
    """Get historical bars for a symbol.

    Note: For crypto symbols with '/' (e.g., BTC/USD), use query parameter instead:
    /api/historical-bars?symbol=BTC/USD&days=90
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        bars = await asyncio.wait_for(
            run_in_threadpool(
                alpaca_client.get_historical_bars, symbol.upper(), days, timeframe
            ),
            timeout=ALPACA_API_TIMEOUT,
        )
        return {"symbol": symbol.upper(), "bars": bars}
    except TimeoutError:
        logger.error(
            f"Timeout fetching historical bars for {symbol}: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Historical bars fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical bars: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical-bars")
async def get_historical_bars_query(
    symbol: str = Query(..., description="Symbol (supports crypto with / separator)"),
    days: int = Query(30, description="Number of days"),
    timeframe: str = Query(
        "Day", description="Timeframe: Minute, Hour, Day, Week, Month"
    ),
    alpaca_client: AlpacaClientDep = ...,
):
    """Get historical bars for a symbol using query parameter.

    This endpoint supports symbols with '/' separator (e.g., BTC/USD).
    Use this for crypto symbols instead of the path parameter version.
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        bars = await asyncio.wait_for(
            run_in_threadpool(
                alpaca_client.get_historical_bars, symbol.upper(), days, timeframe
            ),
            timeout=ALPACA_API_TIMEOUT,
        )
        return {"symbol": symbol.upper(), "bars": bars}
    except TimeoutError:
        logger.error(
            f"Timeout fetching historical bars for {symbol}: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Historical bars fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical bars: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
