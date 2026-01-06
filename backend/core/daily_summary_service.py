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


def categorize_error(description: str) -> tuple[str, str]:
    """Categorize an error from its description.
    
    Returns:
        Tuple of (error_category, fix_suggestion)
    """
    desc_lower = description.lower()
    
    # Check for common error patterns
    if "40310000" in description or "minimal amount" in desc_lower or "below $1" in desc_lower:
        return ("Below $1 minimum", "Increase qty so value >= $1")
    
    if "insufficient" in desc_lower or "buying power" in desc_lower:
        return ("Insufficient funds", "Add funds or reduce order size")
    
    if "0.01" in description and "quantity" in desc_lower:
        return ("Qty below 0.01", "Increase quantity to >= 0.01")
    
    if "fractionable" in desc_lower or "fractional" in desc_lower:
        return ("Not fractionable", "Use whole number quantities")
    
    if "market" in desc_lower and "closed" in desc_lower:
        return ("Market closed", "Wait for market hours")
    
    if "symbol" in desc_lower and ("invalid" in desc_lower or "not found" in desc_lower):
        return ("Invalid symbol", "Check symbol exists on Alpaca")
    
    # Default: truncate description
    return (description[:40] + "..." if len(description) > 40 else description, "")


def get_closest_triggers(orders_by_symbol: dict, max_items: int = 5) -> list:
    """Get symbols closest to triggering based on current prices.
    
    Returns list of (symbol, trigger_price, current_price, percent_away)
    """
    from core.price_cache_service import PriceCacheService
    
    # Get all symbols with pending triggers
    symbols_with_triggers = []
    for symbol, info in orders_by_symbol.items():
        if info.get("next_trigger"):
            symbols_with_triggers.append((symbol, info["next_trigger"]))
    
    if not symbols_with_triggers:
        return []
    
    # Get current prices from cache
    symbols = [s[0] for s in symbols_with_triggers]
    current_prices = PriceCacheService.get_prices(symbols)
    
    # Calculate distance to trigger for each
    closest = []
    for symbol, trigger_price in symbols_with_triggers:
        current_price = current_prices.get(symbol)
        if current_price and current_price > 0 and trigger_price > 0:
            # How far above trigger is the current price? (negative = below trigger)
            percent_away = ((current_price - trigger_price) / trigger_price) * 100
            # Only include if price is above trigger (hasn't fired yet)
            if percent_away > 0:
                closest.append((symbol, trigger_price, current_price, percent_away))
    
    # Sort by closest (smallest percent_away first)
    closest.sort(key=lambda x: x[3])
    return closest[:max_items]


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
        equity = float(account.get("equity", 0))
        cash = float(account.get("cash", 0))
        last_equity = float(account.get("last_equity", equity))
        
        # Calculate today's P/L
        pl_dollars = equity - last_equity if last_equity else 0
        pl_percent = ((equity - last_equity) / last_equity * 100) if last_equity and last_equity > 0 else 0
        
        message += f"Account: {format_currency(equity)} | Cash: {format_currency(cash)}\n"
        
        # Today's P/L with emoji
        pl_emoji = "+" if pl_dollars >= 0 else ""
        message += f"Today: {pl_emoji}{format_currency(pl_dollars)} ({format_percent(pl_percent)})\n"
    
    message += "\n"
    
    # Filled Today (show first if there are fills - most important)
    filled_today = gtt_summary.get("filled_today_by_symbol", {})
    filled_count = gtt_summary.get("filled_today_count", 0)
    filled_amount = gtt_summary.get("filled_today_amount", 0)
    
    if filled_count > 0:
        message += f"--- Filled Today ({filled_count} orders, {format_currency(filled_amount)}) ---\n"
        
        for symbol in sorted(filled_today.keys()):
            fills = filled_today[symbol]
            total_qty = sum(f["qty"] for f in fills)
            total_amount = sum(f["amount"] for f in fills)
            avg_price = sum(f["price"] * f["qty"] for f in fills) / total_qty if total_qty > 0 else 0
            
            # Format qty nicely (no decimals if whole number)
            qty_str = f"{total_qty:.4f}".rstrip('0').rstrip('.') if total_qty < 1 else f"{total_qty:.2f}".rstrip('0').rstrip('.')
            message += f"  {symbol}: {qty_str} @ {format_price(avg_price)} = {format_currency(total_amount)}\n"
        
        message += "\n"
    
    # GTT Orders Summary - compact format
    orders_by_symbol = gtt_summary.get("orders_by_symbol", {})
    total_symbols = gtt_summary.get("total_symbols", 0)
    total_pending = gtt_summary.get("total_pending", 0)
    total_locked = gtt_summary.get("total_locked_bp", 0)
    filled_today_by_symbol = gtt_summary.get("filled_today_by_symbol", {})
    
    if total_symbols > 0:
        # Calculate totals
        total_filled = sum(info["filled_count"] for info in orders_by_symbol.values())
        total_orders = sum(info["total_orders"] for info in orders_by_symbol.values())
        
        # Header with locked BP
        locked_str = f" | {format_currency(total_locked)} locked" if total_locked > 0 else ""
        message += f"--- GTT Orders ({total_symbols} symbols, {total_filled}/{total_orders} filled){locked_str} ---\n"
        
        # Compact list: symbol(filled/total) format, multiple per line
        # Sort: fills today first, then by fill ratio
        def sort_key(symbol):
            info = orders_by_symbol[symbol]
            has_fill_today = 1 if symbol in filled_today_by_symbol else 0
            fill_ratio = info["filled_count"] / max(info["total_orders"], 1)
            return (-has_fill_today, -fill_ratio, symbol)
        
        sorted_symbols = sorted(orders_by_symbol.keys(), key=sort_key)
        
        # Build compact entries: AAPL(2/5) or *AAPL(2/5) for today's fills
        entries = []
        for symbol in sorted_symbols:
            info = orders_by_symbol[symbol]
            filled = info["filled_count"]
            total = info["total_orders"]
            marker = "*" if symbol in filled_today_by_symbol else ""
            entries.append(f"{marker}{symbol}({filled}/{total})")
        
        # Join with spaces
        message += "  " + " ".join(entries) + "\n"
        
        message += "\n"
        
        # Closest to Trigger (only if we have pending orders)
        if total_pending > 0:
            closest = get_closest_triggers(orders_by_symbol, max_items=5)
            if closest:
                message += "--- Closest to Trigger ---\n"
                for symbol, trigger, current, pct_away in closest:
                    message += f"  {symbol}: {format_price(trigger)} (now {format_price(current)}, {pct_away:.1f}% away)\n"
                message += "\n"
    else:
        message += "GTT Orders: None active\n\n"
    
    # Failed Orders (only show if there are failures)
    if failed_activities:
        # Group by symbol and error category
        failed_by_symbol_category = defaultdict(lambda: defaultdict(int))
        for activity in failed_activities:
            category, _ = categorize_error(activity.description)
            failed_by_symbol_category[activity.symbol][category] += 1
        
        total_symbols = len(failed_by_symbol_category)
        message += f"Failed Orders ({len(failed_activities)} attempts, {total_symbols} symbols):\n"
        
        # Show top 5 symbols with most failures
        sorted_symbols = sorted(
            failed_by_symbol_category.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True
        )[:5]
        
        for symbol, categories in sorted_symbols:
            total = sum(categories.values())
            # Get the most common error category for this symbol
            top_category = max(categories.items(), key=lambda x: x[1])
            category_name, count = top_category
            
            if len(categories) == 1:
                message += f"  - {symbol}: {total}x ({category_name})\n"
            else:
                message += f"  - {symbol}: {total}x (mostly: {category_name})\n"
        
        if total_symbols > 5:
            message += f"  ... and {total_symbols - 5} more symbols\n"
        
        # Show fix suggestion for the most common error
        all_categories = defaultdict(int)
        for categories in failed_by_symbol_category.values():
            for cat, count in categories.items():
                all_categories[cat] += count
        
        if all_categories:
            top_error = max(all_categories.items(), key=lambda x: x[1])[0]
            _, fix = categorize_error(top_error)  # Get fix from category name
            if not fix:
                # Re-categorize to get the fix
                for activity in failed_activities:
                    cat, fix = categorize_error(activity.description)
                    if cat == top_error and fix:
                        break
            if fix:
                message += f"  Tip: {fix}\n"
        
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
