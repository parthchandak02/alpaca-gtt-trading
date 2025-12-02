#!/usr/bin/env python3
"""Create a test market order for TSLA for testing purposes."""
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from alpaca_client import AlpacaClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_order():
    """Create a test market buy order for TSLA."""
    try:
        client = AlpacaClient()
        
        # Get current price to calculate quantity
        current_price = client.get_latest_price("TSLA")
        if not current_price:
            logger.error("Could not get current price for TSLA")
            return
        
        logger.info(f"Current TSLA price: ${current_price:.2f}")
        
        # Create a small order (1 share or $100 worth, whichever is less)
        quantity = max(1, int(100 / current_price))
        
        logger.info(f"Creating market buy order for TSLA: {quantity} shares")
        
        # Create market order
        market_order = MarketOrderRequest(
            symbol="TSLA",
            qty=quantity,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        
        order = client.trading_client.submit_order(order_data=market_order)
        
        logger.info(f"✅ Order submitted successfully!")
        logger.info(f"   Order ID: {order.id}")
        logger.info(f"   Symbol: {order.symbol}")
        logger.info(f"   Quantity: {order.qty}")
        logger.info(f"   Side: {order.side}")
        logger.info(f"   Status: {order.status}")
        logger.info(f"   Order Type: {order.order_type}")
        
        print(f"\n🎉 Test order created!")
        print(f"Order ID: {order.id}")
        print(f"Check your Alpaca dashboard or use: GET /api/orders?status=filled&limit=10")
        
    except Exception as e:
        logger.error(f"Error creating test order: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    create_test_order()

