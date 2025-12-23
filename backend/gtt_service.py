"""Service for managing GTT orders and price monitoring."""

import logging
import os
from datetime import datetime, timedelta

from alpaca_client import AlpacaClient
from config import settings
from core.logging_utils import (
    log_gtt_monitoring_summary,
    log_gtt_order_created,
    log_gtt_order_deleted,
    log_order_detail_deleted,
    log_order_failed,
    log_order_triggered,
    log_price_fetch,
)
from models import Activity, ActivityType, GTTOrder, GTTOrderDetail, OrderStatus
from rate_limiter import rate_limit_alpaca_call_sync
from schemas import GTTOrderCreate
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Global tolerance for floating point comparisons
TOLERANCE = 1e-6


def _detect_currency_from_symbol(symbol: str) -> str:
    """Detect currency from symbol.
    
    Currently all orders are USD-denominated:
    - Crypto pairs: BTC/USD, ETH/USD -> USD
    - Stocks: AAPL, TSLA -> USD
    
    Future: Can be extended to detect EUR, GBP, JPY, etc. from symbol or asset info.
    
    Args:
        symbol: Symbol string (e.g., "BTC/USD", "AAPL")
    
    Returns:
        Currency code (e.g., "USD", "EUR", "GBP")
    """
    symbol_upper = symbol.upper()
    
    # Check if it's a crypto pair with currency (e.g., BTC/USD, ETH/EUR)
    if "/" in symbol_upper:
        parts = symbol_upper.split("/")
        if len(parts) == 2:
            quote_currency = parts[1]
            # Common quote currencies
            if quote_currency in ["USD", "USDT", "USDC"]:
                return "USD"
            elif quote_currency in ["EUR", "EURT"]:
                return "EUR"
            elif quote_currency == "GBP":
                return "GBP"
            elif quote_currency == "JPY":
                return "JPY"
            # Default to USD for unknown quote currencies
            return "USD"
    
    # Stocks are USD-denominated (for now)
    # Future: Could check asset info from Alpaca API for currency
    return "USD"


def validate_and_prepare_order(
    db: Session,
    order_data: GTTOrderCreate,
    check_duplicates: bool = True,
    auto_round: bool = False,
) -> dict:
    """
    Unified validation for GTT orders.

    Returns a dict with:
    - valid: bool - whether the order is valid
    - order_data: GTTOrderCreate - potentially modified order data (rounded)
    - warnings: list - any warnings (rounding, etc.)
    - duplicate: dict | None - duplicate order info if found
    - error: str | None - error message if invalid
    """
    from alpaca_client import normalize_crypto_symbol
    from asset_cache import get_asset_fractionable
    from models import GTTOrder, OrderStatus

    symbol_upper = order_data.symbol.upper()
    # Normalize crypto symbols for consistent duplicate detection (BTCUSD -> BTC/USD)
    symbol_upper = normalize_crypto_symbol(symbol_upper)
    result = {
        "valid": True,
        "order_data": order_data,
        "warnings": [],
        "duplicate": None,
        "error": None,
    }

    # Check if asset supports fractional trading
    fractionable_status = get_asset_fractionable(symbol_upper)
    fractionable = fractionable_status if fractionable_status is not None else True

    # Check for duplicates (same symbol + trigger price, non-terminal status, with active order_details)
    if check_duplicates:
        existing_orders = (
            db.query(GTTOrder)
            .filter(
                GTTOrder.symbol == symbol_upper,
                GTTOrder.initial_trigger_price == order_data.initial_trigger_price,
            )
            .all()
        )

        for existing_order in existing_orders:
            # Only consider it a duplicate if:
            # 1. Order is not in terminal status
            # 2. Order has at least one order_detail (not empty)
            if not OrderStatus.is_terminal(existing_order.status.value):
                # Check if order has any order_details
                if (
                    existing_order.order_details
                    and len(existing_order.order_details) > 0
                ):
                    result["duplicate"] = {
                        "symbol": symbol_upper,
                        "trigger_price": order_data.initial_trigger_price,
                        "existing_order_id": existing_order.id,
                        "message": f"An order already exists for {symbol_upper} at trigger price ${order_data.initial_trigger_price:.2f} (Order ID: {existing_order.id})",
                    }
                    result["valid"] = False
                    # Don't return immediately - let the caller decide how to handle duplicates
                    break

    # Validate fractional trading
    if not fractionable:
        fractional_quantities = []

        # Check initial quantity
        if (
            abs(order_data.initial_quantity - round(order_data.initial_quantity))
            > TOLERANCE
        ):
            fractional_quantities.append(
                {
                    "level": 0,
                    "original": order_data.initial_quantity,
                    "rounded": max(1, round(order_data.initial_quantity)),
                }
            )

        # Check calculated quantities through the ladder
        current_qty = order_data.initial_quantity
        for i in range(order_data.iterations):
            rounded_qty = max(1, round(current_qty))
            if abs(current_qty - rounded_qty) > TOLERANCE:
                fractional_quantities.append(
                    {"level": i + 1, "original": current_qty, "rounded": rounded_qty}
                )
            current_qty *= order_data.increment_qty_multiplier

        if fractional_quantities:
            if auto_round:
                # Auto-round the initial quantity
                order_data.initial_quantity = max(1, round(order_data.initial_quantity))
                result["order_data"] = order_data
                result["warnings"].append(
                    {
                        "type": "rounding",
                        "symbol": symbol_upper,
                        "message": f"Asset {symbol_upper} does not support fractional trading. Quantities were automatically rounded.",
                        "fractional_quantities": fractional_quantities,
                    }
                )
            else:
                # Require user confirmation
                result["valid"] = False
                result["error"] = (
                    f"Asset {symbol_upper} does not support fractional trading. Quantity must be a whole number."
                )
                result["warnings"].append(
                    {
                        "type": "rounding",
                        "symbol": symbol_upper,
                        "message": f"Asset {symbol_upper} does not support fractional trading. Quantities need to be rounded.",
                        "fractional_quantities": fractional_quantities,
                        "requires_confirmation": True,
                    }
                )

    # MINIMUM QUANTITY VALIDATION (BLOCKING)
    # Alpaca requires minimum 0.01 quantity for fractional orders (stocks and crypto)
    # This applies to ALL fractional orders, including BTC/USD
    # See: backend/constants.py::MIN_FRACTIONAL_QUANTITY
    from constants import MIN_FRACTIONAL_QUANTITY
    
    if fractionable:
        # Check minimum quantity for fractional assets (crypto and fractional stocks)
        quantities_below_minimum = []
        current_qty = order_data.initial_quantity
        
        # Check initial quantity
        if current_qty < MIN_FRACTIONAL_QUANTITY:
            quantities_below_minimum.append({
                "level": 0,
                "quantity": current_qty,
                "min_quantity": MIN_FRACTIONAL_QUANTITY,
            })
        
        # Check calculated quantities through the ladder
        for i in range(order_data.iterations):
            if current_qty < MIN_FRACTIONAL_QUANTITY:
                quantities_below_minimum.append({
                    "level": i + 1,
                    "quantity": current_qty,
                    "min_quantity": MIN_FRACTIONAL_QUANTITY,
                })
            current_qty *= order_data.increment_qty_multiplier
        
        if quantities_below_minimum:
            # BLOCKING: Reject orders with quantities below minimum
            result["valid"] = False
            result["error"] = (
                f"{len(quantities_below_minimum)} order level(s) have quantity below minimum "
                f"({MIN_FRACTIONAL_QUANTITY}). Increase initial quantity."
            )
            result["warnings"].append({
                "type": "minimum_quantity",
                "symbol": symbol_upper,
                "min_quantity": MIN_FRACTIONAL_QUANTITY,
                "message": f"{len(quantities_below_minimum)} order level(s) have quantity below minimum "
                           f"({MIN_FRACTIONAL_QUANTITY}). Increase initial quantity.",
                "quantities_below_minimum": quantities_below_minimum,
                "requires_confirmation": False,  # Blocking error, not a warning
            })

    # MINIMUM ORDER VALUE VALIDATION (BLOCKING)
    # Alpaca requires minimum notional value for all orders (crypto and stocks)
    # Formula: quantity × price ≥ MIN_ORDER_VALUE[currency]
    # Error code: 40310000
    # Minimum order value validation - see README.md for details
    # BLOCKING: Orders below minimum will be rejected at creation time
    from constants import MIN_ORDER_VALUE, MIN_ORDER_VALUE_DEFAULT
    
    # Detect currency from symbol (currently all orders are USD)
    currency = _detect_currency_from_symbol(symbol_upper)
    min_order_value = MIN_ORDER_VALUE.get(currency, MIN_ORDER_VALUE_DEFAULT)
    
    current_price = order_data.initial_trigger_price
    current_qty = order_data.initial_quantity
    orders_below_minimum = []

    for i in range(order_data.iterations):
        limit_price = current_price * order_data.decrement_price_multiplier
        limit_price = round(limit_price, 2)
        
        # Use fractional qty or rounded based on fractionable status
        actual_qty = current_qty if fractionable else max(1, round(current_qty))
        order_value = actual_qty * limit_price

        if order_value < min_order_value:
            min_qty_needed = min_order_value / limit_price if limit_price > 0 else 0
            orders_below_minimum.append({
                "level": i + 1,
                "quantity": actual_qty,
                "price": limit_price,
                "value": round(order_value, 4),
                "min_qty_needed": round(min_qty_needed, 4),
            })

        # Update for next iteration
        current_price = limit_price
        current_qty = current_qty * order_data.increment_qty_multiplier

    if orders_below_minimum:
        # BLOCKING: Reject orders that will fail
        currency_symbol = "$" if currency == "USD" else currency
        result["valid"] = False
        result["error"] = (
            f"{len(orders_below_minimum)} order(s) will be below Alpaca's minimum order value "
            f"({currency_symbol}{min_order_value:.2f}). Increase initial quantity or price."
        )
        result["warnings"].append({
            "type": "minimum_value",
            "symbol": symbol_upper,
            "currency": currency,
            "min_order_value": min_order_value,
            "message": f"{len(orders_below_minimum)} order(s) will be below Alpaca's minimum order value "
                       f"({currency_symbol}{min_order_value:.2f}). Increase initial quantity or price.",
            "orders_below_minimum": orders_below_minimum,
            "requires_confirmation": False,  # Blocking error, not a warning
        })

    return result


