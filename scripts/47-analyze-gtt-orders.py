#!/usr/bin/env python3
"""
Comprehensive GTT order analysis - checks why orders didn't trigger.
Checks for: missed triggers, safety check blocks, balance issues, validation failures.
Run from project root.
"""

import sys
import os
from datetime import datetime, timedelta
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(root_dir, "backend")
sys.path.insert(0, backend_dir)

from database import SessionLocal
from models import GTTOrder, OrderStatus, GTTOrderDetail, Activity, ActivityType
from alpaca_client import AlpacaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analyze_gtt")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

def analyze_gtt_orders(days: int = 30):
    """Comprehensive analysis of GTT orders."""
    db = SessionLocal()
    client = AlpacaClient()
    
    try:
        # Get account balance
        account = client.get_account()
        cash = float(account.get("cash", 0))
        buying_power = float(account.get("buying_power", 0))
        
        if HAS_RICH and console:
            console.print(f"\n[bold blue]GTT Order Analysis (Last {days} days)[/bold blue]\n")
            console.print(f"Account Balance: ${cash:,.2f} cash, ${buying_power:,.2f} buying power\n")
        else:
            print(f"\nGTT Order Analysis (Last {days} days)")
            print(f"Account Balance: ${cash:,.2f} cash, ${buying_power:,.2f} buying power\n")
        
        # Get all orders from period
        since = datetime.utcnow() - timedelta(days=days)
        all_orders = db.query(GTTOrder).filter(
            GTTOrder.created_at >= since
        ).order_by(GTTOrder.created_at.desc()).all()
        
        pending_orders = [o for o in all_orders if o.status == OrderStatus.PENDING]
        
        if not all_orders:
            msg = "No orders found in analysis period."
            if HAS_RICH and console:
                console.print(f"[yellow]{msg}[/yellow]")
            else:
                print(msg)
            return
        
        # Get current prices
        symbols = list(set([o.symbol for o in all_orders]))
        current_prices = client.get_latest_prices(symbols)
        
        # Analyze issues
        safety_blocked = []
        balance_issues = []
        should_have_triggered = []
        
        for order in all_orders:
            symbol = order.symbol
            current_price = current_prices.get(symbol)
            
            if not isinstance(current_price, (int, float)):
                continue
            
            # Get pending details
            pending_details = [d for d in order.order_details if not d.alpaca_order_id]
            
            for detail in pending_details:
                trigger_price = detail.trigger_price
                limit_price = detail.limit_price
                qty = detail.fractional_quantity if detail.fractional_quantity else detail.quantity
                order_value = qty * limit_price
                
                # Check if price dropped below trigger
                if current_price <= trigger_price:
                    drop_pct = (trigger_price - current_price) / trigger_price
                    
                    # Check safety check (50% crypto, 20% stocks)
                    from alpaca_client import is_crypto_symbol
                    threshold = 0.50 if is_crypto_symbol(symbol) else 0.20
                    
                    if drop_pct > threshold:
                        safety_blocked.append({
                            "order_id": order.id,
                            "symbol": symbol,
                            "detail_id": detail.id,
                            "trigger": trigger_price,
                            "current": current_price,
                            "drop_pct": drop_pct * 100,
                            "threshold": threshold * 100
                        })
                        continue
                    
                    # Check balance
                    if order_value > buying_power:
                        balance_issues.append({
                            "order_id": order.id,
                            "symbol": symbol,
                            "detail_id": detail.id,
                            "needed": order_value,
                            "available": buying_power
                        })
                        continue
                    
                    # Should have triggered
                    should_have_triggered.append({
                        "order_id": order.id,
                        "symbol": symbol,
                        "detail_id": detail.id,
                        "trigger": trigger_price,
                        "current": current_price,
                        "drop_pct": drop_pct * 100
                    })
        
        # Report results
        if HAS_RICH and console:
            if safety_blocked:
                console.print(Panel(f"[bold yellow]⚠️  {len(safety_blocked)} orders blocked by safety check[/bold yellow]", 
                                  title="Safety Check Blocks", border_style="yellow"))
                table = Table()
                table.add_column("Order ID", justify="right")
                table.add_column("Symbol")
                table.add_column("Trigger", justify="right")
                table.add_column("Current", justify="right")
                table.add_column("Drop %", justify="right", style="red")
                table.add_column("Threshold", justify="right")
                for item in safety_blocked:
                    table.add_row(
                        str(item["order_id"]),
                        item["symbol"],
                        f"${item['trigger']:.2f}",
                        f"${item['current']:.2f}",
                        f"{item['drop_pct']:.1f}%",
                        f"{item['threshold']:.0f}%"
                    )
                console.print(table)
                console.print()
            
            if balance_issues:
                console.print(Panel(f"[bold yellow]⚠️  {len(balance_issues)} orders need more balance[/bold yellow]", 
                                  title="Balance Issues", border_style="yellow"))
                table = Table()
                table.add_column("Order ID", justify="right")
                table.add_column("Symbol")
                table.add_column("Needed", justify="right")
                table.add_column("Available", justify="right")
                for item in balance_issues:
                    table.add_row(
                        str(item["order_id"]),
                        item["symbol"],
                        f"${item['needed']:.2f}",
                        f"${item['available']:.2f}"
                    )
                console.print(table)
                console.print()
            
            if should_have_triggered:
                console.print(Panel(f"[bold red]❌ {len(should_have_triggered)} orders should have triggered![/bold red]", 
                                  title="Missed Triggers", border_style="red"))
                table = Table()
                table.add_column("Order ID", justify="right")
                table.add_column("Symbol")
                table.add_column("Trigger", justify="right")
                table.add_column("Current", justify="right")
                table.add_column("Drop %", justify="right")
                for item in should_have_triggered:
                    table.add_row(
                        str(item["order_id"]),
                        item["symbol"],
                        f"${item['trigger']:.2f}",
                        f"${item['current']:.2f}",
                        f"{item['drop_pct']:.1f}%"
                    )
                console.print(table)
                console.print()
            
            # Summary
            console.print(f"[bold]Summary:[/bold]")
            console.print(f"  Total orders analyzed: {len(all_orders)}")
            console.print(f"  Pending orders: {len(pending_orders)}")
            console.print(f"  Safety check blocks: {len(safety_blocked)}")
            console.print(f"  Balance issues: {len(balance_issues)}")
            console.print(f"  Should have triggered: {len(should_have_triggered)}")
        else:
            # Standard output
            print(f"\nAnalysis Results:")
            print(f"  Total orders: {len(all_orders)}")
            print(f"  Pending: {len(pending_orders)}")
            if safety_blocked:
                print(f"\n⚠️  {len(safety_blocked)} orders blocked by safety check:")
                for item in safety_blocked:
                    print(f"  Order #{item['order_id']} {item['symbol']}: {item['drop_pct']:.1f}% drop (>{item['threshold']:.0f}% threshold)")
            if balance_issues:
                print(f"\n⚠️  {len(balance_issues)} orders need more balance:")
                for item in balance_issues:
                    print(f"  Order #{item['order_id']} {item['symbol']}: Need ${item['needed']:.2f}, Have ${item['available']:.2f}")
            if should_have_triggered:
                print(f"\n❌ {len(should_have_triggered)} orders should have triggered:")
                for item in should_have_triggered:
                    print(f"  Order #{item['order_id']} {item['symbol']}: {item['drop_pct']:.1f}% drop")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        if HAS_RICH and console:
            console.print(f"[bold red]Error: {e}[/bold red]")
        else:
            print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze GTT orders")
    parser.add_argument("--days", type=int, default=30, help="Number of days to analyze (default: 30)")
    args = parser.parse_args()
    analyze_gtt_orders(args.days)

