"""Daily summary service for generating and sending trading summaries.

This service generates enhanced daily summaries including:
- GTT orders status per symbol
- Today's order executions with details  
- Pending orders waiting to trigger
- Account overview and P/L
- Failed orders alert (if any)

Called automatically at market close from background_tasks.py
"""

import logging
from collections import defaultdict
from datetime import datetime

from alpaca_client import AlpacaClient
from database import get_db
from models import Activity, ActivityType, GTTOrder, OrderStatus
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def format_currency(value: float) -> str:
    """Format a value as currency."""
    if value >= 0:
        return f"${value:,.2f}"
    return f"-${abs(value):,.2f}"


def format_percent(value: float) -> str:
    """Format a value as percentage."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def format_price(value: float) -> str:
    """Format price - use more decimals for small values (crypto), fewer for large."""
    if value >= 100:
        return f"${value:,.2f}"
    elif value >= 1:
        return f"${value:.2f}"
    else:
        return f"${value:.4f}"


def get_account_summary(alpaca_client: AlpacaClient) -> dict:
    """Get account summary from Alpaca."""
    try:
        return alpaca_client.get_account()
    except Exception as e:
        logger.error(f"Error fetching account: {e}")
        return {}


def get_gtt_orders_summary(db: Session) -> dict:
    """Get GTT orders summary grouped by symbol.
    
    Returns a dict with:
    - orders_by_symbol: dict mapping symbol -> order info
    - total_locked_bp: total locked buying power
    - total_symbols: count of symbols with active GTT orders
    - filled_today_by_symbol: orders filled today grouped by symbol
    - filled_today_count: count of orders filled today
    - filled_today_amount: total amount of orders filled today
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get all non-terminal GTT orders
    active_orders = (
        db.query(GTTOrder)
        .filter(GTTOrder.status.in_([
            OrderStatus.PENDING,
            OrderStatus.PARTIALLY_FILLED,
        ]))
        .all()
    )
    
    # Get orders filled today
    filled_today_activities = (
        db.query(Activity)
        .filter(
            Activity.activity_type == ActivityType.ORDER_FILLED,
            Activity.created_at >= today_start,
        )
        .all()
    )
    
    # Build summary by symbol
    orders_by_symbol = defaultdict(lambda: {
        "total_orders": 0,
        "filled_count": 0,
        "pending_count": 0,
        "locked_bp": 0.0,
        "next_trigger": None,
        "gtt_order_ids": [],
        "filled_today": [],
    })
    
    total_locked_bp = 0.0
    
    for gtt_order in active_orders:
        symbol = gtt_order.symbol
        info = orders_by_symbol[symbol]
        info["gtt_order_ids"].append(gtt_order.id)
        info["total_orders"] += gtt_order.total_count
        info["filled_count"] += gtt_order.filled_count
        info["locked_bp"] += gtt_order.locked_buying_power
        total_locked_bp += gtt_order.locked_buying_power
        
        # Find next trigger price (lowest trigger price without alpaca_order_id)
        for detail in gtt_order.order_details:
            if not detail.alpaca_order_id:
                info["pending_count"] += 1
                if info["next_trigger"] is None or detail.trigger_price < info["next_trigger"]:
                    info["next_trigger"] = detail.trigger_price
    
    # Add filled today info
    filled_today_by_symbol = defaultdict(list)
    total_filled_amount = 0.0
    
    for activity in filled_today_activities:
        symbol = activity.symbol
        qty = activity.quantity or 0
        price = activity.price or 0
        amount = activity.amount or (qty * price)
        filled_today_by_symbol[symbol].append({
            "qty": qty,
            "price": price,
            "amount": amount,
        })
        total_filled_amount += amount
        
        # Update the orders_by_symbol if symbol exists
        if symbol in orders_by_symbol:
            orders_by_symbol[symbol]["filled_today"].append({
                "qty": qty,
                "price": price,
                "amount": amount,
            })
    
    return {
        "orders_by_symbol": dict(orders_by_symbol),
        "total_locked_bp": total_locked_bp,
        "total_symbols": len(orders_by_symbol),
        "total_pending": sum(info["pending_count"] for info in orders_by_symbol.values()),
        "filled_today_by_symbol": dict(filled_today_by_symbol),
        "filled_today_count": len(filled_today_activities),
        "filled_today_amount": total_filled_amount,
    }


