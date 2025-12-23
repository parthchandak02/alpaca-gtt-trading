#!/usr/bin/env python3
"""
Script to check if any GTT orders missed their triggers in the last few days.
Run this from the project root.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
import logging

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(root_dir, "backend")
sys.path.insert(0, backend_dir)

from database import SessionLocal
from models import GTTOrder, OrderStatus, GTTOrderDetail
from alpaca_client import AlpacaClient
from sqlalchemy.orm import Session

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_triggers")

try:
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
    console = Console()
except ImportError:
    console = None
    print("Rich library not found, using standard output.")

def check_missed_triggers(days: int = 30):
    """Check for missed triggers in the last N days."""
    try:
        db = SessionLocal()
        client = AlpacaClient()

        # Get all pending GTT orders
        # We want orders that are ACTIVE (PENDING status)
        orders = db.query(GTTOrder).filter(GTTOrder.status == OrderStatus.PENDING).all()
        
        if not orders:
            msg = "[yellow]No pending GTT orders found.[/yellow]"
            if console:
                console.print(msg)
            else:
                print("No pending GTT orders found.")
            return

        msg = f"[bold blue]Checking {len(orders)} pending GTT orders for missed triggers in the last {days} days...[/bold blue]"
        if console:
            console.print(msg)
        else:
            print(f"Checking {len(orders)} pending GTT orders for missed triggers in the last {days} days...")

        # Group by symbol to minimize API calls
        orders_by_symbol = {}
        for order in orders:
            if order.symbol not in orders_by_symbol:
                orders_by_symbol[order.symbol] = []
            orders_by_symbol[order.symbol].append(order)

        missed_triggers = []

        for symbol, symbol_orders in orders_by_symbol.items():
            # Fetch historical data
            # Use 'Minute' timeframe to catch intraday dips
            if console:
                console.print(f"Fetching history for [cyan]{symbol}[/cyan]...")
            else:
                print(f"Fetching history for {symbol}...")
                
            bars = client.get_historical_bars(symbol, days=days, timeframe="Minute")
            
            if not bars:
                logger.warning(f"No historical data found for {symbol}")
                continue

            # Find the global low for the period
            # bars is a list of dicts with 'low', 'timestamp'
            min_low = float('inf')
            min_low_time = None
            
            # We also want to check against specific timeframes if needed, 
            # but simply checking if ANY low < trigger is sufficient to say "we missed something"
            # However, we must ensure the low happened AFTER the order was created.
            
            for order in symbol_orders:
                # Ensure order created_at is offset-aware UTC
                order_created_utc = order.created_at
                if order_created_utc.tzinfo is None:
                    order_created_utc = order_created_utc.replace(tzinfo=timezone.utc)

                # Filter bars that happened AFTER order creation
                valid_bars = []
                for b in bars:
                    if not b.get('timestamp'):
                        continue
                    # Parse timestamp from Alpaca (ISO format with Z or offset)
                    try:
                        ts_str = b['timestamp']
                        # Handle Z suffix manually if needed, or rely on fromisoformat
                        if ts_str.endswith('Z'):
                            ts_str = ts_str[:-1] + '+00:00'
                        
                        ts = datetime.fromisoformat(ts_str)
                        
                        # Ensure ts is offset-aware UTC
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        
                        if ts > order_created_utc:
                            valid_bars.append(b)
                    except ValueError:
                        continue
                
                if not valid_bars:
                    continue

                # Get active (pending) details
                pending_details = [
                    d for d in order.order_details 
                    if not d.alpaca_order_id # Not submitted
                    # We don't have a status on detail, but if alpaca_order_id is None, it's pending locally
                ]
                
                for detail in pending_details:
                    trigger_price = detail.trigger_price
                    
                    # Check if any valid bar had a low < trigger_price
                    for bar in valid_bars:
                        low_price = bar['low']
                        if low_price <= trigger_price:
                            # Found a missed trigger!
                            missed_triggers.append({
                                "order_id": order.id,
                                "symbol": symbol,
                                "detail_id": detail.id,
                                "trigger_price": trigger_price,
                                "low_price": low_price,
                                "timestamp": bar['timestamp'],
                                "order_created": order.created_at
                            })
                            # Once we find one miss for a detail, we can break for that detail
                            # (or keep collecting to find the *first* miss, but any miss is bad)
                            break
        
        # Report results
        if not missed_triggers:
            msg = "[bold green]No missed triggers found! All active orders seem safe.[/bold green]"
            if console:
                console.print(msg)
            else:
                print("No missed triggers found! All active orders seem safe.")
        else:
            msg = f"[bold red]Found {len(missed_triggers)} missed triggers![/bold red]"
            if console:
                console.print(msg)
                
                table = Table(title="Missed Triggers")
                table.add_column("Order ID", justify="right", style="cyan")
                table.add_column("Symbol", style="magenta")
                table.add_column("Detail ID", justify="right")
                table.add_column("Trigger Price", justify="right", style="green")
                table.add_column("Lowest Price", justify="right", style="red")
                table.add_column("Missed At", style="yellow")
                table.add_column("Order Created", style="dim")

                for m in missed_triggers:
                    table.add_row(
                        str(m["order_id"]),
                        m["symbol"],
                        str(m["detail_id"]),
                        f"${m['trigger_price']:.2f}",
                        f"${m['low_price']:.2f}",
                        m["timestamp"],
                        str(m["order_created"])
                    )
                console.print(table)
            else:
                print(f"Found {len(missed_triggers)} missed triggers!")
                print("Order ID | Symbol | Detail ID | Trigger Price | Lowest Price | Missed At")
                for m in missed_triggers:
                    print(f"{m['order_id']} | {m['symbol']} | {m['detail_id']} | ${m['trigger_price']:.2f} | ${m['low_price']:.2f} | {m['timestamp']}")

    except Exception as e:
        logger.error(f"Error checking triggers: {e}", exc_info=True)
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    check_missed_triggers()

