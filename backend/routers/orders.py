"""Alpaca order routes (not GTT orders)."""

import asyncio
import logging

from core.dependencies import AlpacaClientDep
from fastapi import APIRouter, HTTPException
from rate_limiter import rate_limit_alpaca_call
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["orders"])

# Timeout for Alpaca API calls (8 seconds - fail before frontend's 10s timeout)
ALPACA_API_TIMEOUT = 8.0


@router.get("/orders")
async def get_orders(
    status: str = None,
    symbol: str = None,
    limit: int = 100,
    alpaca_client: AlpacaClientDep = ...,
):
    """Get all orders from Alpaca, optionally filtered by status and symbol."""
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        orders = await asyncio.wait_for(
            run_in_threadpool(alpaca_client.get_all_orders, status, limit),
            timeout=ALPACA_API_TIMEOUT,
        )

        # Filter by symbol if provided
        if symbol:
            symbol_upper = symbol.upper()
            orders = [o for o in orders if o.get("symbol", "").upper() == symbol_upper]

        return orders
    except TimeoutError:
        logger.error(
            f"Timeout fetching orders: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Orders fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
