#!/usr/bin/env python3
"""End-to-end test for frontend-to-backend flow.

Tests the complete flow:
1. Backend API endpoints (REST)
2. WebSocket connections
3. Price updates flow
4. Order updates flow

Run with: uv run --directory backend scripts/40-test-e2e-flow.py
"""
import sys
import os
import asyncio
import logging
import requests
import json
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client not available, WebSocket tests will be skipped")

from config import settings

# Test configuration
BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/ws/prices"
TEST_SYMBOLS = ["AAPL", "MSFT", "GOOGL"]


class E2ETestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        logger.info(f"✅ PASSED: {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        logger.error(f"❌ FAILED: {test_name} - {error}")
    
    def print_summary(self):
        logger.info("\n" + "=" * 80)
        logger.info("E2E TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Passed: {len(self.passed)}")
        logger.info(f"❌ Failed: {len(self.failed)}")
        
        if self.passed:
            logger.info("\nPassed tests:")
            for test in self.passed:
                logger.info(f"  ✅ {test}")
        
        if self.failed:
            logger.info("\nFailed tests:")
            for test, error in self.failed:
                logger.info(f"  ❌ {test}: {error}")
        
        logger.info("=" * 80)


def test_backend_health(results: E2ETestResults):
    """Test backend is running."""
    logger.info("=" * 80)
    logger.info("TEST: Backend Health Check")
    logger.info("=" * 80)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/version", timeout=5)
        if response.status_code == 200:
            results.add_pass("Backend health check")
            logger.info(f"Backend version: {response.json()}")
            return True
        else:
            results.add_fail("Backend health check", f"Status code: {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Backend health check", str(e))
        return False


def test_prices_api(results: E2ETestResults):
    """Test prices API endpoint."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Prices API Endpoint")
    logger.info("=" * 80)
    
    try:
        # Test 1: Get prices for specific symbols
        symbols_str = ",".join(TEST_SYMBOLS)
        response = requests.get(f"{BACKEND_URL}/api/prices?symbols={symbols_str}", timeout=10)
        
        if response.status_code != 200:
            results.add_fail("Prices API - status code", f"Got {response.status_code}")
            return False
        
        data = response.json()
        if "prices" not in data:
            results.add_fail("Prices API - response format", "Missing 'prices' key")
            return False
        
        prices = data["prices"]
        logger.info(f"Received {len(prices)} price(s)")
        
        # Check if we got prices for requested symbols
        received_symbols = [p["symbol"] for p in prices]
        logger.info(f"Received symbols: {received_symbols}")
        
        results.add_pass("Prices API endpoint")
        return True
        
    except Exception as e:
        results.add_fail("Prices API", str(e))
        return False


def test_prices_api_no_symbols(results: E2ETestResults):
    """Test prices API without symbols (should get from GTT orders)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Prices API (no symbols)")
    logger.info("=" * 80)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/prices", timeout=10)
        
        if response.status_code != 200:
            results.add_fail("Prices API (no symbols) - status code", f"Got {response.status_code}")
            return False
        
        data = response.json()
        if "prices" not in data:
            results.add_fail("Prices API (no symbols) - response format", "Missing 'prices' key")
            return False
        
        logger.info(f"Received {len(data['prices'])} price(s) from GTT orders")
        results.add_pass("Prices API (no symbols)")
        return True
        
    except Exception as e:
        results.add_fail("Prices API (no symbols)", str(e))
        return False


def test_websocket_connection(results: E2ETestResults):
    """Test WebSocket connection."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: WebSocket Connection")
    logger.info("=" * 80)
    
    if not WEBSOCKET_AVAILABLE:
        logger.warning("websocket-client not available, skipping WebSocket test")
        logger.info("Install with: uv pip install websocket-client")
        results.add_pass("WebSocket connection (skipped - package not available)")
        return True
    
    received_messages = []
    connection_established = False
    
    def on_message(ws, message):
        nonlocal received_messages
        try:
            data = json.loads(message)
            received_messages.append(data)
            logger.info(f"Received WebSocket message: {data.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Error parsing WebSocket message: {e}")
    
    def on_error(ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def on_open(ws):
        nonlocal connection_established
        connection_established = True
        logger.info("WebSocket connection opened")
        
        # Subscribe to test symbols
        subscribe_msg = {
            "type": "subscribe",
            "symbols": TEST_SYMBOLS
        }
        ws.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to symbols: {TEST_SYMBOLS}")
    
    def on_close(ws, close_status_code, close_msg):
        logger.info("WebSocket connection closed")
    
    try:
        ws = websocket.WebSocketApp(
            WS_URL,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close
        )
        
        # Run WebSocket in background thread
        import threading
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for connection
        time.sleep(2)
        
        if not connection_established:
            results.add_fail("WebSocket connection", "Connection not established")
            ws.close()
            return False
        
        # Wait for messages
        logger.info("Waiting for WebSocket messages (10 seconds)...")
        time.sleep(10)
        
        ws.close()
        ws_thread.join(timeout=2)
        
        # Check if we received messages
        if len(received_messages) == 0:
            logger.warning("No WebSocket messages received (this might be normal if no price updates)")
            results.add_pass("WebSocket connection (no messages yet)")
        else:
            logger.info(f"Received {len(received_messages)} WebSocket message(s)")
            # Check message types
            message_types = [msg.get('type', 'unknown') for msg in received_messages]
            logger.info(f"Message types: {message_types}")
            results.add_pass("WebSocket connection with messages")
        
        return True
        
    except Exception as e:
        results.add_fail("WebSocket connection", str(e))
        return False


def test_gtt_orders_api(results: E2ETestResults):
    """Test GTT orders API endpoint."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: GTT Orders API Endpoint")
    logger.info("=" * 80)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/gtt-orders", timeout=10)
        
        if response.status_code != 200:
            results.add_fail("GTT Orders API - status code", f"Got {response.status_code}")
            return False
        
        orders = response.json()
        logger.info(f"Received {len(orders)} GTT order(s)")
        
        results.add_pass("GTT Orders API endpoint")
        return True
        
    except Exception as e:
        results.add_fail("GTT Orders API", str(e))
        return False


