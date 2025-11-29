"""Centralized service for GTT order status updates.

This module provides a single source of truth for updating GTT order statuses
based on Alpaca order status, eliminating code duplication.
"""

import logging

from alpaca_client import AlpacaClient
from alpaca_order_cache import get_alpaca_order_data
from models import GTTOrder, GTTOrderDetail, OrderStatus

logger = logging.getLogger(__name__)


class GTTOrderStatusService:
    """Service for managing GTT order status updates."""

    @staticmethod
    def update_order_status_from_alpaca_order(
        db, alpaca_client: AlpacaClient, order_id: str
    ) -> GTTOrder | None:
        """Update GTT order status based on an Alpaca order ID.

        Args:
            db: Database session
            alpaca_client: Alpaca client instance
            order_id: Alpaca order ID

        Returns:
            Updated GTTOrder if found, None otherwise
        """
        try:
            # Find GTT order detail linked to this Alpaca order
            detail = (
                db.query(GTTOrderDetail)
                .filter(GTTOrderDetail.alpaca_order_id == order_id)
                .first()
            )

            if not detail:
                logger.debug(f"No GTT order detail found for Alpaca order {order_id}")
                return None

            gtt_order = detail.gtt_order

            # Update filled count for the GTT order
            filled_count = GTTOrderStatusService._calculate_filled_count(
                db, alpaca_client, gtt_order
            )

            gtt_order.filled_count = filled_count

            # Update GTT order status
            if filled_count == gtt_order.total_count:
                gtt_order.status = OrderStatus.FILLED
            elif filled_count > 0:
                gtt_order.status = OrderStatus.PARTIALLY_FILLED

            # Recalculate locked buying power based on order statuses
            locked_amount = GTTOrderStatusService._calculate_locked_buying_power(
                db, alpaca_client, gtt_order
            )
            gtt_order.locked_buying_power = locked_amount

            db.commit()
            logger.debug(
                f"Updated GTT order {gtt_order.id} status: filled_count={filled_count}, status={gtt_order.status}"
            )

            return gtt_order

        except Exception as e:
            logger.error(
                f"Error updating GTT order status for order {order_id}: {e}",
                exc_info=True,
            )
            db.rollback()
            return None

    @staticmethod
    def update_order_statuses(
        db, alpaca_client: AlpacaClient, gtt_orders: list[GTTOrder] | None = None
    ) -> int:
        """Update statuses for multiple GTT orders.

        Args:
            db: Database session
            alpaca_client: Alpaca client instance
            gtt_orders: Optional list of GTT orders to update (if None, updates all pending orders)

        Returns:
            Number of orders updated
        """
        try:
            if gtt_orders is None:
                # Get all pending orders
                gtt_orders = (
                    db.query(GTTOrder)
                    .filter(GTTOrder.status == OrderStatus.PENDING)
                    .all()
                )

            updated_count = 0
            for gtt_order in gtt_orders:
                filled_count = GTTOrderStatusService._calculate_filled_count(
                    db, alpaca_client, gtt_order
                )

                gtt_order.filled_count = filled_count

                # Update GTT order status
                if filled_count == gtt_order.total_count:
                    gtt_order.status = OrderStatus.FILLED
                elif filled_count > 0:
                    gtt_order.status = OrderStatus.PARTIALLY_FILLED

                # Recalculate locked buying power based on order statuses
                locked_amount = GTTOrderStatusService._calculate_locked_buying_power(
                    db, alpaca_client, gtt_order
                )
                gtt_order.locked_buying_power = locked_amount

                updated_count += 1

            db.commit()
            logger.debug(f"Updated statuses for {updated_count} GTT orders")

            return updated_count

        except Exception as e:
            logger.error(f"Error updating GTT order statuses: {e}", exc_info=True)
            db.rollback()
            return 0

    @staticmethod
    def _calculate_filled_count(
        db, alpaca_client: AlpacaClient, gtt_order: GTTOrder
    ) -> int:
        """Calculate filled count for a GTT order.

        Args:
            db: Database session
            alpaca_client: Alpaca client instance
            gtt_order: GTT order to calculate for

        Returns:
            Number of filled order details
        """
        filled_count = 0
        for detail in gtt_order.order_details:
            if detail.alpaca_order_id:
                cache_data = get_alpaca_order_data(
                    db, alpaca_client, detail.alpaca_order_id, force_refresh=False
                )
                if cache_data and cache_data.get("status") == "FILLED":
                    filled_count += 1
        return filled_count

    @staticmethod
    def _calculate_locked_buying_power(
        db, alpaca_client: AlpacaClient, gtt_order: GTTOrder
    ) -> float:
        """Calculate locked buying power for a GTT order.

        IMPORTANT: Only orders SUBMITTED TO ALPACA lock buying power.
        - Our internal PENDING status (no alpaca_order_id) = NOT submitted = does NOT lock buying power
        - Alpaca's pending statuses (has alpaca_order_id) = submitted = DOES lock buying power

        Orders that lock buying power (must have alpaca_order_id):
        - NEW, ACCEPTED, PENDING_NEW (submitted but not filled)
        - PARTIALLY_FILLED (remaining quantity locks buying power)
        - PENDING_CANCEL, PENDING_REPLACE (still locks until cancelled/replaced)
        - Any Alpaca "pending" status (submitted to Alpaca)

        Orders that DO NOT lock buying power:
        - Our internal PENDING (no alpaca_order_id - not yet triggered/submitted)
        - FILLED (executed, money deducted)
        - CANCELLED, EXPIRED, REJECTED (buying power released)
        - DONE_FOR_DAY, REPLACED, FAILED (terminal states)

        Args:
            db: Database session
            alpaca_client: Alpaca client instance
            gtt_order: GTT order to calculate for

        Returns:
            Total locked buying power amount
        """
        from gtt_service import _get_detail_status
        from alpaca_order_cache import get_alpaca_order_data

        locked_amount = 0.0
        for detail in gtt_order.order_details:
            # Only orders submitted to Alpaca (have alpaca_order_id) can lock buying power
            if not detail.alpaca_order_id:
                # Our internal PENDING - not submitted yet, does NOT lock buying power
                continue

            # Order is submitted to Alpaca - check its status
            cache_data = get_alpaca_order_data(
                db, alpaca_client, detail.alpaca_order_id, force_refresh=False
            )
            if cache_data and cache_data.get("status"):
                detail_status = cache_data["status"]
                if OrderStatus.locks_buying_power(detail_status):
                    locked_amount += detail.amount
            else:
                # If we can't get status but order is submitted, assume it might lock
                # (conservative approach - but this shouldn't happen normally)
                logger.warning(
                    f"Could not get status for Alpaca order {detail.alpaca_order_id}, "
                    "assuming it might lock buying power"
                )
                locked_amount += detail.amount

        return locked_amount