def _get_detail_status(
    db: Session, alpaca_client: AlpacaClient, detail: GTTOrderDetail
) -> str:
    """Get the status of an order detail from Alpaca cache."""
    if not detail.alpaca_order_id:
        return OrderStatus.PENDING.value

    from alpaca_order_cache import get_alpaca_order_data

    cache_data = get_alpaca_order_data(
        db, alpaca_client, detail.alpaca_order_id, force_refresh=False
    )
    if cache_data and cache_data.get("status"):
        return cache_data["status"]

    return OrderStatus.PENDING.value


class GTTService:
    """Service for GTT order management."""

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.alpaca = AlpacaClient()

    def _log_to_file(
        self, description: str, type_: str, qty: float, amount: float, date: datetime
    ):
        """Log successful triggers to a file.
        
        Format matches user requirement:
        Description | Type | Qty | Amount | Date
        """
        try:
            # Get log path from settings or env
            log_path = os.getenv("ACTIVITY_LOGS") or getattr(
                settings, "activity_logs_dir", None
            )
            
            # If not configured, try default directory
            if not log_path:
                # Fallback to relative logs directory
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                log_path = os.path.join(base_dir, "logs", "triggered_orders.log")

            # Check if log_path looks like a file or directory
            if log_path.endswith(".log") or log_path.endswith(".txt"):
                # It's a file path
                log_file = log_path
                log_dir = os.path.dirname(log_file)
            else:
                # It's a directory
                log_dir = log_path
                log_file = os.path.join(log_dir, "triggered_orders.log")

            # Ensure directory exists
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # Format: Description | Type | Qty | Amount | Date
            # Example: Buy 0.32 LYFT | FILL | 0.32 | -$6.21 | Nov 25, 2025, 07:19:40 AM
            # Using tabs as delimiters based on user example visual spacing
            amount_str = f"-${abs(amount):.2f}" if amount > 0 else f"${abs(amount):.2f}"
            date_str = date.strftime("%b %d, %Y, %I:%M:%S %p")
            
            log_entry = f"{description}\t{type_}\t{qty}\t{amount_str}\t{date_str}\n"

            with open(log_file, "a") as f:
                f.write(log_entry)

        except Exception as e:
            logger.error(f"Failed to log to file: {e}")

    def create_gtt_order(
        self, order_data: GTTOrderCreate, skip_validation: bool = False
    ) -> GTTOrder:
        """Create a new GTT order with ladder of limit orders.

        Args:
            order_data: Order creation data
            skip_validation: Skip validation (used when already validated, e.g., from CSV with auto_round=True)
        """
        from alpaca_client import normalize_crypto_symbol
        from asset_cache import get_asset_fractionable

        symbol_upper = order_data.symbol.upper()
        # Normalize crypto symbols for consistent duplicate detection (BTCUSD -> BTC/USD)
        symbol_upper = normalize_crypto_symbol(symbol_upper)
        fractionable_status = get_asset_fractionable(symbol_upper)
        fractionable = fractionable_status if fractionable_status is not None else True

        # Validate if not skipped
        if not skip_validation:
            validation_result = validate_and_prepare_order(
                self.db, order_data, check_duplicates=True, auto_round=False
            )
            if not validation_result["valid"]:
                error_msg = validation_result["error"] or "Validation failed"
                raise ValueError(error_msg)

        # Calculate order ladder
        order_details = []
        current_price = order_data.initial_trigger_price
        current_qty = order_data.initial_quantity
        total_value = 0.0

        for i in range(order_data.iterations):
            limit_price = current_price * order_data.decrement_price_multiplier
            # Round price to 2 decimal places to avoid floating point precision issues
            limit_price = round(limit_price, 2)

            # Store original fractional quantity for fractionable assets
            # For non-fractionable assets, ensure quantity is integer (round, don't truncate)
            if not fractionable:
                qty = max(1, round(current_qty))  # Round to nearest integer, min 1
                fractional_qty = float(qty)
            else:
                # For fractionable assets, keep fractional quantity
                fractional_qty = current_qty
                # Round for display/storage (but use fractional for orders)
                qty = max(1, round(current_qty)) if current_qty >= 0.01 else 0

            amount = fractional_qty * limit_price
            total_value += amount

            # Auto-calculate time_in_force based on fractional quantity and asset type
            # For stocks: Fractional quantities must use DAY, whole numbers can use GTC
            # For crypto: Only GTC and IOC are supported (not DAY)
            actual_qty = fractional_qty if fractionable else qty
            is_fractional = abs(actual_qty - round(actual_qty)) > TOLERANCE
            is_crypto = "/" in symbol_upper

            if is_crypto:
                # Crypto only supports GTC and IOC - use GTC as default
                time_in_force = order_data.time_in_force or "gtc"
                if time_in_force.lower() == "day":
                    logger.info(
                        f"Crypto symbol {symbol_upper} - converting DAY to GTC (crypto doesn't support DAY)"
                    )
                    time_in_force = "gtc"
                elif time_in_force.lower() not in ["gtc", "ioc"]:
                    logger.warning(
                        f"Crypto symbol {symbol_upper} - invalid time_in_force {time_in_force}, defaulting to GTC"
                    )
                    time_in_force = "gtc"
            else:
                # Stocks: Fractional quantities must use DAY, whole numbers can use GTC
                time_in_force = (
                    "day" if is_fractional else (order_data.time_in_force or "gtc")
                )

            detail = GTTOrderDetail(
                order_index=i,
                trigger_price=round(current_price, 2),  # Round trigger price too
                quantity=qty,  # Display quantity (rounded)
                fractional_quantity=fractional_qty
                if fractionable
                else None,  # Store fractional for orders
                limit_price=limit_price,
                amount=round(amount, 2),  # Round amount
                time_in_force=time_in_force,
            )
            order_details.append(detail)

            # Update for next iteration
            current_price = limit_price
            current_qty = current_qty * order_data.increment_qty_multiplier
            if not fractionable:
                current_qty = round(
                    current_qty
                )  # Round, don't truncate (int() truncates)

        # Create GTT order
        try:
            gtt_order = GTTOrder(
                symbol=order_data.symbol,
                initial_trigger_price=order_data.initial_trigger_price,
                initial_quantity=order_data.initial_quantity,
                increment_qty_multiplier=order_data.increment_qty_multiplier,
                decrement_price_multiplier=order_data.decrement_price_multiplier,
                iterations=order_data.iterations,
                total_count=order_data.iterations,
                total_value=total_value,
                locked_buying_power=total_value,
                order_details=order_details,
            )

            self.db.add(gtt_order)
            self.db.commit()
            self.db.refresh(gtt_order)

            # Log activity
            self._log_activity(
                gtt_order_id=gtt_order.id,
                activity_type=ActivityType.GTT_TRIGGER,
                symbol=gtt_order.symbol,
                description=f"GTT order created: {order_data.iterations} orders, total value ${total_value:.2f}",
                notes=f"Initial trigger: ${order_data.initial_trigger_price}, Qty: {order_data.initial_quantity}",
            )

            log_gtt_order_created(gtt_order.id, gtt_order.symbol, order_data.iterations)
            return gtt_order
        except Exception as e:
            logger.error(f"Error creating GTT order: {e}", exc_info=True)
            self.db.rollback()
            raise

    def get_all_gtt_orders(self) -> list[GTTOrder]:
        """Get all GTT orders."""
        return self.db.query(GTTOrder).order_by(GTTOrder.created_at.desc()).all()

    def get_gtt_order(self, order_id: int) -> GTTOrder | None:
        """Get a specific GTT order by ID."""
        return self.db.query(GTTOrder).filter(GTTOrder.id == order_id).first()

    def delete_gtt_order(self, order_id: int) -> bool:
        """Delete a GTT order."""
        try:
            gtt_order = self.get_gtt_order(order_id)
            if not gtt_order:
                return False

            # Cancel any pending Alpaca orders
            for detail in gtt_order.order_details:
                if detail.alpaca_order_id:
                    detail_status = _get_detail_status(self.db, self.alpaca, detail)
                    if detail_status == OrderStatus.PENDING.value:
                        try:
                            self.alpaca.cancel_order(detail.alpaca_order_id)
                        except Exception as e:
                            logger.warning(
                                f"Failed to cancel order {detail.alpaca_order_id}: {e}"
                            )

            self.db.delete(gtt_order)
            self.db.commit()

            log_gtt_order_deleted(order_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting GTT order {order_id}: {e}", exc_info=True)
            self.db.rollback()
            raise

    def delete_order_detail(self, detail_id: int) -> bool:
        """Delete an individual order detail."""
        from models import GTTOrderDetail

        try:
            detail = (
                self.db.query(GTTOrderDetail)
                .filter(GTTOrderDetail.id == detail_id)
                .first()
            )
            if not detail:
                logger.warning(f"Order detail {detail_id} not found")
                return False

            # Get the parent GTT order and store detail info before deletion
            gtt_order = detail.gtt_order
            detail_amount = detail.amount
            alpaca_order_id = detail.alpaca_order_id
            detail_status = _get_detail_status(self.db, self.alpaca, detail)

            logger.info(
                f"Deleting order detail {detail_id} (order {gtt_order.id}, symbol {gtt_order.symbol}, status {detail_status})"
            )

            # Cancel Alpaca order if pending
            if alpaca_order_id and detail_status == OrderStatus.PENDING.value:
                try:
                    logger.info(
                        f"Cancelling Alpaca order {alpaca_order_id} for detail {detail_id}"
                    )
                    self.alpaca.cancel_order(alpaca_order_id)
                    logger.info(
                        f"Successfully cancelled Alpaca order {alpaca_order_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to cancel Alpaca order {alpaca_order_id}: {e}",
                        exc_info=True,
                    )
                    # Don't fail the deletion if cancel fails - just log it

            # Delete the detail
            self.db.delete(detail)
            self.db.flush()  # Flush to ensure deletion is processed

            # Recalculate order counts from remaining details
            # Query remaining details directly instead of using relationship after refresh
            remaining_details = (
                self.db.query(GTTOrderDetail)
                .filter(GTTOrderDetail.gtt_order_id == gtt_order.id)
                .all()
            )

            # Get status from cache for each detail
            filled_count = 0
            locked_amount = 0.0
            for d in remaining_details:
                # Only orders submitted to Alpaca (have alpaca_order_id) can lock buying power
                if not d.alpaca_order_id:
                    # Our internal PENDING - not submitted yet, does NOT lock buying power
                    continue

                d_status = _get_detail_status(self.db, self.alpaca, d)
                if d_status == OrderStatus.FILLED.value:
                    filled_count += 1
                elif OrderStatus.locks_buying_power(d_status):
                    # Only count orders that lock buying power (submitted to Alpaca and not filled/cancelled/etc.)
                    locked_amount += d.amount

            gtt_order.filled_count = filled_count
            gtt_order.total_count = len(remaining_details)
            gtt_order.total_value = sum(d.amount for d in remaining_details)
            gtt_order.locked_buying_power = locked_amount

            # If no details remain, delete the parent order automatically
            # An order with no details is useless and creates confusion
            if len(remaining_details) == 0:
                logger.info(
                    f"No order details remain for GTT order {gtt_order.id}. Deleting parent order."
                )
                self.db.delete(gtt_order)
                logger.info(
                    f"Deleted empty GTT order {gtt_order.id} (symbol: {gtt_order.symbol})"
                )

            self.db.commit()

            log_order_detail_deleted(
                detail_id, gtt_order.id, gtt_order.symbol, len(remaining_details)
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting order detail {detail_id}: {e}", exc_info=True)
            self.db.rollback()
            raise

    def _is_safe_price_drop(
        self, symbol: str, trigger_price: float, current_price: float, threshold: float = None
    ) -> tuple[bool, str]:
        """Check if price drop is safe (within threshold).

        Uses different thresholds for crypto vs stocks:
        - Crypto: 50% threshold (crypto markets are volatile, legitimate drops can be large)
        - Stocks: 20% threshold (protects against symbol mismatches or bad data)

        Args:
            symbol: Symbol string (e.g., "BTC/USD", "AAPL")
            trigger_price: Original trigger price
            current_price: Current market price
            threshold: Optional override threshold (if None, auto-detects based on symbol type)

        Returns:
            (is_safe, reason)
        """
        from alpaca_client import is_crypto_symbol
        
        # Auto-detect threshold based on symbol type if not provided
        if threshold is None:
            is_crypto = is_crypto_symbol(symbol)
            threshold = 0.50 if is_crypto else 0.20  # 50% for crypto, 20% for stocks
        
        # Calculate percentage drop
        drop_pct = (trigger_price - current_price) / trigger_price

        if drop_pct > threshold:
            asset_type = "crypto" if is_crypto_symbol(symbol) else "stock"
            reason = (
                f"SAFETY HALT: Price ${current_price:.2f} is {drop_pct*100:.1f}% below trigger "
                f"${trigger_price:.2f} (>{threshold*100:.0f}% threshold for {asset_type}). "
                f"This usually indicates a symbol mismatch or bad data. Skipping order to protect funds."
            )
            return False, reason

        return True, ""

    def check_and_trigger_orders(self):
        """Check prices and trigger GTT orders when conditions are met."""
        # Get all pending GTT orders
        pending_orders = (
            self.db.query(GTTOrder).filter(GTTOrder.status == OrderStatus.PENDING).all()
        )

        if not pending_orders:
            logger.debug("No pending GTT orders to monitor")
            return

        # Get unique symbols - fetch prices once per stock symbol, not per order detail
        # Individual order details are only checked to see if price is below their trigger price
        symbols = list(set([order.symbol for order in pending_orders]))
        logger.info(
            f"👀 Monitoring {len(pending_orders)} GTT order(s) for {len(symbols)} symbol(s): {', '.join(symbols)}"
        )

        # Fetch latest prices once per unique symbol (not per order detail)
        # This prevents rate limiting by minimizing API calls
        logger.info(f"📊 Fetching current prices for: {', '.join(symbols)}")
        # Rate limit before fetching prices
        rate_limit_alpaca_call_sync()
        prices = self.alpaca.get_latest_prices(symbols)

        # Update price cache using centralized service
        from core.price_cache_service import PriceCacheService

        PriceCacheService.update_prices(prices, datetime.utcnow())

        # Log prices and GTT monitoring summary using standardized logging
        log_price_fetch(prices)
        log_gtt_monitoring_summary(
            pending_orders, prices, db=self.db, alpaca_client=self.alpaca
        )

        # Broadcast prices to WebSocket clients
        # Note: This is called from run_in_threadpool, so we store prices for async broadcast
        # The actual broadcast will be handled in background_tasks.py after this completes
        # Store prices in a way that background_tasks can access them
        try:
            # Store prices for async broadcast (will be picked up by background_tasks)
            # We'll broadcast from the async context in background_tasks.py
            pass  # Prices are already stored in cache, broadcast happens in async context
        except Exception as e:
            logger.debug(f"Error preparing WebSocket broadcast (non-critical): {e}")

        # Group orders by symbol to process each symbol once
        orders_by_symbol = {}
        for gtt_order in pending_orders:
            symbol = gtt_order.symbol
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(gtt_order)

        # Fetch all open orders from Alpaca once to check for duplicates/orphans
        try:
            open_orders = self.alpaca.get_all_orders(status="OPEN", limit=500)
            # Map: symbol -> list of open orders
            open_orders_map = {}
            for order in open_orders:
                o_symbol = order.get("symbol")
                if o_symbol:
                    if o_symbol not in open_orders_map:
                        open_orders_map[o_symbol] = []
                    open_orders_map[o_symbol].append(order)
            logger.info(
                f"Fetched {len(open_orders)} open orders from Alpaca for duplicate checking"
            )
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            open_orders_map = {}

        # Process each symbol once
        for symbol, symbol_orders in orders_by_symbol.items():
            current_price = prices.get(symbol)
            if not current_price:
                continue

            # Check all order details for this symbol across all GTT orders
            # Only check pending (non-linked) orders - skip filled, cancelled, expired orders
            # Find the first pending order from the top of the ladder to determine if we should check
            for gtt_order in symbol_orders:
                # Get all pending order details (not linked to Alpaca orders yet)
                # Sort by order_index to get the top order first (laddered from highest to lowest trigger)
                pending_details = [
                    detail
                    for detail in gtt_order.order_details
                    if not detail.is_manually_linked and not detail.alpaca_order_id
                ]

                # Sort by order_index (ascending) to get top order first
                pending_details.sort(key=lambda d: d.order_index)

                # If no pending orders, skip this GTT order
                if not pending_details:
                    continue

                # Early exit: only check if price has dropped below the first pending order's trigger price
                # Since orders are laddered downward, if price > first_pending_trigger_price,
                # none of the pending suborders can trigger
                first_pending_trigger = pending_details[0].trigger_price
                if current_price > first_pending_trigger:
                    logger.info(
                        f"   ⏸️  GTT #{gtt_order.id} {symbol}: "
                        f"Current=${current_price:.2f} > FirstTrigger=${first_pending_trigger:.2f} - "
                        f"No orders triggered (waiting for price to drop)"
                    )
                    continue

                logger.info(
                    f"   🎯 GTT #{gtt_order.id} {symbol}: "
                    f"Current=${current_price:.2f} ≤ FirstTrigger=${first_pending_trigger:.2f} - "
                    f"Checking {len(pending_details)} pending order(s)..."
                )

                # Price has dropped below the first pending order - check all pending orders
                for detail in pending_details:
                    if current_price <= detail.trigger_price:
                        # Trigger this order

                        # SAFETY CHECK: Verify price drop is reasonable
                        is_safe, safety_reason = self._is_safe_price_drop(
                            symbol, detail.trigger_price, current_price
                        )
                        if not is_safe:
                            logger.error(f"      🛑 {safety_reason}")
                            # Log failure
                            # Determine threshold used for logging
                            from alpaca_client import is_crypto_symbol
                            threshold_used = 50 if is_crypto_symbol(symbol) else 20
                            
                            self._log_activity(
                                gtt_order_id=gtt_order.id,
                                activity_type=ActivityType.ORDER_FAILED,
                                symbol=symbol,
                                description=safety_reason,
                                notes=f"Trigger: ${detail.trigger_price}, Current: ${current_price}, Threshold: {threshold_used}%",
                            )
                            # Continue to next detail (skip this one)
                            continue

                        # Check for existing orphan order
                        existing_order = None
                        if symbol in open_orders_map:
                            # Look for matching order: same side, qty, price (approx)
                            # We only place BUY orders in this flow
                            expected_price = detail.limit_price

                            # Use fractional quantity if available, otherwise integer
                            expected_qty = (
                                detail.fractional_quantity
                                if detail.fractional_quantity is not None
                                else float(detail.quantity)
                            )

                            for open_o in open_orders_map[symbol]:
                                # Check side
                                if open_o.get("side") != "buy":
                                    continue

                                # Check price (allow small difference for float precision)
                                o_price = float(open_o.get("limit_price", 0) or 0)
                                if abs(o_price - expected_price) > 0.01:
                                    continue

                                # Check quantity (allow small difference)
                                o_qty = float(open_o.get("quantity", 0) or 0)
                                if abs(o_qty - expected_qty) > 0.001:
                                    continue

                                # Found a match!
                                existing_order = open_o
                                break

                        if existing_order:
                            logger.warning(
                                f"⚠️ Found existing orphan Alpaca order {existing_order['id']} "
                                f"for {symbol} (Qty: {expected_qty}, Price: {expected_price}). "
                                f"Linking to GTT detail {detail.id} instead of creating duplicate."
                            )

                            # Link the order
                            detail.alpaca_order_id = existing_order["id"]

                            # Cache Alpaca order data immediately
                            from alpaca_order_cache import get_alpaca_order_data

                            get_alpaca_order_data(
                                self.db,
                                self.alpaca,
                                existing_order["id"],
                                force_refresh=True,
                            )

                            self.db.commit()

                            # Remove from map so we don't link it again to another detail
                            if symbol in open_orders_map:
                                open_orders_map[symbol].remove(existing_order)

                            continue

                        logger.info(
                            f"      🔔 TRIGGER CONDITION MET! "
                            f"Price=${current_price:.2f} ≤ Trigger=${detail.trigger_price:.2f} - "
                            f"Placing order..."
                        )
                        try:
                            # Use fractional quantity if available, otherwise use integer quantity
                            order_qty = (
                                detail.fractional_quantity
                                if detail.fractional_quantity is not None
                                else float(detail.quantity)
                            )

                            # Ensure minimum quantity of 0.01 for fractional orders
                            # Alpaca requires minimum 0.01 quantity for fractional orders
                            if order_qty < 0.01:
                                logger.warning(
                                    f"      ❌ Order detail {detail.id} has quantity {order_qty} < 0.01, skipping"
                                )
                                # Log failure but don't set status (detail doesn't have status field)
                                self._log_activity(
                                    gtt_order_id=gtt_order.id,
                                    activity_type=ActivityType.ORDER_FAILED,
                                    symbol=symbol,
                                    description=f"Order failed: Quantity {order_qty} < 0.01 minimum",
                                    notes=f"Trigger price: ${detail.trigger_price}, Current price: ${current_price}",
                                )
                                self.db.commit()
                                continue

                            # PRE-VALIDATION: Alpaca requires minimum notional value for all orders
                            # (crypto and stocks). Check this BEFORE calling the API to avoid repeated failures.
                            # Formula: quantity × price ≥ MIN_ORDER_VALUE[currency]
                            # Error code: 40310000
                            from constants import MIN_ORDER_VALUE, MIN_ORDER_VALUE_DEFAULT
                            
                            currency = _detect_currency_from_symbol(symbol)
                            min_order_value = MIN_ORDER_VALUE.get(currency, MIN_ORDER_VALUE_DEFAULT)
                            
                            order_value = order_qty * detail.limit_price
                            if order_value < min_order_value:
                                currency_symbol = "$" if currency == "USD" else currency
                                logger.warning(
                                    f"      ❌ Order value {currency_symbol}{order_value:.4f} < {currency_symbol}{min_order_value} minimum - SKIPPING"
                                )
                                self._log_activity(
                                    gtt_order_id=gtt_order.id,
                                    activity_type=ActivityType.ORDER_FAILED,
                                    symbol=symbol,
                                    description=f"Order value {currency_symbol}{order_value:.4f} below {currency_symbol}{min_order_value} minimum. Increase quantity or price.",
                                    quantity=detail.quantity,
                                    price=detail.limit_price,
                                    notes=f"Qty: {order_qty}, Price: {currency_symbol}{detail.limit_price:.4f}, Value: {currency_symbol}{order_value:.4f}. "
                                          f"Min qty needed: {(min_order_value / detail.limit_price):.4f}",
                                )
                                self.db.commit()
                                continue

                            logger.info(
                                f"      📤 Placing LIMIT order: "
                                f"BUY {order_qty} {symbol} @ ${detail.limit_price:.2f} ({detail.time_in_force})"
                            )

                            # Rate limit before placing order (critical!)
                            rate_limit_alpaca_call_sync()
                            alpaca_order = self.alpaca.place_limit_order(
                                symbol=symbol,
                                quantity=order_qty,
                                limit_price=detail.limit_price,
                                time_in_force=detail.time_in_force,
                            )

                            if alpaca_order:
                                # Update directly in DB to avoid race conditions with other threads/workers
                                # that might be updating the parent order status simultaneously.
                                from models import GTTOrderDetail
                                self.db.query(GTTOrderDetail).filter(GTTOrderDetail.id == detail.id).update(
                                    {"alpaca_order_id": alpaca_order["id"]}
                                )
                                detail.alpaca_order_id = alpaca_order["id"] # Update local object too
                                
                                # CRITICAL: Commit transaction immediately to link Alpaca order to DB
                                # This prevents duplicate order placement if the loop continues or cache update fails
                                try:
                                    self.db.commit()
                                    logger.info(
                                        f"      ✅ Linked Alpaca Order ID: {alpaca_order['id']} to Detail #{detail.id}"
                                    )
                                except Exception as e:
                                    # If commit fails, we're in trouble - but at least try to log it
                                    logger.error(f"      ❌ FAILED TO COMMIT ALPACA ORDER LINK: {e!s}")
                                    self.db.rollback()
                                    # Don't continue processing this order if we can't save the link
                                    continue

                                # Cache Alpaca order data immediately (after commit)
                                from alpaca_order_cache import get_alpaca_order_data

                                try:
                                    get_alpaca_order_data(
                                        self.db,
                                        self.alpaca,
                                        alpaca_order["id"],
                                        force_refresh=True,
                                    )
                                except Exception as e:
                                    logger.error(f"      ⚠️ Failed to cache order data (non-critical): {e!s}")

                                # Log activity
                                self._log_activity(
                                    gtt_order_id=gtt_order.id,
                                    activity_type=ActivityType.ORDER_PLACED,
                                    symbol=symbol,
                                    description=f"Limit order placed: {detail.quantity} @ ${detail.limit_price}",
                                    quantity=detail.quantity,
                                    price=detail.limit_price,
                                    side="BUY",
                                    amount=detail.amount,
                                )

                                logger.info(
                                    f"      ✅ ORDER PLACED SUCCESSFULLY! "
                                    f"Alpaca Order ID: {alpaca_order['id']}"
                                )
                                log_order_triggered(
                                    detail.id, symbol, detail.limit_price
                                )
                        except Exception as e:
                            logger.error(f"      ❌ ORDER PLACEMENT FAILED: {e!s}")
                            log_order_failed(detail.id, symbol, str(e))
                            # Log failure but don't set status (detail doesn't have status field)
                            self._log_activity(
                                gtt_order_id=gtt_order.id,
                                activity_type=ActivityType.ORDER_FAILED,
                                symbol=symbol,
                                description=f"Order failed: {e!s}",
                                notes=f"Trigger price: ${detail.trigger_price}, Current price: ${current_price}",
                            )
                    else:
                        logger.debug(
                            f"      ⏭️  Skipping Detail #{detail.id}: "
                            f"Price=${current_price:.2f} > Trigger=${detail.trigger_price:.2f}"
                        )
        
        # Update GTT order statuses for all orders
        # Use a fresh try/except block for status updates to isolate from trigger logic
        try:
            for gtt_order in pending_orders:
                # Update order status using centralized service
                from core.gtt_order_status_service import GTTOrderStatusService

                GTTOrderStatusService.update_order_statuses(
                    self.db, self.alpaca, [gtt_order]
                )
            self.db.commit()
        except Exception as e:
            logger.error(f"Error updating order statuses: {e}")
            self.db.rollback()

    def update_order_statuses(self):
        """Update order statuses from Alpaca cache (background sync at lower rate)."""
        from alpaca_order_cache import batch_refresh_stale_orders

        # Refresh stale cache entries in batch (limits API calls)
        refreshed_count = batch_refresh_stale_orders(
            self.db,
            self.alpaca,
            max_age=timedelta(minutes=2),  # Refresh orders older than 2 minutes
            limit=50,  # Max 50 orders per sync cycle
        )

        if refreshed_count > 0:
            logger.info(f"Refreshed {refreshed_count} Alpaca order cache entries")

        # Update GTT order filled_count based on cached status
        from alpaca_order_cache import get_alpaca_order_data
        from core.gtt_order_status_service import GTTOrderStatusService

        # Get all GTT orders and check their details
        gtt_orders = self.db.query(GTTOrder).all()

        for gtt_order in gtt_orders:
            previous_filled_count = gtt_order.filled_count

            # Update status using centralized service
            GTTOrderStatusService.update_order_statuses(
                self.db, self.alpaca, [gtt_order]
            )

            # Refresh to get updated filled_count
            self.db.refresh(gtt_order)
            new_filled_count = gtt_order.filled_count

            # Log activity if newly filled
            if previous_filled_count < new_filled_count:
                # Find which details were newly filled
                for detail in gtt_order.order_details:
                    if detail.alpaca_order_id:
                        cache_data = get_alpaca_order_data(
                            self.db,
                            self.alpaca,
                            detail.alpaca_order_id,
                            force_refresh=False,
                        )
                        if cache_data and cache_data.get("status") == "FILLED":
                            self._log_activity(
                                gtt_order_id=gtt_order.id,
                                activity_type=ActivityType.ORDER_FILLED,
                                symbol=gtt_order.symbol,
                                description=f"Order filled: {detail.quantity} @ ${detail.limit_price}",
                                quantity=detail.quantity,
                                price=detail.limit_price,
                                side="BUY",
                                amount=detail.amount,
                            )
                            
                            # Log to file (successful trigger/fill)
                            description = f"Buy {detail.quantity} {gtt_order.symbol}"
                            self._log_to_file(
                                description=description,
                                type_="FILL",
                                qty=detail.quantity,
                                amount=-detail.amount,  # Negative for buy (money spent)
                                date=datetime.utcnow(),
                            )

        self.db.commit()

    def check_corporate_actions(self):
        """Check for corporate actions that would affect GTT orders and cancel them.

        Corporate actions like stock splits, symbol changes, mergers, etc. can invalidate
        GTT orders. This method checks for such actions and cancels affected orders.

        Also checks if assets are still valid (exist and are tradable) to catch
        delistings or symbol changes not yet reflected in corporate actions.

        WHY ORDERS EXPIRE:
        - Stock splits change share price/quantity, making existing orders invalid
        - Mergers may change or delist symbols
        - Spinoffs affect share structure
        - Delistings make assets non-tradable
        
        NOTE: Once a limit order is placed with Alpaca, it still needs to be filled by the market.
        GTT orders don't automatically execute - they place limit orders when triggered.
        
        Orders expire when corporate actions (splits, mergers, delistings) invalidate them.
        """
        # Get all pending GTT orders
        pending_orders = (
            self.db.query(GTTOrder).filter(GTTOrder.status == OrderStatus.PENDING).all()
        )

        if not pending_orders:
            return

        # Get unique symbols from pending orders
        symbols = list(set([order.symbol for order in pending_orders]))

        # First, check if assets are still valid (exist and tradable)
        # This catches delistings and symbol changes
        # IMPORTANT: Only expire if we successfully get asset info AND tradable is explicitly False
        # If API call fails (returns None), skip expiration to avoid false positives
        for gtt_order in pending_orders:
            symbol = gtt_order.symbol.upper()
            try:
                # Rate limit before fetching asset info
                rate_limit_alpaca_call_sync()
                asset_info = self.alpaca.get_asset_info(symbol)
                
                # Only expire if we successfully got asset info AND tradable is explicitly False
                # If asset_info is None (API failure), skip to avoid false positives
                if asset_info is not None and asset_info.get("tradable") is False:
                    # Asset exists but is explicitly marked as not tradable - cancel orders
                    logger.info(
                        f"Asset {symbol} is marked as not tradable - expiring GTT order {gtt_order.id}"
                    )
                    self._cancel_gtt_order_due_to_corporate_action(
                        gtt_order=gtt_order,
                        reason="Asset no longer tradable or delisted",
                        action_type="DELISTING",
                        action_subtype="",
                    )
                    continue
                elif asset_info is None:
                    # API call failed - log but don't expire (could be temporary network issue)
                    logger.warning(
                        f"Could not get asset info for {symbol} (API returned None) - skipping expiration check to avoid false positives"
                    )
            except Exception as e:
                # If we can't get asset info due to exception, log but don't cancel
                # This prevents false positives from temporary API failures
                logger.warning(
                    f"Exception getting asset info for {symbol}: {e} - skipping expiration check to avoid false positives"
                )

        # Check for corporate actions in the last 7 days and upcoming 7 days
        # This covers recent actions that might have affected orders
        from datetime import timedelta

        date_from = datetime.utcnow() - timedelta(days=7)
        date_to = datetime.utcnow() + timedelta(days=7)

        # Check for corporate actions that would INVALIDATE GTT orders:
        # - forward_split, reverse_split: Stock splits affect price and quantity
        #   (Alpaca cancels all GTC orders for reverse splits, adjusts for forward splits)
        # - cash_merger, stock_merger: Mergers - symbol may change or be delisted
        # - spinoff: Spinoffs - may affect symbol or share structure
        #
        # DO NOT cancel for:
        # - cash_dividend, stock_dividend: Dividends don't affect order structure
        #
        # Note: Symbol changes are tracked via Assets API (checked separately above)
        action_types = [
            "forward_split",
            "reverse_split",
            "cash_merger",
            "stock_merger",
            "spinoff",
        ]

        try:
            logger.debug(
                f"Checking corporate actions for symbols: {symbols}, types: {action_types}"
            )
            corporate_actions = self.alpaca.get_corporate_actions(
                symbols=symbols,
                action_types=action_types,
                date_from=date_from,
                date_to=date_to,
            )

            if not corporate_actions:
                logger.debug(f"No corporate actions found for symbols: {symbols}")
                return

            logger.info(
                f"Found {len(corporate_actions)} corporate action(s) to process"
            )

            # Create a map of symbols to corporate actions
            # Alpaca API may return symbol in different fields: "symbol", "symbols" (array), etc.
            symbol_to_actions = {}
            for action in corporate_actions:
                # Handle different possible symbol field formats
                symbol = None
                if "symbol" in action:
                    symbol = action.get("symbol", "").upper()
                elif "symbols" in action:
                    # Some actions may have multiple symbols (e.g., mergers)
                    symbols_list = action.get("symbols", [])
                    if isinstance(symbols_list, list) and symbols_list:
                        symbol = str(symbols_list[0]).upper()
                    elif isinstance(symbols_list, str):
                        symbol = symbols_list.upper()

                if symbol:
                    if symbol not in symbol_to_actions:
                        symbol_to_actions[symbol] = []
                    symbol_to_actions[symbol].append(action)
                else:
                    logger.warning(f"Corporate action missing symbol field: {action}")

            # Process each pending order
            for gtt_order in pending_orders:
                symbol = gtt_order.symbol.upper()

                # Check if this symbol has any corporate actions
                if symbol not in symbol_to_actions:
                    continue

                actions = symbol_to_actions[symbol]

                # For each corporate action, check if it affects the order
                for action in actions:
                    # Alpaca API returns action type in "_action_type" field (we add this during flattening)
                    # or check other possible field names
                    action_type_raw = (
                        action.get("_action_type")  # Our added field
                        or action.get("ca_type")
                        or action.get("type")
                        or action.get("action_type")
                        or ""
                    )

                    # Convert plural forms back to singular for our logic
                    # e.g., "forward_splits" -> "forward_split"
                    action_type = action_type_raw.lower().rstrip("s")

                    if not action_type:
                        logger.warning(f"Corporate action missing type field: {action}")
                        continue

                    # Determine if this action should cancel the order
                    # We only cancel for actions that invalidate orders (splits, mergers, spinoffs)
                    # NOT for dividends which don't affect order structure
                    should_cancel = False
                    reason = ""

                    if action_type in ["forward_split", "reverse_split"]:
                        # Stock splits affect price and quantity - cancel GTT orders
                        # Alpaca cancels all GTC orders for reverse splits
                        # Forward splits adjust orders, but we cancel to be safe
                        should_cancel = True
                        split_type = (
                            "Forward" if action_type == "forward_split" else "Reverse"
                        )
                        reason = f"Stock Split ({split_type})"
                    elif action_type in ["cash_merger", "stock_merger"]:
                        # Mergers may change or delist the symbol - cancel GTT orders
                        should_cancel = True
                        merger_type = action_type.replace("_", " ").title()
                        reason = f"Stock Merger ({merger_type})"
                    elif action_type == "spinoff":
                        # Spinoffs may affect the symbol or share structure - cancel GTT orders
                        should_cancel = True
                        reason = "Stock Spinoff"
                    # Explicitly skip dividends - they don't invalidate orders
                    elif action_type in ["cash_dividend", "stock_dividend"]:
                        should_cancel = False
                        logger.debug(
                            f"Skipping dividend action for {symbol} - does not invalidate GTT orders"
                        )
                        continue

                    if should_cancel:
                        # Extract date from various possible fields
                        action_date = (
                            action.get("ex_date")
                            or action.get("ex_dividend_date")
                            or action.get("payable_date")
                            or action.get("record_date")
                            or action.get("effective_date")
                            or action.get("date")
                        )

                        self._cancel_gtt_order_due_to_corporate_action(
                            gtt_order=gtt_order,
                            reason=reason,
                            action_type=action_type,
                            action_subtype="",  # Not always present in response
                            action_date=action_date,
                        )
                        # Only process the first relevant action per symbol
                        break

        except Exception as e:
            logger.error(f"Error checking corporate actions: {e}", exc_info=True)

        self.db.commit()

    def _cancel_gtt_order_due_to_corporate_action(
        self,
        gtt_order: GTTOrder,
        reason: str,
        action_type: str,
        action_subtype: str,
        action_date: str | None = None,
    ):
        """Cancel a GTT order due to corporate action.

        Helper method to cancel all pending order details and mark the order as expired.
        """
        symbol = gtt_order.symbol.upper()
        cancelled_count = 0

        for detail in gtt_order.order_details:
            detail_status = _get_detail_status(self.db, self.alpaca, detail)
            if detail_status == OrderStatus.PENDING.value:
                # Cancel Alpaca order if it exists
                if detail.alpaca_order_id:
                    try:
                        self.alpaca.cancel_order(detail.alpaca_order_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to cancel Alpaca order {detail.alpaca_order_id}: {e}"
                        )

                # Note: Can't set status on detail (it doesn't have status field)
                # The status is tracked in Alpaca cache
                cancelled_count += 1

        if cancelled_count > 0:
            # Update GTT order status
            gtt_order.status = OrderStatus.EXPIRED
            
            # Explicitly add to session to ensure update is tracked
            self.db.add(gtt_order)

            # Log activity with format matching user's example
            date_str = action_date if action_date else "N/A"
            description = f"Your GTT order with id: {gtt_order.id} for symbol {symbol} is expired due to Corporate Action."
            notes = f"Corporate action type: {action_type}, Subtype: {action_subtype}, Date: {date_str}, Reason: {reason}"

            self._log_activity(
                gtt_order_id=gtt_order.id,
                activity_type=ActivityType.CORPORATE_ACTION_EXPIRED,
                symbol=symbol,
                description=description,
                notes=notes,
            )

            logger.info(
                f"GTT order {gtt_order.id} for symbol {symbol} expired due to corporate action: {reason}"
            )

    def send_daily_failed_orders_summary(self) -> bool:
        """Send a daily summary of failed orders at market close.
        
        Groups failures by error type and provides actionable fixes.
        
        Returns:
            True if summary was sent successfully, False otherwise
        """
        try:
            from core.whatsapp_service import get_whatsapp_service

            whatsapp = get_whatsapp_service()
            if not whatsapp.enabled:
                return False

            # Get all failed orders from today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            failed_activities = (
                self.db.query(Activity)
                .filter(
                    Activity.activity_type == ActivityType.ORDER_FAILED,
                    Activity.created_at >= today_start,
                )
                .order_by(Activity.created_at.desc())
                .all()
            )

            if not failed_activities:
                logger.debug("No failed orders today, skipping daily summary")
                return False

            # Group by symbol, then by error type (deduplicate repeated errors)
            failed_by_symbol: dict[str, dict[str, list]] = {}
            for activity in failed_activities:
                symbol = activity.symbol
                # Extract error type from description
                error_key = self._extract_error_key(activity.description)
                
                if symbol not in failed_by_symbol:
                    failed_by_symbol[symbol] = {}
                if error_key not in failed_by_symbol[symbol]:
                    failed_by_symbol[symbol][error_key] = []
                failed_by_symbol[symbol][error_key].append(activity)

            # Count unique errors across all symbols
            total_attempts = len(failed_activities)
            # Use a set comprehension to count globally unique error keys
            unique_errors = len({
                key 
                for symbol_errors in failed_by_symbol.values() 
                for key in symbol_errors.keys()
            })

            # Format summary message - more concise and actionable
            message = "📊 Daily Summary - Failed Orders\n"
            message += f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
            message += f"Attempts: {total_attempts} | Unique Issues: {unique_errors}\n\n"

            for symbol, errors_by_type in failed_by_symbol.items():
                total_symbol_failures = sum(len(errs) for errs in errors_by_type.values())
                message += f"❌ {symbol}: {total_symbol_failures} attempt(s)\n"
                
                for error_key, activities in errors_by_type.items():
                    # Get human-readable error and fix suggestion
                    error_msg, fix_suggestion = self._parse_error_message(error_key)
                    message += f"   • {error_msg} ({len(activities)}x)\n"
                    if fix_suggestion:
                        message += f"     💡 {fix_suggestion}\n"
                
                message += "\n"

            message += "Check GTT Orders page to fix or delete problematic orders."

            # Send message
            success = whatsapp.send_message(message=message)
            if success:
                logger.info(f"✅ Daily failed orders summary sent: {total_attempts} attempts, {unique_errors} unique errors")
            return success

        except Exception as e:
            logger.error(f"Error sending daily failed orders summary: {e}", exc_info=True)
            return False

    def _extract_error_key(self, description: str) -> str:
        """Extract a normalized error key from description for grouping."""
        import json
        import re
        
        # Try to extract Alpaca error code
        code_match = re.search(r'"code":\s*(\d+)', description)
        if code_match:
            return f"code:{code_match.group(1)}"
        
        # Try to extract key error phrases
        if "below $1 minimum" in description.lower() or "minimal amount of order" in description.lower():
            return "min_value"
        if "insufficient" in description.lower():
            return "insufficient_funds"
        if "quantity" in description.lower() and "0.01" in description:
            return "min_qty"
        
        # Default: use first 50 chars of description
        return description[:50] if len(description) > 50 else description

    def _parse_error_message(self, error_key: str) -> tuple[str, str]:
        """Convert error key to human-readable message and fix suggestion.
        
        Returns:
            Tuple of (error_message, fix_suggestion)
        """
        # Known Alpaca error codes
        error_map = {
            "code:40310000": (
                "Order below $1 minimum",
                "Increase quantity so order value ≥ $1"
            ),
            "min_value": (
                "Order below $1 minimum", 
                "Increase quantity so order value ≥ $1"
            ),
            "min_qty": (
                "Quantity below 0.01 minimum",
                "Increase quantity to at least 0.01"
            ),
            "insufficient_funds": (
                "Insufficient buying power",
                "Add funds or reduce order size"
            ),
        }
        
        if error_key in error_map:
            return error_map[error_key]
        
        # For unknown errors, return as-is with no suggestion
        return (error_key, "")

    def _log_activity(
        self,
        gtt_order_id: int | None,
        activity_type: ActivityType,
        symbol: str,
        description: str,
        quantity: int | None = None,
        price: float | None = None,
        side: str | None = None,
        amount: float | None = None,
        notes: str | None = None,
    ):
        """Log an activity."""
        activity = Activity(
            gtt_order_id=gtt_order_id,
            activity_type=activity_type,
            symbol=symbol,
            description=description,
            quantity=quantity,
            price=price,
            side=side,
            amount=amount,
            notes=notes,
        )
        self.db.add(activity)
        self.db.commit()

        # Send WhatsApp notification only for successful orders (ORDER_FILLED)
        # Failed orders will be summarized at market close
        try:
            from core.whatsapp_service import get_whatsapp_service

            whatsapp = get_whatsapp_service()
            
            # Only send immediate notifications for successful orders
            if activity_type == ActivityType.ORDER_FILLED and whatsapp.enabled:
                # Format message
                message = f"✅ ORDER_FILLED\n"
                message += f"Symbol: {symbol}\n"
                message += f"{description}"
                
                if price:
                    message += f"\nPrice: ${price:.2f}"
                if quantity:
                    message += f"\nQty: {quantity}"
                if amount:
                    message += f"\nAmount: ${amount:.2f}"
                
                # Send message (non-blocking, errors are logged but don't affect main flow)
                whatsapp.send_message(message=message)
        except Exception as e:
            # WhatsApp failures should not break the main flow
            logger.debug(f"Could not send WhatsApp notification (non-critical): {e}")