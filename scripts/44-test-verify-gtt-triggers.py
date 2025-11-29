#!/usr/bin/env python3
"""Verify GTT trigger logic and check if orders are being triggered correctly.

This script checks:
1. Pending GTT orders and their trigger prices
2. Current market prices
3. Which orders should trigger (price <= trigger_price)
4. Recent trigger activity from logs
5. Background task status
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from database import SessionLocal
from models import GTTOrder, GTTOrderDetail, OrderStatus, PriceCache, Activity, ActivityType
from alpaca_client import AlpacaClient
from datetime import datetime, timedelta

# Simple console output without rich
def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def print_section(text):
    print(f"\n{text}")
    print("-" * 80)

def check_pending_orders():
    """Check pending GTT orders and their trigger status."""
    db = SessionLocal()
    try:
        # Get all pending GTT orders
        pending_orders = db.query(GTTOrder).filter(
            GTTOrder.status == OrderStatus.PENDING
        ).all()
        
        if not pending_orders:
            print("\n⚠️  No pending GTT orders found")
            return
        
        print(f"\n✓ Found {len(pending_orders)} pending GTT order(s)\n")
        
        # Get unique symbols
        symbols = list(set([order.symbol for order in pending_orders]))
        
        # Fetch current prices
        print(f"Fetching current prices for: {', '.join(symbols)}")
        alpaca = AlpacaClient()
        prices = alpaca.get_latest_prices(symbols)
        
        orders_ready_to_trigger = []
        
        for gtt_order in pending_orders:
            symbol = gtt_order.symbol
            current_price = prices.get(symbol)
            
            if not current_price:
                print(f"  Order #{gtt_order.id} {symbol}: N/A (no price)")
                continue
            
            # Get pending order details (not linked to Alpaca orders)
            pending_details = [
                detail for detail in gtt_order.order_details
                if not detail.is_manually_linked and not detail.alpaca_order_id
            ]
            
            if not pending_details:
                print(f"  Order #{gtt_order.id} {symbol}: ${current_price:.2f} - All Triggered")
                continue
            
            # Sort by order_index
            pending_details.sort(key=lambda d: d.order_index)
            first_trigger = pending_details[0].trigger_price
            
            # Check trigger condition
            if current_price <= first_trigger:
                status = "✓ READY"
                # Check which details should trigger
                for detail in pending_details:
                    if current_price <= detail.trigger_price:
                        orders_ready_to_trigger.append({
                            "order_id": gtt_order.id,
                            "symbol": symbol,
                            "detail_id": detail.id,
                            "current_price": current_price,
                            "trigger_price": detail.trigger_price,
                            "limit_price": detail.limit_price,
                            "quantity": detail.fractional_quantity if detail.fractional_quantity else detail.quantity
                        })
            else:
                status = "⏸️  WAITING"
            
            print(f"  Order #{gtt_order.id} {symbol}: Current=${current_price:.2f}, FirstTrigger=${first_trigger:.2f}, Status={status}, Pending={len(pending_details)}")
        
        if orders_ready_to_trigger:
            print(f"\n⚠️  Found {len(orders_ready_to_trigger)} order detail(s) that SHOULD trigger!")
            print("\nOrders Ready to Trigger:")
            print("-" * 80)
            print(f"{'Order ID':<10} {'Symbol':<10} {'Detail ID':<12} {'Current':<12} {'Trigger':<12} {'Limit':<12} {'Qty':<10}")
            print("-" * 80)
            for order in orders_ready_to_trigger:
                print(f"{order['order_id']:<10} {order['symbol']:<10} {order['detail_id']:<12} ${order['current_price']:<11.2f} ${order['trigger_price']:<11.2f} ${order['limit_price']:<11.2f} {order['quantity']:<10}")
            print("\n⚠️  These orders should trigger on the next price check cycle (every 60s)")
        else:
            print("\n✓ No orders ready to trigger - all prices above trigger points")
        
    finally:
        db.close()

def check_recent_activity():
    """Check recent trigger activity from database."""
    db = SessionLocal()
    try:
        # Get recent ORDER_PLACED activities (last 24 hours)
        since = datetime.utcnow() - timedelta(hours=24)
        recent_triggers = db.query(Activity).filter(
            Activity.activity_type == ActivityType.ORDER_PLACED,
            Activity.created_at >= since
        ).order_by(Activity.created_at.desc()).limit(10).all()
        
        if not recent_triggers:
            print("\n⚠️  No trigger activity in the last 24 hours")
            return
        
        print(f"\n✓ Found {len(recent_triggers)} recent trigger(s) in last 24 hours\n")
        print("Recent Trigger Activity:")
        print("-" * 80)
        print(f"{'Time':<20} {'Order ID':<10} {'Symbol':<10} {'Description':<40} {'Price':<12} {'Qty':<10}")
        print("-" * 80)
        
        for activity in recent_triggers:
            print(f"{activity.created_at.strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{str(activity.gtt_order_id) if activity.gtt_order_id else 'N/A':<10} "
                  f"{activity.symbol:<10} "
                  f"{activity.description[:40]:<40} "
                  f"{('$' + str(activity.price)) if activity.price else 'N/A':<12} "
                  f"{str(activity.quantity) if activity.quantity else 'N/A':<10}")
        
    finally:
        db.close()

def check_background_task():
    """Check if background task is running by looking at recent logs."""
    log_file = Path(__file__).parent.parent / "logs" / "backend.log"
    
    if not log_file.exists():
        print("\n⚠️  Log file not found")
        return
    
    print("\nChecking recent background task activity...")
    
    # Read last 100 lines of log
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        # Look for price monitoring cycle messages
        price_cycles = []
        for line in recent_lines:
            if "PRICE MONITORING CYCLE STARTED" in line or ("Monitoring" in line and "GTT order" in line):
                price_cycles.append(line.strip())
        
        if price_cycles:
            print(f"✓ Found {len(price_cycles)} recent price monitoring cycle(s)")
            print("Most recent cycles:")
            for cycle in price_cycles[-3:]:
                print(f"  {cycle[:100]}...")
        else:
            print("⚠️  No recent price monitoring cycles found in logs")
            print("   Background task may not be running")
    
    except Exception as e:
        print(f"Error reading log file: {e}")

def verify_trigger_logic():
    """Verify the trigger logic is correct."""
    print("\nVerifying trigger logic...")
    
    # The trigger condition should be: current_price <= trigger_price
    print("✓ Trigger condition: current_price <= trigger_price")
    print("✓ This means orders trigger when price goes BELOW or EQUAL to trigger price")
    
    db = SessionLocal()
    try:
        # Check if there are any orders with price exactly at trigger
        pending_orders = db.query(GTTOrder).filter(
            GTTOrder.status == OrderStatus.PENDING
        ).all()
        
        if pending_orders:
            symbols = list(set([order.symbol for order in pending_orders]))
            alpaca = AlpacaClient()
            prices = alpaca.get_latest_prices(symbols)
            
            for gtt_order in pending_orders:
                current_price = prices.get(gtt_order.symbol)
                if current_price:
                    pending_details = [
                        detail for detail in gtt_order.order_details
                        if not detail.is_manually_linked and not detail.alpaca_order_id
                    ]
                    for detail in pending_details:
                        if current_price <= detail.trigger_price:
                            print(f"\n⚠️  Order #{gtt_order.id} Detail #{detail.id}:")
                            print(f"   Current: ${current_price:.2f} <= Trigger: ${detail.trigger_price:.2f}")
                            print(f"   Should trigger on next cycle!")
    finally:
        db.close()

def main():
    """Main verification function."""
    print_header("GTT Trigger Verification")
    print("Checking if stocks are being triggered when prices go below trigger points")
    
    # Check pending orders and trigger status
    check_pending_orders()
    
    # Check recent activity
    check_recent_activity()
    
    # Check background task
    check_background_task()
    
    # Verify trigger logic
    verify_trigger_logic()
    
    print("\n✓ Verification complete!")
    print("\nNote: Background task checks prices every 60 seconds")
    print("Orders ready to trigger will be placed on the next cycle")

if __name__ == "__main__":
    main()

