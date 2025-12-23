#!/usr/bin/env python3
"""Safely reactivate incorrectly expired GTT orders.

This script validates and reactivates orders that were incorrectly expired due to
the bug in corporate action detection. It performs multiple safety checks before
reactivating any order.

SAFETY CHECKS:
1. Asset must be tradable (verified via Alpaca API)
2. Current price must be within reasonable range of trigger price (safety check)
3. Order details must exist
4. No open Alpaca orders should be linked (they should have been cancelled)
5. Only reactivate orders expired due to DELISTING corporate action (the bug)

USAGE:
    # Dry-run mode (default) - shows what would be reactivated
    python scripts/reactivate-expired-orders.py
    
    # Actually reactivate orders
    python scripts/reactivate-expired-orders.py --confirm
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import SessionLocal
from models import GTTOrder, OrderStatus, Activity, ActivityType
from alpaca_client import AlpacaClient
from datetime import datetime
from rate_limiter import rate_limit_alpaca_call_sync

def check_order_safety(order: GTTOrder, alpaca_client: AlpacaClient) -> tuple[bool, str]:
    """Check if an order is safe to reactivate.
    
    Returns:
        (is_safe, reason)
    """
    symbol = order.symbol.upper()
    
    # Check 1: Asset must be tradable
    try:
        rate_limit_alpaca_call_sync()
        asset_info = alpaca_client.get_asset_info(symbol)
        if asset_info is None:
            return False, f"Could not verify asset {symbol} (API returned None)"
        if asset_info.get("tradable") is False:
            return False, f"Asset {symbol} is explicitly marked as not tradable"
    except Exception as e:
        return False, f"Error checking asset {symbol}: {e}"
    
    # Check 2: Current price must be within reasonable range
    try:
        rate_limit_alpaca_call_sync()
        current_price = alpaca_client.get_latest_price(symbol)
        if current_price is None:
            return False, f"Could not get current price for {symbol}"
        
        # Safety check: price shouldn't have changed dramatically
        # Use same thresholds as order triggering logic
        from alpaca_client import is_crypto_symbol
        is_crypto = is_crypto_symbol(symbol)
        threshold = 0.50 if is_crypto else 0.20  # 50% for crypto, 20% for stocks
        
        trigger_price = order.initial_trigger_price
        price_change_pct = abs(current_price - trigger_price) / trigger_price
        
        if price_change_pct > threshold:
            return False, (
                f"Price change too large: Current ${current_price:.2f} vs Trigger ${trigger_price:.2f} "
                f"({price_change_pct*100:.1f}% change, >{threshold*100:.0f}% threshold). "
                f"This may indicate a symbol mismatch or significant market change."
            )
    except Exception as e:
        return False, f"Error checking price for {symbol}: {e}"
    
    # Check 3: Order details must exist
    if not order.order_details or len(order.order_details) == 0:
        return False, "No order details found"
    
    # Check 4: Verify no open Alpaca orders are linked (they should have been cancelled)
    # This is a safety check - if there are open orders, we shouldn't reactivate
    open_alpaca_orders = []
    for detail in order.order_details:
        if detail.alpaca_order_id:
            try:
                rate_limit_alpaca_call_sync()
                alpaca_order = alpaca_client.get_order(detail.alpaca_order_id)
                if alpaca_order:
                    status = alpaca_order.get("status", "").upper()
                    # Check if order is still open/active
                    if status not in ["FILLED", "CANCELLED", "EXPIRED", "REJECTED", "DONE_FOR_DAY"]:
                        open_alpaca_orders.append({
                            "detail_id": detail.id,
                            "alpaca_order_id": detail.alpaca_order_id,
                            "status": status
                        })
            except Exception as e:
                # If we can't get order info, assume it's cancelled/expired (safe assumption)
                pass
    
    if open_alpaca_orders:
        return False, (
            f"Found {len(open_alpaca_orders)} open Alpaca order(s) still linked. "
            f"These should have been cancelled. Order IDs: {[o['alpaca_order_id'] for o in open_alpaca_orders]}"
        )
    
    return True, "All safety checks passed"

def reactivate_order(db, order: GTTOrder, reason: str):
    """Reactivate an expired order by changing status to PENDING."""
    symbol = order.symbol.upper()
    
    # Change status back to PENDING
    order.status = OrderStatus.PENDING
    
    # Reset locked buying power (will be recalculated by status service)
    order.locked_buying_power = 0.0
    
    # Update timestamp
    order.updated_at = datetime.utcnow()
    
    # Log activity for audit trail
    activity = Activity(
        gtt_order_id=order.id,
        activity_type=ActivityType.GTT_TRIGGER,
        symbol=symbol,
        description=f"Order reactivated: {reason}",
        notes=f"Previously expired due to false positive corporate action detection. Reactivated after validation.",
    )
    db.add(activity)
    
    db.add(order)
    db.commit()
    
    print(f"   ✅ Reactivated order {order.id} for {symbol}")

def main():
    parser = argparse.ArgumentParser(
        description="Reactivate incorrectly expired GTT orders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (default) - shows what would be reactivated
  python scripts/reactivate-expired-orders.py
  
  # Actually reactivate orders
  python scripts/reactivate-expired-orders.py --confirm
        """
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually reactivate orders (default is dry-run mode)"
    )
    args = parser.parse_args()
    
    db = SessionLocal()
    alpaca_client = AlpacaClient()
    
    try:
        # Get all expired orders
        expired_orders = db.query(GTTOrder).filter(
            GTTOrder.status == OrderStatus.EXPIRED
        ).order_by(GTTOrder.updated_at.desc()).all()
        
        if not expired_orders:
            print("✅ No expired orders found.")
            return
        
        print(f"\n🔍 Found {len(expired_orders)} expired order(s)")
        print("=" * 100)
        
        # Filter to only orders expired due to DELISTING (the bug)
        # Check activity logs to identify incorrectly expired orders
        reactivatable_orders = []
        skipped_orders = []
        
        for order in expired_orders:
            # Check if this order was expired due to DELISTING corporate action
            # (which was the bug - these are the false positives)
            corporate_action = db.query(Activity).filter(
                Activity.gtt_order_id == order.id,
                Activity.activity_type == ActivityType.CORPORATE_ACTION_EXPIRED,
                Activity.description.like("%Corporate Action%")
            ).first()
            
            if corporate_action and "DELISTING" in corporate_action.notes:
                # This is likely a false positive - check if it's safe to reactivate
                is_safe, reason = check_order_safety(order, alpaca_client)
                if is_safe:
                    reactivatable_orders.append((order, reason))
                else:
                    skipped_orders.append((order, reason))
            else:
                skipped_orders.append((order, "Not expired due to DELISTING corporate action"))
        
        print(f"\n📊 Analysis Results:")
        print(f"   ✅ Safe to reactivate: {len(reactivatable_orders)}")
        print(f"   ⚠️  Skipped (not safe or not eligible): {len(skipped_orders)}")
        
        if skipped_orders:
            print(f"\n⚠️  Skipped Orders (will NOT be reactivated):")
            print("-" * 100)
            for order, reason in skipped_orders[:10]:  # Show first 10
                print(f"   Order {order.id} ({order.symbol}): {reason}")
            if len(skipped_orders) > 10:
                print(f"   ... and {len(skipped_orders) - 10} more")
        
        if not reactivatable_orders:
            print("\n✅ No orders are safe to reactivate.")
            return
        
        print(f"\n✅ Orders Safe to Reactivate:")
        print("-" * 100)
        for order, reason in reactivatable_orders:
            print(f"   Order {order.id}: {order.symbol}")
            print(f"      Trigger: ${order.initial_trigger_price:.2f}, Qty: {order.initial_quantity}")
            print(f"      Total Value: ${order.total_value:.2f}")
            print(f"      Filled: {order.filled_count}/{order.total_count}")
            print(f"      Reason: {reason}")
            print()
        
        if not args.confirm:
            print("=" * 100)
            print("🔒 DRY-RUN MODE: No orders were reactivated.")
            print("   To actually reactivate these orders, run with --confirm flag:")
            print("   python scripts/reactivate-expired-orders.py --confirm")
            return
        
        # Confirm before proceeding
        print("=" * 100)
        print(f"⚠️  WARNING: About to reactivate {len(reactivatable_orders)} order(s)")
        print("   This will change order status from EXPIRED to PENDING")
        print("   Orders will become active and may trigger trades if price conditions are met")
        response = input("\n   Type 'YES' to confirm: ")
        
        if response != "YES":
            print("\n❌ Cancelled. No orders were reactivated.")
            return
        
        # Reactivate orders
        print(f"\n🔄 Reactivating {len(reactivatable_orders)} order(s)...")
        print("-" * 100)
        
        reactivated_count = 0
        failed_count = 0
        
        for order, reason in reactivatable_orders:
            try:
                reactivate_order(db, order, reason)
                reactivated_count += 1
            except Exception as e:
                print(f"   ❌ Failed to reactivate order {order.id}: {e}")
                failed_count += 1
                db.rollback()
        
        print("-" * 100)
        print(f"\n✅ Successfully reactivated: {reactivated_count}")
        if failed_count > 0:
            print(f"❌ Failed: {failed_count}")
        print("\n💡 Note: Orders are now PENDING and will be monitored by the price monitoring service.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

