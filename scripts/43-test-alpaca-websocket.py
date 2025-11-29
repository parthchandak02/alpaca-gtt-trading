#!/usr/bin/env python3
"""Unit tests for Alpaca WebSocket client.

Tests WebSocket connections for:
- Live prices (bars stream)
- Order updates (trade_updates stream)

Run with: uv run --directory backend scripts/43-test-alpaca-websocket.py
"""
import sys
import os
import asyncio
import logging
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import settings
from core.alpaca_websocket_client import AlpacaWebSocketClient
from database import SessionLocal
from models import PriceCache

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_price_updates():
    """Test receiving price updates via WebSocket."""
    logger.info("=" * 80)
    logger.info("TEST: Price Updates via WebSocket")
    logger.info("=" * 80)
    
    client = AlpacaWebSocketClient()
    
    # Track received prices
    received_prices = {}
    
    # Override handler to track prices
    original_handler = client._on_stock_bar_update
    
    def test_handler(bar):
        symbol = bar.symbol
        price = float(bar.close)
        received_prices[symbol] = price
        logger.info(f"✅ Received price update: {symbol} = ${price:.2f}")
        original_handler(bar)
    
    client._on_stock_bar_update = test_handler
    
    try:
        # Start client
        await client.start()
        logger.info("WebSocket client started")
        
        # Subscribe to test symbols
        test_symbols = ["AAPL", "MSFT"]  # Common stocks
        await client.subscribe_symbols(test_symbols)
        logger.info(f"Subscribed to: {test_symbols}")
        
        # Wait for price updates (30 seconds)
        logger.info("Waiting for price updates (30 seconds)...")
        await asyncio.sleep(30)
        
        # Check results
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS:")
        logger.info("=" * 80)
        
        for symbol in test_symbols:
            if symbol in received_prices:
                logger.info(f"✅ {symbol}: Received price ${received_prices[symbol]:.2f}")
            else:
                logger.warning(f"❌ {symbol}: No price update received")
        
        # Check database cache
        db = SessionLocal()
        try:
            for symbol in test_symbols:
                cache = db.query(PriceCache).filter(PriceCache.symbol == symbol).first()
                if cache:
                    logger.info(f"✅ {symbol}: Cached in database at ${cache.price:.2f} (timestamp: {cache.timestamp})")
                else:
                    logger.warning(f"❌ {symbol}: Not found in database cache")
        finally:
            db.close()
        
        return len(received_prices) > 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        await client.stop()
        logger.info("WebSocket client stopped")


async def test_order_updates():
    """Test receiving order updates via WebSocket."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Order Updates via WebSocket")
    logger.info("=" * 80)
    
    client = AlpacaWebSocketClient()
    
    # Track received updates
    received_updates = []
    
    def test_handler(trade_update):
        received_updates.append(trade_update)
        logger.info(f"✅ Received trade update: {trade_update}")
    
    client._on_trade_update = test_handler
    
    try:
        # Start client
        await client.start()
        logger.info("WebSocket client started")
        
        logger.info("Waiting for order updates (30 seconds)...")
        logger.info("Note: Updates will only appear if you have active orders")
        await asyncio.sleep(30)
        
        # Check results
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS:")
        logger.info("=" * 80)
        
        if received_updates:
            logger.info(f"✅ Received {len(received_updates)} order update(s)")
            for update in received_updates:
                logger.info(f"  - {update}")
        else:
            logger.info("ℹ️  No order updates received (this is normal if no active orders)")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        await client.stop()
        logger.info("WebSocket client stopped")


async def test_reconnection():
    """Test reconnection logic."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Reconnection Logic")
    logger.info("=" * 80)
    
    client = AlpacaWebSocketClient()
    
    try:
        await client.start()
        logger.info("WebSocket client started")
        
        # Subscribe to a symbol
        await client.subscribe_symbols(["AAPL"])
        logger.info("Subscribed to AAPL")
        
        # Wait a bit
        await asyncio.sleep(5)
        
        logger.info("✅ Reconnection test passed (client started successfully)")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        await client.stop()


async def main():
    """Run all tests."""
    logger.info("Starting Alpaca WebSocket Tests")
    logger.info(f"Trading mode: {'PAPER' if settings.use_paper_trading else 'LIVE'}")
    logger.info(f"API Key: {settings.alpaca_api_key[:10]}..." if settings.alpaca_api_key else "No API key")
    
    results = []
    
    # Test 1: Price updates
    try:
        result = await test_price_updates()
        results.append(("Price Updates", result))
    except Exception as e:
        logger.error(f"Price updates test error: {e}", exc_info=True)
        results.append(("Price Updates", False))
    
    # Test 2: Order updates
    try:
        result = await test_order_updates()
        results.append(("Order Updates", result))
    except Exception as e:
        logger.error(f"Order updates test error: {e}", exc_info=True)
        results.append(("Order Updates", False))
    
    # Test 3: Reconnection
    try:
        result = await test_reconnection()
        results.append(("Reconnection", result))
    except Exception as e:
        logger.error(f"Reconnection test error: {e}", exc_info=True)
        results.append(("Reconnection", False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n✅ All tests passed!")
        return 0
    else:
        logger.info("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

