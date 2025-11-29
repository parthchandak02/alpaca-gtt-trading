#!/usr/bin/env python3
"""Unit tests for GTTOrderStatusService.

Tests the centralized GTT order status service to ensure it works correctly.

Run with: uv run --directory backend scripts/42-test-gtt-order-status.py
"""
import sys
import os
import logging
from datetime import datetime
from unittest.mock import Mock, MagicMock

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

# Set working directory to backend for database access
os.chdir(backend_path)

from database import SessionLocal, engine, Base
from core.gtt_order_status_service import GTTOrderStatusService
from models import GTTOrder, GTTOrderDetail, OrderStatus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_test_db():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)


def cleanup_test_db():
    """Clean up test data."""
    db = SessionLocal()
    try:
        db.query(GTTOrderDetail).delete()
        db.query(GTTOrder).delete()
        db.commit()
    finally:
        db.close()


def create_test_order(db, symbol: str = "AAPL", total_count: int = 3):
    """Create a test GTT order with details."""
    gtt_order = GTTOrder(
        symbol=symbol,
        status=OrderStatus.PENDING,
        total_count=total_count,
        filled_count=0,
        initial_trigger_price=150.0,  # Required field
        initial_quantity=10,  # Required field
        iterations=total_count,  # Required field
        increment_qty_multiplier=1.0,  # Required field
        decrement_price_multiplier=1.0  # Required field
    )
    db.add(gtt_order)
    db.flush()
    
    # Create order details
    for i in range(total_count):
        detail = GTTOrderDetail(
            gtt_order_id=gtt_order.id,
            order_index=i,  # Required field
            quantity=10,
            limit_price=150.0 + i,
            trigger_price=149.0 + i,
            amount=(150.0 + i) * 10,  # Required field: limit_price * quantity
            alpaca_order_id=None  # Will be set in tests
        )
        db.add(detail)
    
    db.commit()
    db.refresh(gtt_order)
    return gtt_order


def test_calculate_filled_count():
    """Test calculating filled count."""
    logger.info("=" * 80)
    logger.info("TEST: Calculate Filled Count")
    logger.info("=" * 80)
    
    cleanup_test_db()
    db = SessionLocal()
    
    try:
        # Create test order with 3 details
        gtt_order = create_test_order(db, "AAPL", 3)
        
        # Mock alpaca client and cache data
        mock_alpaca = Mock()
        
        # Mock get_alpaca_order_data to return filled status for first 2 orders
        def mock_get_order_data(db, client, order_id, force_refresh=False):
            if order_id == "order1":
                return {"status": "FILLED"}
            elif order_id == "order2":
                return {"status": "FILLED"}
            elif order_id == "order3":
                return {"status": "NEW"}
            return None
        
        # Set alpaca_order_ids
        details = db.query(GTTOrderDetail).filter(GTTOrderDetail.gtt_order_id == gtt_order.id).all()
        details[0].alpaca_order_id = "order1"
        details[1].alpaca_order_id = "order2"
        details[2].alpaca_order_id = "order3"
        db.commit()
        
        # Patch get_alpaca_order_data
        import alpaca_order_cache
        original_func = alpaca_order_cache.get_alpaca_order_data
        alpaca_order_cache.get_alpaca_order_data = mock_get_order_data
        
        try:
            filled_count = GTTOrderStatusService._calculate_filled_count(db, mock_alpaca, gtt_order)
            assert filled_count == 2, f"Expected 2 filled orders, got {filled_count}"
            logger.info("✅ Test passed: Filled count calculated correctly")
        finally:
            alpaca_order_cache.get_alpaca_order_data = original_func
            
    finally:
        db.close()
        cleanup_test_db()
    
    logger.info("✅ All calculate filled count tests passed!\n")


