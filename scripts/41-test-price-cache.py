#!/usr/bin/env python3
"""Unit tests for PriceCacheService.

Tests the centralized price cache service to ensure it works correctly.

Run with: uv run --directory backend scripts/41-test-price-cache.py
"""
import sys
import os
import logging
from datetime import datetime, timedelta

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

# Set working directory to backend for database access
os.chdir(backend_path)

from database import SessionLocal, engine, Base
from core.price_cache_service import PriceCacheService
from models import PriceCache

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
        db.query(PriceCache).delete()
        db.commit()
    finally:
        db.close()


def test_update_single_price():
    """Test updating a single price."""
    logger.info("=" * 80)
    logger.info("TEST: Update Single Price")
    logger.info("=" * 80)
    
    cleanup_test_db()
    
    # Test 1: Update new price
    result = PriceCacheService.update_price("AAPL", 150.50)
    assert result is True, "Should return True on success"
    
    price = PriceCacheService.get_price("AAPL")
    assert price == 150.50, f"Expected 150.50, got {price}"
    logger.info("✅ Test 1 passed: New price created")
    
    # Test 2: Update existing price
    result = PriceCacheService.update_price("AAPL", 151.25)
    assert result is True, "Should return True on success"
    
    price = PriceCacheService.get_price("AAPL")
    assert price == 151.25, f"Expected 151.25, got {price}"
    logger.info("✅ Test 2 passed: Existing price updated")
    
    # Test 3: Case insensitive
    price = PriceCacheService.get_price("aapl")
    assert price == 151.25, "Should be case insensitive"
    logger.info("✅ Test 3 passed: Case insensitive")
    
    # Test 4: Invalid input
    result = PriceCacheService.update_price("", 100.0)
    assert result is False, "Should return False for empty symbol"
    
    result = PriceCacheService.update_price("MSFT", None)
    assert result is False, "Should return False for None price"
    logger.info("✅ Test 4 passed: Invalid input handling")
    
    logger.info("✅ All single price tests passed!\n")


def test_update_multiple_prices():
    """Test updating multiple prices."""
    logger.info("=" * 80)
    logger.info("TEST: Update Multiple Prices")
    logger.info("=" * 80)
    
    cleanup_test_db()
    
    # Test 1: Update multiple prices
    prices = {
        "AAPL": 150.50,
        "MSFT": 300.25,
        "GOOGL": 2500.75
    }
    
    count = PriceCacheService.update_prices(prices)
    assert count == 3, f"Expected 3 updates, got {count}"
    
    retrieved = PriceCacheService.get_prices(["AAPL", "MSFT", "GOOGL"])
    assert retrieved["AAPL"] == 150.50
    assert retrieved["MSFT"] == 300.25
    assert retrieved["GOOGL"] == 2500.75
    logger.info("✅ Test 1 passed: Multiple prices created")
    
    # Test 2: Update existing prices
    prices = {
        "AAPL": 151.00,
        "MSFT": 301.00,
        "TSLA": 200.00  # New symbol
    }
    
    count = PriceCacheService.update_prices(prices)
    assert count == 3, f"Expected 3 updates, got {count}"
    
    retrieved = PriceCacheService.get_prices(["AAPL", "MSFT", "TSLA"])
    assert retrieved["AAPL"] == 151.00
    assert retrieved["MSFT"] == 301.00
    assert retrieved["TSLA"] == 200.00
    logger.info("✅ Test 2 passed: Mixed update (existing + new)")
    
    # Test 3: Empty dict
    count = PriceCacheService.update_prices({})
    assert count == 0, "Should return 0 for empty dict"
    logger.info("✅ Test 3 passed: Empty dict handling")
    
    # Test 4: None prices filtered
    prices = {
        "AAPL": 152.00,
        "MSFT": None,  # Should be skipped
        "GOOGL": 2501.00
    }
    
    count = PriceCacheService.update_prices(prices)
    assert count == 2, f"Expected 2 updates (None filtered), got {count}"
    logger.info("✅ Test 4 passed: None prices filtered")
    
    logger.info("✅ All multiple price tests passed!\n")


def test_get_price_with_timestamp():
    """Test getting price with timestamp."""
    logger.info("=" * 80)
    logger.info("TEST: Get Price With Timestamp")
    logger.info("=" * 80)
    
    cleanup_test_db()
    
    # Test 1: Get price with timestamp
    test_timestamp = datetime.utcnow() - timedelta(minutes=5)
    PriceCacheService.update_price("AAPL", 150.50, test_timestamp)
    
    result = PriceCacheService.get_price_with_timestamp("AAPL")
    assert result is not None, "Should return price data"
    assert result["price"] == 150.50
    assert result["timestamp"] == test_timestamp
    logger.info("✅ Test 1 passed: Price with timestamp retrieved")
    
    # Test 2: Non-existent symbol
    result = PriceCacheService.get_price_with_timestamp("NONEXISTENT")
    assert result is None, "Should return None for non-existent symbol"
    logger.info("✅ Test 2 passed: Non-existent symbol handling")
    
    logger.info("✅ All timestamp tests passed!\n")


def test_edge_cases():
    """Test edge cases."""
    logger.info("=" * 80)
    logger.info("TEST: Edge Cases")
    logger.info("=" * 80)
    
    cleanup_test_db()
    
    # Test 1: Empty symbol list
    result = PriceCacheService.get_prices([])
    assert result == {}, "Should return empty dict"
    logger.info("✅ Test 1 passed: Empty symbol list")
    
    # Test 2: Non-existent symbols
    result = PriceCacheService.get_prices(["NONEXISTENT1", "NONEXISTENT2"])
    assert result["NONEXISTENT1"] is None
    assert result["NONEXISTENT2"] is None
    logger.info("✅ Test 2 passed: Non-existent symbols")
    
    # Test 3: Mixed existing and non-existent
    PriceCacheService.update_price("EXISTS", 100.0)
    result = PriceCacheService.get_prices(["EXISTS", "NOTEXISTS"])
    assert result["EXISTS"] == 100.0
    assert result["NOTEXISTS"] is None
    logger.info("✅ Test 3 passed: Mixed existing/non-existent")
    
    logger.info("✅ All edge case tests passed!\n")


def main():
    """Run all tests."""
    logger.info("Starting PriceCacheService Unit Tests")
    logger.info("=" * 80)
    
    try:
        setup_test_db()
        
        test_update_single_price()
        test_update_multiple_prices()
        test_get_price_with_timestamp()
        test_edge_cases()
        
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

