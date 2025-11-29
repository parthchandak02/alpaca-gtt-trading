#!/usr/bin/env python3
"""Script to delete all GTT orders from the database."""

import os
import sys

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from config import settings
from database import SessionLocal
from models import Activity, GTTOrder, GTTOrderDetail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def delete_all_orders():
    """Delete all GTT orders from the database."""
    db = SessionLocal()
    try:
        # Count orders before deletion
        order_count = db.query(GTTOrder).count()
        detail_count = db.query(GTTOrderDetail).count()
        activity_count = db.query(Activity).count()

        logger.info("Current database state:")
        logger.info(f"  - GTT Orders: {order_count}")
        logger.info(f"  - Order Details: {detail_count}")
        logger.info(f"  - Activities: {activity_count}")
        logger.info(f"  - Database: {settings.database_url}")

        if order_count == 0:
            logger.info("No orders to delete. Database is already empty.")
            return

        # Confirm deletion
        print(f"\n⚠️  WARNING: This will delete ALL {order_count} GTT orders!")
        print(
            f"   This will also delete {detail_count} order details and {activity_count} activities."
        )
        response = input("   Type 'DELETE ALL' to confirm: ")

        if response != "DELETE ALL":
            logger.info("Deletion cancelled.")
            return

        # Delete all activities first (they reference orders)
        deleted_activities = db.query(Activity).delete()
        logger.info(f"Deleted {deleted_activities} activities")

        # Delete all order details (cascade should handle this, but being explicit)
        deleted_details = db.query(GTTOrderDetail).delete()
        logger.info(f"Deleted {deleted_details} order details")

        # Delete all GTT orders (cascade will handle order_details, but we already deleted them)
        deleted_orders = db.query(GTTOrder).delete()
        logger.info(f"Deleted {deleted_orders} GTT orders")

        # Commit the deletion
        db.commit()

        logger.info("\n✅ Successfully deleted all orders!")
        logger.info(f"   - Deleted {deleted_orders} GTT orders")
        logger.info(f"   - Deleted {deleted_details} order details")
        logger.info(f"   - Deleted {deleted_activities} activities")

    except Exception as e:
        logger.error(f"Error deleting orders: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    delete_all_orders()