def test_update_order_status_from_alpaca_order():
    """Test updating order status from Alpaca order."""
    logger.info("=" * 80)
    logger.info("TEST: Update Order Status From Alpaca Order")
    logger.info("=" * 80)
    
    cleanup_test_db()
    db = SessionLocal()
    
    try:
        # Create test order
        gtt_order = create_test_order(db, "AAPL", 3)
        details = db.query(GTTOrderDetail).filter(GTTOrderDetail.gtt_order_id == gtt_order.id).all()
        
        # Set alpaca_order_ids
        details[0].alpaca_order_id = "order1"
        details[1].alpaca_order_id = "order2"
        details[2].alpaca_order_id = "order3"
        db.commit()
        
        # Mock alpaca client
        mock_alpaca = Mock()
        
        # Mock get_alpaca_order_data - all orders filled
        def mock_get_order_data(db, client, order_id, force_refresh=False):
            return {"status": "FILLED"}
        
        import alpaca_order_cache
        original_func = alpaca_order_cache.get_alpaca_order_data
        alpaca_order_cache.get_alpaca_order_data = mock_get_order_data
        
        try:
            # Update status
            updated_order = GTTOrderStatusService.update_order_status_from_alpaca_order(
                db, mock_alpaca, "order1"
            )
            
            assert updated_order is not None, "Should return updated order"
            assert updated_order.id == gtt_order.id
            assert updated_order.filled_count == 3, "All 3 orders should be filled"
            assert updated_order.status == OrderStatus.FILLED, "Status should be FILLED"
            logger.info("✅ Test 1 passed: Order status updated to FILLED")
            
            # Test with non-existent order
            updated_order = GTTOrderStatusService.update_order_status_from_alpaca_order(
                db, mock_alpaca, "nonexistent"
            )
            assert updated_order is None, "Should return None for non-existent order"
            logger.info("✅ Test 2 passed: Non-existent order handling")
            
        finally:
            alpaca_order_cache.get_alpaca_order_data = original_func
            
    finally:
        db.close()
        cleanup_test_db()
    
    logger.info("✅ All update order status tests passed!\n")


def test_update_order_statuses():
    """Test updating multiple order statuses."""
    logger.info("=" * 80)
    logger.info("TEST: Update Order Statuses")
    logger.info("=" * 80)
    
    cleanup_test_db()
    db = SessionLocal()
    
    try:
        # Create multiple test orders
        order1 = create_test_order(db, "AAPL", 2)
        order2 = create_test_order(db, "MSFT", 3)
        
        # Set alpaca_order_ids
        details1 = db.query(GTTOrderDetail).filter(GTTOrderDetail.gtt_order_id == order1.id).all()
        details2 = db.query(GTTOrderDetail).filter(GTTOrderDetail.gtt_order_id == order2.id).all()
        
        details1[0].alpaca_order_id = "order1_1"
        details1[1].alpaca_order_id = "order1_2"
        details2[0].alpaca_order_id = "order2_1"
        details2[1].alpaca_order_id = "order2_2"
        details2[2].alpaca_order_id = "order2_3"
        db.commit()
        
        # Mock alpaca client
        mock_alpaca = Mock()
        
        # Mock get_alpaca_order_data - order1: 1 filled, order2: 2 filled
        def mock_get_order_data(db, client, order_id, force_refresh=False):
            if order_id in ["order1_1"]:
                return {"status": "FILLED"}
            elif order_id in ["order2_1", "order2_2"]:
                return {"status": "FILLED"}
            return {"status": "NEW"}
        
        import alpaca_order_cache
        original_func = alpaca_order_cache.get_alpaca_order_data
        alpaca_order_cache.get_alpaca_order_data = mock_get_order_data
        
        try:
            # Update all orders
            count = GTTOrderStatusService.update_order_statuses(db, mock_alpaca, [order1, order2])
            
            assert count == 2, f"Expected 2 orders updated, got {count}"
            
            db.refresh(order1)
            db.refresh(order2)
            
            assert order1.filled_count == 1, "Order1 should have 1 filled"
            assert order1.status == OrderStatus.PARTIALLY_FILLED, "Order1 should be PARTIALLY_FILLED"
            
            assert order2.filled_count == 2, "Order2 should have 2 filled"
            assert order2.status == OrderStatus.PARTIALLY_FILLED, "Order2 should be PARTIALLY_FILLED"
            
            logger.info("✅ Test passed: Multiple orders updated correctly")
            
        finally:
            alpaca_order_cache.get_alpaca_order_data = original_func
            
    finally:
        db.close()
        cleanup_test_db()
    
    logger.info("✅ All update order statuses tests passed!\n")


def main():
    """Run all tests."""
    logger.info("Starting GTTOrderStatusService Unit Tests")
    logger.info("=" * 80)
    
    try:
        setup_test_db()
        
        test_calculate_filled_count()
        test_update_order_status_from_alpaca_order()
        test_update_order_statuses()
        
        cleanup_test_db()
        
        logger.info("=" * 80)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 80)
        return 0
        
    except AssertionError as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        cleanup_test_db()


if __name__ == "__main__":
    sys.exit(main())

