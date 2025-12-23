#!/usr/bin/env python3
"""Check for expired GTT orders in the database."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import SessionLocal
from models import GTTOrder, OrderStatus, Activity, ActivityType
from datetime import datetime

def check_expired_orders():
    """Check for expired orders and display details."""
    db = SessionLocal()
    
    try:
        # Get all expired orders
        expired_orders = db.query(GTTOrder).filter(
            GTTOrder.status == OrderStatus.EXPIRED
        ).order_by(GTTOrder.updated_at.desc()).all()
        
        if not expired_orders:
            print("✅ No expired orders found.")
            return
        
        print(f"\n🔍 Found {len(expired_orders)} expired order(s):\n")
        print("=" * 100)
        
        for order in expired_orders:
            # Get the corporate action activity if it exists
            corporate_action = db.query(Activity).filter(
                Activity.gtt_order_id == order.id,
                Activity.activity_type == ActivityType.CORPORATE_ACTION_EXPIRED
            ).first()
            
            print(f"\n📋 Order ID: {order.id}")
            print(f"   Symbol: {order.symbol}")
            print(f"   Status: {order.status.value}")
            print(f"   Created: {order.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   Updated: {order.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   Initial Trigger Price: ${order.initial_trigger_price:.2f}")
            print(f"   Initial Quantity: {order.initial_quantity}")
            print(f"   Total Value: ${order.total_value:.2f}")
            print(f"   Filled Count: {order.filled_count}/{order.total_count}")
            
            if corporate_action:
                print(f"\n   ⚠️  Corporate Action Expiration:")
                print(f"      Reason: {corporate_action.description}")
                if corporate_action.notes:
                    print(f"      Details: {corporate_action.notes}")
                print(f"      Date: {corporate_action.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Count order details
            pending_details = [d for d in order.order_details if not d.alpaca_order_id]
            linked_details = [d for d in order.order_details if d.alpaca_order_id]
            
            print(f"\n   Order Details:")
            print(f"      Total: {len(order.order_details)}")
            print(f"      Pending (not linked): {len(pending_details)}")
            print(f"      Linked to Alpaca orders: {len(linked_details)}")
            
            print("-" * 100)
        
        print(f"\n📊 Summary: {len(expired_orders)} expired order(s) found")
        
    except Exception as e:
        print(f"❌ Error checking expired orders: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_expired_orders()

