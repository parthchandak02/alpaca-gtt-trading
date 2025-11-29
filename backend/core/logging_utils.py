"""Standardized logging utilities for consistent log formatting."""

import logging

from models import OrderStatus

logger = logging.getLogger(__name__)


def log_gtt_order_created(order_id: int, symbol: str, iterations: int):
    """Log GTT order creation."""
    logger.info(
        f"GTT order created: ID={order_id}, Symbol={symbol}, Orders={iterations}"
    )


def log_gtt_order_deleted(order_id: int, symbol: str | None = None):
    """Log GTT order deletion."""
    symbol_str = f", Symbol={symbol}" if symbol else ""
    logger.info(f"GTT order deleted: ID={order_id}{symbol_str}")


def log_order_detail_deleted(
    detail_id: int, order_id: int, symbol: str, remaining: int
):
    """Log order detail deletion."""
    logger.info(
        f"Order detail deleted: DetailID={detail_id}, OrderID={order_id}, Symbol={symbol}, Remaining={remaining}"
    )


def log_order_triggered(detail_id: int, symbol: str, limit_price: float):
    """Log when an order is triggered."""
    logger.info(
        f"Order triggered: DetailID={detail_id}, Symbol={symbol}, Limit=${limit_price:.2f}"
    )


def log_order_failed(detail_id: int, symbol: str, error: str):
    """Log order failure."""
    logger.error(f"Order failed: DetailID={detail_id}, Symbol={symbol}, Error={error}")


def log_price_fetch(prices: dict[str, float]):
    """Log price fetch operation."""
    price_str = ", ".join(
        [f"{sym}=${p:.2f}" if p else f"{sym}=N/A" for sym, p in prices.items()]
    )
    logger.info(f"💰 Current Market Prices: {price_str}")


def log_gtt_monitoring_summary(
    orders: list, prices: dict[str, float], db=None, alpaca_client=None
):
    """Log concise GTT monitoring summary.

    Args:
        orders: List of GTTOrder objects
        prices: Dictionary of symbol -> price
        db: Optional database session (required for status lookups)
        alpaca_client: Optional Alpaca client (required for status lookups)
    """
    for order in orders:
        current_price = prices.get(order.symbol)
        if not current_price:
            continue

        # Count order details by status
        # If db and alpaca_client are provided, fetch status from cache
        # Otherwise, use simpler logic based on alpaca_order_id presence
        pending_details = []
        filled_details = []
        failed_details = []

        if db and alpaca_client:
            # Import here to avoid circular imports
            from gtt_service import _get_detail_status

            for d in order.order_details:
                if d.is_manually_linked:
                    continue

                # Get status from cache
                detail_status = _get_detail_status(db, alpaca_client, d)

                if detail_status == OrderStatus.PENDING.value:
                    pending_details.append(d)
                elif detail_status == OrderStatus.FILLED.value:
                    filled_details.append(d)
                elif detail_status in [
                    OrderStatus.FAILED.value,
                    OrderStatus.CANCELLED.value,
                    OrderStatus.EXPIRED.value,
                ]:
                    failed_details.append(d)
        else:
            # Fallback: use simpler logic without status lookups
            # Pending = no alpaca_order_id, others = has alpaca_order_id
            for d in order.order_details:
                if d.is_manually_linked:
                    continue
                if not d.alpaca_order_id:
                    pending_details.append(d)
                # Note: Can't distinguish filled vs failed without status lookup

        # Get trigger price range
        if pending_details:
            min_trigger = min(d.trigger_price for d in pending_details)
            max_trigger = max(d.trigger_price for d in pending_details)
            trigger_range = (
                f"${min_trigger:.2f}-${max_trigger:.2f}"
                if min_trigger != max_trigger
                else f"${min_trigger:.2f}"
            )
        else:
            trigger_range = "N/A"

        # Compact one-line summary
        status_summary = f"P:{len(pending_details)}"
        if filled_details:
            status_summary += f" F:{len(filled_details)}"
        if failed_details:
            status_summary += f" X:{len(failed_details)}"

        # Visual indicator based on status
        icon = "📊"  # Default
        if len(pending_details) == 0:
            icon = "✅"  # All filled
        elif filled_details:
            icon = "⚡"  # Partially filled

        logger.info(
            f"{icon} GTT #{order.id} {order.symbol}: "
            f"Price=${current_price:.2f} | "
            f"Triggers={trigger_range} | "
            f"{status_summary} | "
            f"Value=${order.total_value:.2f}"
        )


def log_api_request(method: str, path: str, status_code: int = None):
    """Log API request."""
    status_str = f", Status={status_code}" if status_code else ""
    logger.debug(f"API request: {method} {path}{status_str}")


def log_api_error(method: str, path: str, error: str, status_code: int = 500):
    """Log API error."""
    logger.error(f"API error: {method} {path}, Status={status_code}, Error={error}")


def log_validation_error(resource: str, error: str):
    """Log validation error."""
    logger.warning(f"Validation error: Resource={resource}, Error={error}")