def get_todays_failed_activities(db: Session) -> list:
    """Get today's failed order activities."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return (
        db.query(Activity)
        .filter(
            Activity.activity_type == ActivityType.ORDER_FAILED,
            Activity.created_at >= today_start,
        )
        .order_by(Activity.created_at.desc())
        .all()
    )


def generate_daily_summary(db: Session, alpaca_client: AlpacaClient) -> str:
    """Generate the enhanced daily summary message.
    
    Args:
        db: Database session
        alpaca_client: Alpaca API client
        
    Returns:
        Formatted summary message
    """
    # Get data
    account = get_account_summary(alpaca_client)
    gtt_summary = get_gtt_orders_summary(db)
    failed_activities = get_todays_failed_activities(db)
    
    # Build message
    now = datetime.utcnow()
    message = "Daily Trading Summary\n"
    message += f"{now.strftime('%Y-%m-%d %H:%M')} UTC\n"
    message += "=" * 30 + "\n\n"
    
    # Account Overview (compact format)
    if account:
        equity = account.get("equity", 0)
        cash = account.get("cash", 0)
        last_equity = account.get("last_equity", equity)
        
        # Calculate today's P/L
        pl_dollars = equity - last_equity if last_equity else 0
        pl_percent = ((equity - last_equity) / last_equity * 100) if last_equity and last_equity > 0 else 0
        
        message += f"Account: {format_currency(equity)} equity | {format_currency(cash)} cash\n"
        
        # Today's P/L
        emoji = "+" if pl_dollars >= 0 else ""
        message += f"Today's P/L: {emoji}{format_currency(pl_dollars)} ({format_percent(pl_percent)})\n"
    
    message += "\n"
    
    # GTT Orders Summary
    orders_by_symbol = gtt_summary.get("orders_by_symbol", {})
    total_symbols = gtt_summary.get("total_symbols", 0)
    
    if total_symbols > 0:
        message += f"GTT Orders ({total_symbols} symbols active):\n"
        
        # Sort by symbol for consistent display
        for symbol in sorted(orders_by_symbol.keys()):
            info = orders_by_symbol[symbol]
            filled = info["filled_count"]
            total = info["total_orders"]
            pending = info["pending_count"]
            next_trigger = info["next_trigger"]
            
            # Format: AAPL: 2/5 filled | Next: $172.50
            status_str = f"{filled}/{total} filled" if filled > 0 else f"{pending} pending"
            trigger_str = f"Next: {format_price(next_trigger)}" if next_trigger else "All triggered"
            
            message += f"  {symbol}: {status_str} | {trigger_str}\n"
    else:
        message += "GTT Orders: None active\n"
    
    message += "\n"
    
    # Filled Today
    filled_today = gtt_summary.get("filled_today_by_symbol", {})
    filled_count = gtt_summary.get("filled_today_count", 0)
    filled_amount = gtt_summary.get("filled_today_amount", 0)
    
    if filled_count > 0:
        message += f"Filled Today ({filled_count} orders, {format_currency(filled_amount)} total):\n"
        
        for symbol in sorted(filled_today.keys()):
            fills = filled_today[symbol]
            total_qty = sum(f["qty"] for f in fills)
            avg_price = sum(f["price"] * f["qty"] for f in fills) / total_qty if total_qty > 0 else 0
            
            message += f"  - {symbol}: {total_qty} @ {format_price(avg_price)}\n"
        
        message += "\n"
    
    # Locked Buying Power
    total_locked = gtt_summary.get("total_locked_bp", 0)
    if total_locked > 0:
        message += f"Locked Buying Power: {format_currency(total_locked)}\n\n"
    
    # Failed Orders (only show if there are failures)
    if failed_activities:
        failed_by_symbol = defaultdict(int)
        for activity in failed_activities:
            failed_by_symbol[activity.symbol] += 1
        
        message += f"Failed Orders ({len(failed_activities)} attempts):\n"
        for symbol, count in sorted(failed_by_symbol.items(), key=lambda x: -x[1])[:5]:
            message += f"  - {symbol}: {count}x\n"
        
        if len(failed_by_symbol) > 5:
            message += f"  ... and {len(failed_by_symbol) - 5} more\n"
        
        message += "\n"
    
    # Footer
    message += "=" * 30 + "\n"
    message += "trading.parthchandak.info"
    
    return message


def send_enhanced_daily_summary(db: Session, alpaca_client: AlpacaClient) -> bool:
    """Generate and send the enhanced daily summary via WhatsApp.
    
    Args:
        db: Database session
        alpaca_client: Alpaca API client
        
    Returns:
        True if summary was sent successfully, False otherwise
    """
    try:
        from core.whatsapp_service import get_whatsapp_service

        whatsapp = get_whatsapp_service()
        if not whatsapp.enabled:
            logger.debug("WhatsApp notifications are disabled, skipping daily summary")
            return False

        # Generate the summary
        message = generate_daily_summary(db, alpaca_client)
        
        # Send message
        success = whatsapp.send_message(message=message)
        if success:
            logger.info("Daily trading summary sent successfully")
        else:
            logger.error("Failed to send daily trading summary")
        
        return success

    except Exception as e:
        logger.error(f"Error sending enhanced daily summary: {e}", exc_info=True)
        return False
