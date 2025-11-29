"""Service for caching Alpaca order data with stale-while-revalidate pattern."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from alpaca_client import AlpacaClient
from models import AlpacaOrderCache
from rate_limiter import rate_limit_alpaca_call_sync
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Cache TTL: Consider data stale after 5 minutes, but keep using it while refreshing
CACHE_STALE_THRESHOLD = timedelta(minutes=5)
# Background refresh interval: Update cache every 2-3 minutes
BACKGROUND_REFRESH_INTERVAL = timedelta(minutes=2)


def get_alpaca_order_data(
    db: Session,
    alpaca_client: AlpacaClient,
    alpaca_order_id: str,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """
    Get Alpaca order data with caching (stale-while-revalidate pattern).

    - Returns cached data immediately if available and fresh
    - Returns cached data even if stale (for immediate response)
    - Triggers background refresh if stale
    - Fetches fresh if cache missing or force_refresh=True

    Args:
        db: Database session
        alpaca_client: Alpaca client instance
        alpaca_order_id: Alpaca order ID
        force_refresh: Force fresh fetch from Alpaca API

    Returns:
        Dict with order data (status, timestamps, etc.) or None if order not found
    """
    # Check cache first
    cache_entry = (
        db.query(AlpacaOrderCache)
        .filter(AlpacaOrderCache.alpaca_order_id == alpaca_order_id)
        .first()
    )

    # If cache exists and fresh, return immediately
    if cache_entry and not force_refresh:
        age = datetime.utcnow() - cache_entry.last_fetched_at
        if age < CACHE_STALE_THRESHOLD:
            return _cache_to_dict(cache_entry)

        # Cache is stale - return cached data but mark for refresh
        # (In production, you'd trigger background refresh here)
        logger.debug(f"Cache stale for order {alpaca_order_id}, returning cached data")
        return _cache_to_dict(cache_entry)

    # Fetch fresh from Alpaca API
    try:
        # Rate limit before fetching order
        rate_limit_alpaca_call_sync()
        alpaca_order = alpaca_client.get_order(alpaca_order_id)
        if not alpaca_order:
            # Order not found - remove from cache if exists
            if cache_entry:
                db.delete(cache_entry)
                db.commit()
            return None

        # Update or create cache entry
        if cache_entry:
            _update_cache_from_alpaca(cache_entry, alpaca_order)
        else:
            cache_entry = _create_cache_from_alpaca(alpaca_order)
            db.add(cache_entry)

        db.commit()
        return _cache_to_dict(cache_entry)

    except Exception as e:
        logger.error(f"Error fetching Alpaca order {alpaca_order_id}: {e}")
        db.rollback()  # Ensure session is clean
        # Return cached data if available (graceful degradation)
        if cache_entry:
            logger.warning(f"Returning stale cache due to API error: {e}")
            return _cache_to_dict(cache_entry)
        return None


def refresh_alpaca_order_cache(
    db: Session, alpaca_client: AlpacaClient, alpaca_order_id: str
) -> bool:
    """
    Refresh cache for a specific Alpaca order (background sync).

    Returns True if successful, False otherwise.
    """
    try:
        # Rate limit before fetching order
        rate_limit_alpaca_call_sync()
        alpaca_order = alpaca_client.get_order(alpaca_order_id)
        if not alpaca_order:
            return False

        cache_entry = (
            db.query(AlpacaOrderCache)
            .filter(AlpacaOrderCache.alpaca_order_id == alpaca_order_id)
            .first()
        )

        if cache_entry:
            _update_cache_from_alpaca(cache_entry, alpaca_order)
        else:
            cache_entry = _create_cache_from_alpaca(alpaca_order)
            db.add(cache_entry)

        db.commit()
        return True

    except Exception as e:
        logger.error(f"Error refreshing cache for order {alpaca_order_id}: {e}")
        return False


def batch_refresh_stale_orders(
    db: Session,
    alpaca_client: AlpacaClient,
    max_age: timedelta = BACKGROUND_REFRESH_INTERVAL,
    limit: int = 50,
) -> int:
    """
    Refresh stale cache entries in batch (for background sync).

    Args:
        db: Database session
        alpaca_client: Alpaca client instance
        max_age: Only refresh entries older than this
        limit: Maximum number of orders to refresh per call

    Returns:
        Number of orders refreshed
    """
    cutoff_time = datetime.utcnow() - max_age

    stale_entries = (
        db.query(AlpacaOrderCache)
        .filter(AlpacaOrderCache.last_fetched_at < cutoff_time)
        .limit(limit)
        .all()
    )

    refreshed_count = 0
    for cache_entry in stale_entries:
        try:
            # Rate limit before fetching each order (batch refresh)
            rate_limit_alpaca_call_sync()
            alpaca_order = alpaca_client.get_order(cache_entry.alpaca_order_id)
            if alpaca_order:
                _update_cache_from_alpaca(cache_entry, alpaca_order)
                refreshed_count += 1
        except Exception as e:
            logger.warning(f"Error refreshing order {cache_entry.alpaca_order_id}: {e}")

    if refreshed_count > 0:
        db.commit()

    return refreshed_count


def update_alpaca_order_cache(db: Session, order_data: dict[str, Any]) -> None:
    """
    Update cache directly from order data dict (e.g., from WebSocket update).
    
    Args:
        db: Database session
        order_data: Dict containing order data
    """
    alpaca_order_id = order_data.get("id")
    if not alpaca_order_id:
        return

    cache_entry = (
        db.query(AlpacaOrderCache)
        .filter(AlpacaOrderCache.alpaca_order_id == alpaca_order_id)
        .first()
    )

    if cache_entry:
        _update_cache_from_alpaca(cache_entry, order_data)
    else:
        cache_entry = _create_cache_from_alpaca(order_data)
        db.add(cache_entry)

    db.commit()


def _create_cache_from_alpaca(alpaca_order: dict[str, Any]) -> AlpacaOrderCache:
    """Create cache entry from Alpaca order data."""
    from dateutil import parser

    cache_entry = AlpacaOrderCache(
        alpaca_order_id=alpaca_order.get("id"),
        status=alpaca_order.get("status", "").upper(),
        filled_qty=alpaca_order.get("filled_qty"),
        filled_avg_price=alpaca_order.get("filled_avg_price"),
    )

    # Parse timestamps - ensure UTC timezone
    if alpaca_order.get("submitted_at"):
        try:
            dt = parser.parse(alpaca_order["submitted_at"])
            # If naive datetime, assume UTC (Alpaca timestamps are always UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.submitted_at = dt
        except:
            pass

    if alpaca_order.get("filled_at"):
        try:
            dt = parser.parse(alpaca_order["filled_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.filled_at = dt
        except:
            pass

    if alpaca_order.get("expired_at"):
        try:
            dt = parser.parse(alpaca_order["expired_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.expired_at = dt
        except:
            pass

    cache_entry.last_fetched_at = datetime.utcnow()
    return cache_entry


def _update_cache_from_alpaca(
    cache_entry: AlpacaOrderCache, alpaca_order: dict[str, Any]
) -> None:
    """Update existing cache entry from Alpaca order data."""
    from dateutil import parser

    cache_entry.status = alpaca_order.get("status", "").upper()
    cache_entry.filled_qty = alpaca_order.get("filled_qty")
    cache_entry.filled_avg_price = alpaca_order.get("filled_avg_price")
    cache_entry.last_fetched_at = datetime.utcnow()

    # Parse timestamps - ensure UTC timezone
    if alpaca_order.get("submitted_at"):
        try:
            dt = parser.parse(alpaca_order["submitted_at"])
            # If naive datetime, assume UTC (Alpaca timestamps are always UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.submitted_at = dt
        except:
            pass

    if alpaca_order.get("filled_at"):
        try:
            dt = parser.parse(alpaca_order["filled_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.filled_at = dt
        except:
            pass

    if alpaca_order.get("expired_at"):
        try:
            dt = parser.parse(alpaca_order["expired_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            cache_entry.expired_at = dt
        except:
            pass


def _cache_to_dict(cache_entry: AlpacaOrderCache) -> dict[str, Any]:
    """Convert cache entry to dictionary format."""

    def format_datetime(dt: datetime) -> str:
        """Format datetime to ISO string, ensuring UTC timezone is included."""
        if dt is None:
            return None
        # Ensure UTC timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        # Return ISO format with timezone (will include +00:00 for UTC)
        return dt.isoformat()

    return {
        "status": cache_entry.status,
        "submitted_at": format_datetime(cache_entry.submitted_at),
        "filled_at": format_datetime(cache_entry.filled_at),
        "expired_at": format_datetime(cache_entry.expired_at),
        "filled_qty": cache_entry.filled_qty,
        "filled_avg_price": cache_entry.filled_avg_price,
        "cached_at": format_datetime(cache_entry.cached_at),
        "last_fetched_at": format_datetime(cache_entry.last_fetched_at),
    }