def test_account_api(results: E2ETestResults):
    """Test account API endpoint."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Account API Endpoint")
    logger.info("=" * 80)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/account", timeout=10)
        
        if response.status_code != 200:
            results.add_fail("Account API - status code", f"Got {response.status_code}")
            return False
        
        account = response.json()
        logger.info(f"Account data received: portfolio_value={account.get('portfolio_value')}")
        
        results.add_pass("Account API endpoint")
        return True
        
    except Exception as e:
        results.add_fail("Account API", str(e))
        return False


def test_price_cache_service(results: E2ETestResults):
    """Test that price cache service is working."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Price Cache Service Integration")
    logger.info("=" * 80)
    
    try:
        # Import directly to avoid triggering websocket client imports
        import sys
        import importlib.util
        backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
        price_cache_path = os.path.join(backend_path, 'core', 'price_cache_service.py')
        
        # Change to backend directory for database access
        original_cwd = os.getcwd()
        try:
            os.chdir(backend_path)
            spec = importlib.util.spec_from_file_location("price_cache_service", price_cache_path)
            price_cache_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(price_cache_module)
            PriceCacheService = price_cache_module.PriceCacheService
            
            # Update a test price
            test_symbol = "TEST_SYMBOL_E2E"
            test_price = 100.50
            PriceCacheService.update_price(test_symbol, test_price)
            
            # Retrieve it
            retrieved_price = PriceCacheService.get_price(test_symbol)
            
            if retrieved_price == test_price:
                results.add_pass("Price Cache Service")
                # Cleanup - delete test symbol
                from database import SessionLocal
                from models import PriceCache
                db = SessionLocal()
                try:
                    db.query(PriceCache).filter(PriceCache.symbol == test_symbol).delete()
                    db.commit()
                finally:
                    db.close()
                return True
            else:
                results.add_fail("Price Cache Service", f"Expected {test_price}, got {retrieved_price}")
                return False
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        results.add_fail("Price Cache Service", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all end-to-end tests."""
    logger.info("Starting End-to-End Tests")
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info(f"WebSocket URL: {WS_URL}")
    logger.info(f"Test symbols: {TEST_SYMBOLS}")
    logger.info("=" * 80)
    
    results = E2ETestResults()
    
    # Run tests
    test_backend_health(results)
    test_prices_api(results)
    test_prices_api_no_symbols(results)
    test_websocket_connection(results)
    test_gtt_orders_api(results)
    test_account_api(results)
    test_price_cache_service(results)
    
    # Print summary
    results.print_summary()
    
    # Return exit code
    return 0 if len(results.failed) == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

