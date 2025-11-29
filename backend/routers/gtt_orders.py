"""GTT (Good-Till-Triggered) order routes."""

import asyncio
import logging
from datetime import datetime
from io import StringIO

import pandas as pd
from alpaca_client import is_crypto_symbol
from asset_cache import is_asset_fractionable
from core.dependencies import AlpacaClientDep
from core.sse_manager import sse_manager
from database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from gtt_service import GTTService
from models import GTTOrderDetail, OrderStatus
from rate_limiter import rate_limit_alpaca_call
from schemas import (
    GTTOrderCreate,
    GTTOrderDetailLink,
    GTTOrderDetailUpdate,
    GTTOrderResponse,
)
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gtt-orders", tags=["gtt-orders"])

# Timeout for Alpaca API calls (8 seconds - fail before frontend's 10s timeout)
ALPACA_API_TIMEOUT = 8.0


def validate_fractional_trading(order_data: GTTOrderCreate) -> tuple[bool, str]:
    """
    Validate that fractional trading is supported or quantities are whole numbers.
    Returns (is_valid, error_message)
    Uses tolerance-based comparison to handle floating point precision issues.
    """
    symbol_upper = order_data.symbol.upper()
    fractionable = is_asset_fractionable(symbol_upper)

    if not fractionable:
        # Use tolerance for floating point comparison (1e-6)
        TOLERANCE = 1e-6

        # Check if initial quantity is fractional (using tolerance)
        if (
            abs(order_data.initial_quantity - round(order_data.initial_quantity))
            > TOLERANCE
        ):
            return (
                False,
                f"Asset {symbol_upper} does not support fractional trading. Quantity must be a whole number.",
            )

        # Check if any calculated quantities in the ladder would be fractional
        current_qty = order_data.initial_quantity
        for i in range(order_data.iterations):
            # Use tolerance-based check instead of exact equality
            if abs(current_qty - round(current_qty)) > TOLERANCE:
                return (
                    False,
                    f"Asset {symbol_upper} does not support fractional trading. Calculated quantity {current_qty:.2f} is fractional.",
                )
            current_qty *= order_data.increment_qty_multiplier

    return True, ""


def enrich_order_details_with_alpaca_data(db: Session, alpaca_client, order_details):
    """Enrich order details with Alpaca data from cache."""
    from alpaca_order_cache import get_alpaca_order_data

    enriched_details = []
    for detail in order_details:
        detail_dict = {
            "id": detail.id,
            "gtt_order_id": detail.gtt_order_id,
            "order_index": detail.order_index,
            "trigger_price": detail.trigger_price,
            "quantity": detail.quantity,
            "fractional_quantity": detail.fractional_quantity,
            "limit_price": detail.limit_price,
            "amount": detail.amount,
            "alpaca_order_id": detail.alpaca_order_id,
            "is_manually_linked": detail.is_manually_linked,
            "time_in_force": detail.time_in_force,
            "status": None,
            "submitted_at": None,
            "filled_at": None,
            "expired_at": None,
        }

        # Fetch Alpaca data from cache if order is linked
        if detail.alpaca_order_id:
            # First try without refresh (fast path)
            cache_data = get_alpaca_order_data(
                db, alpaca_client, detail.alpaca_order_id, force_refresh=False
            )
            
            # If cache is missing filled_avg_price but order is FILLED, force refresh
            # This ensures filled prices are populated even if cache was created before order filled
            if cache_data:
                status = cache_data.get("status", "").upper()
                has_filled_price = cache_data.get("filled_avg_price") is not None
                
                # Force refresh if order is FILLED but missing filled_avg_price
                if status == "FILLED" and not has_filled_price:
                    logger.debug(f"Refreshing cache for FILLED order {detail.alpaca_order_id} missing filled_avg_price")
                    cache_data = get_alpaca_order_data(
                        db, alpaca_client, detail.alpaca_order_id, force_refresh=True
                    )
            
            if cache_data:
                detail_dict["status"] = cache_data.get("status")
                # Timestamps are already ISO strings with timezone from cache
                # FastAPI will serialize datetime objects correctly
                if cache_data.get("submitted_at"):
                    detail_dict["submitted_at"] = cache_data["submitted_at"]
                if cache_data.get("filled_at"):
                    detail_dict["filled_at"] = cache_data["filled_at"]
                if cache_data.get("expired_at"):
                    detail_dict["expired_at"] = cache_data["expired_at"]
                # Always include filled_avg_price - include it even if None so frontend knows it was checked
                filled_price = cache_data.get("filled_avg_price")
                if filled_price is not None:
                    detail_dict["filled_avg_price"] = float(filled_price)
                # Don't set it if None - let frontend handle missing as "-"
        else:
            # No Alpaca order yet - default to PENDING
            detail_dict["status"] = "PENDING"

        enriched_details.append(detail_dict)

    return enriched_details


@router.get("", response_model=list[GTTOrderResponse])
async def get_gtt_orders(
    db: Session = Depends(get_db), alpaca_client: AlpacaClientDep = ...
):
    """Get all GTT orders with Alpaca data from cache."""
    try:
        service = GTTService(db)
        orders = service.get_all_gtt_orders()

        # Enrich order details with Alpaca data
        enriched_orders = []
        for order in orders:
            order_dict = {
                "id": order.id,
                "symbol": order.symbol,
                "initial_trigger_price": order.initial_trigger_price,
                "initial_quantity": order.initial_quantity,
                "increment_qty_multiplier": order.increment_qty_multiplier,
                "decrement_price_multiplier": order.decrement_price_multiplier,
                "iterations": order.iterations,
                "status": order.status,
                "filled_count": order.filled_count,
                "total_count": order.total_count,
                "total_value": order.total_value,
                "locked_buying_power": order.locked_buying_power,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "order_details": enrich_order_details_with_alpaca_data(
                    db, alpaca_client, order.order_details
                ),
            }
            enriched_orders.append(order_dict)

        return enriched_orders
    except Exception as e:
        logger.error(f"API error: GET /api/gtt-orders, Error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}", response_model=GTTOrderResponse)
async def get_gtt_order(
    order_id: int, db: Session = Depends(get_db), alpaca_client: AlpacaClientDep = ...
):
    """Get a specific GTT order with Alpaca data from cache."""
    try:
        service = GTTService(db)
        order = service.get_gtt_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="GTT order not found")

        # Enrich order details with Alpaca data
        order_dict = {
            "id": order.id,
            "symbol": order.symbol,
            "initial_trigger_price": order.initial_trigger_price,
            "initial_quantity": order.initial_quantity,
            "increment_qty_multiplier": order.increment_qty_multiplier,
            "decrement_price_multiplier": order.decrement_price_multiplier,
            "iterations": order.iterations,
            "status": order.status,
            "filled_count": order.filled_count,
            "total_count": order.total_count,
            "total_value": order.total_value,
            "locked_buying_power": order.locked_buying_power,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "order_details": enrich_order_details_with_alpaca_data(
                db, alpaca_client, order.order_details
            ),
        }

        return order_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: GET /api/gtt-orders/{order_id}, Error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=GTTOrderResponse)
async def create_gtt_order(
    order_data: GTTOrderCreate,
    confirm_rounding: bool = False,
    confirm_duplicates: bool = False,
    db: Session = Depends(get_db),
):
    """Create a new GTT order with validation for fractional trading and duplicates.

    Workflow:
    - First call (confirm_rounding=False, confirm_duplicates=False): Validates and returns warnings
    - Second call (confirm_rounding=True, confirm_duplicates=True): Creates order with auto-rounding

    Returns validation errors with details that frontend can display in a preview modal.
    """
    from gtt_service import validate_and_prepare_order

    logger.info(
        f"[Manual Create] confirm_rounding={confirm_rounding}, confirm_duplicates={confirm_duplicates}"
    )

    try:
        # Validate order (check fractional trading and duplicates)
        validation = validate_and_prepare_order(
            db, order_data, check_duplicates=True, auto_round=confirm_rounding
        )

        # If validation failed (has warnings or duplicates) and user hasn't confirmed
        if not validation["valid"]:
            # If user hasn't confirmed either warnings or duplicates, return them
            if (validation["warnings"] and not confirm_rounding) or (
                validation["duplicate"] and not confirm_duplicates
            ):
                error_response = {
                    "detail": validation["error"] or "Validation warnings detected"
                }

                if validation["warnings"]:
                    error_response["warnings"] = validation["warnings"]

                if validation["duplicate"]:
                    error_response["duplicate"] = validation["duplicate"]

                raise HTTPException(status_code=400, detail=error_response)

            # If we reach here, user has confirmed warnings/duplicates
            # Override validation result to allow creation
            if (validation["duplicate"] and confirm_duplicates) or (
                validation["warnings"] and confirm_rounding
            ):
                validation["valid"] = True
                logger.info(
                    "[Manual Create] User confirmed warnings/duplicates, proceeding with creation"
                )

            # If user confirmed but there's still an error (shouldn't happen), return error
            if (
                validation["error"]
                and not validation["warnings"]
                and not validation["duplicate"]
            ):
                raise HTTPException(status_code=400, detail=validation["error"])

        # Create the order
        service = GTTService(db)
        order = service.create_gtt_order(validation["order_data"], skip_validation=True)
        logger.info(f"[Manual Create] Order created successfully: {order.id}")

        # Broadcast SSE event for real-time updates (synchronous call)
        # Note: broadcast is async but we call it synchronously - it will queue the event
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create task
                asyncio.create_task(
                    sse_manager.broadcast(
                        "order_created", {"order_id": order.id, "symbol": order.symbol}
                    )
                )
            else:
                # If no loop running, run it
                loop.run_until_complete(
                    sse_manager.broadcast(
                        "order_created", {"order_id": order.id, "symbol": order.symbol}
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast SSE event: {e}")

        return order

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error: Resource=GTT order, Error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API error: POST /api/gtt-orders, Error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", response_model=list[GTTOrderResponse])
async def create_gtt_orders_bulk(
    orders: list[GTTOrderCreate], db: Session = Depends(get_db)
):
    """Create multiple GTT orders."""
    try:
        service = GTTService(db)
        created_orders = []
        for order_data in orders:
            order = service.create_gtt_order(order_data)
            created_orders.append(order)
        return created_orders
    except Exception as e:
        logger.error(f"Error creating bulk GTT orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-csv")
async def upload_csv_gtt_orders(
    file: UploadFile = File(...),
    confirm_rounding: str = Form("false"),
    confirm_duplicates: str = Form("false"),
    db: Session = Depends(get_db),
):
    """Upload CSV file with GTT orders. Supports two formats:
    1. Simple format: symbol, initial_trigger_price, initial_quantity, increment_qty_multiplier, decrement_price_multiplier, iterations
    2. Ladder format: Symbol, Amt 1, Price 1, Amt 2, Price 2, ... (up to 5 levels)

    Workflow:
    - First call (confirm_rounding=false, confirm_duplicates=false): Validates and returns warnings
    - Second call (confirm_rounding=true, confirm_duplicates=true): Creates orders with auto-rounding, skipping duplicates
    """
    # Convert params from string to boolean
    confirm_rounding_bool = confirm_rounding.lower() in ("true", "1", "yes")
    confirm_duplicates_bool = confirm_duplicates.lower() in ("true", "1", "yes")
    logger.info(
        f"[CSV Upload] confirm_rounding={confirm_rounding_bool}, confirm_duplicates={confirm_duplicates_bool}"
    )

    try:
        # Read CSV file
        contents = await file.read()
        logger.info(
            f"[DEBUG] Received CSV file '{file.filename}', size: {len(contents)} bytes"
        )
        try:
            # Try UTF-8 first, fallback to other encodings if needed
            csv_text = contents.decode("utf-8")
            logger.info(f"CSV decoded as UTF-8. First 200 chars: {csv_text[:200]}")
            df = pd.read_csv(StringIO(csv_text))
            logger.info(
                f"CSV parsed successfully. Columns: {list(df.columns)}, Rows: {len(df)}"
            )
            logger.info(
                f"First row data: {df.iloc[0].to_dict() if len(df) > 0 else 'No rows'}"
            )
        except UnicodeDecodeError as e:
            logger.error(f"UTF-8 decode error: {e}, trying latin-1")
            try:
                csv_text = contents.decode("latin-1")
                df = pd.read_csv(StringIO(csv_text))
                logger.info("CSV parsed successfully with latin-1 encoding")
            except Exception as e2:
                logger.error(f"Error parsing CSV with latin-1: {e2}", exc_info=True)
                raise HTTPException(
                    status_code=400, detail=f"Error parsing CSV file encoding: {e2!s}"
                )
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Error parsing CSV file: {e!s}"
            )

        # Clean up column names (remove trailing/leading spaces)
        df.columns = df.columns.str.strip()
        logger.info(
            f"[CSV Upload] Cleaned column names: {list(df.columns)}, Rows: {len(df)}"
        )

        orders_to_validate = []

        # Check if it's the ladder format (has "Amt 1", "Price 1" columns)
        is_ladder_format = "Amt 1" in df.columns and "Price 1" in df.columns
        logger.info(
            f"[CSV Upload] Format: {'Ladder' if is_ladder_format else 'Simple'}"
        )

        if is_ladder_format:
            # Ladder format: parse explicit amounts and prices
            logger.info(f"[CSV Upload] Processing {len(df)} rows in ladder format")

            for idx, row in df.iterrows():
                try:
                    if "Symbol" not in row.index:
                        logger.error(f"Row {idx}: 'Symbol' column not found")
                        continue

                    symbol = str(row["Symbol"]).upper().strip()
                    if pd.isna(symbol) or symbol == "":
                        logger.warning(f"Row {idx}: Empty symbol, skipping")
                        continue

                    logger.info(f"[CSV Upload] Row {idx}: Processing {symbol}")

                    # Extract amounts and prices (up to 5 levels)
                    amounts = []
                    prices = []
                    for i in range(1, 6):  # Amt 1-5, Price 1-5
                        amt_col = f"Amt {i}"
                        price_col = f"Price {i}"
                        if amt_col in df.columns and price_col in df.columns:
                            amt_val = row[amt_col]
                            price_val = row[price_col]
                            if pd.notna(amt_val) and pd.notna(price_val):
                                try:
                                    # Remove $ sign and convert
                                    price_str = (
                                        str(price_val)
                                        .replace("$", "")
                                        .replace(",", "")
                                        .strip()
                                    )
                                    amounts.append(float(amt_val))
                                    prices.append(float(price_str))
                                except (ValueError, TypeError) as e:
                                    logger.warning(
                                        f"Row {idx}, Level {i}: Error converting value: {e}"
                                    )
                                    continue

                    if len(amounts) < 2:
                        logger.warning(
                            f"Row {idx} ({symbol}): Need at least 2 levels, got {len(amounts)}, skipping"
                        )
                        continue

                    # Calculate multipliers from the ladder
                    initial_price = prices[0]
                    initial_qty = amounts[0]

                    # Calculate increment multiplier (how much qty increases)
                    increment_multiplier = (
                        amounts[1] / amounts[0] if amounts[0] > 0 else 1.2
                    )

                    # Calculate decrement multiplier (how much price decreases)
                    decrement_multiplier = (
                        prices[1] / prices[0] if prices[0] > 0 else 0.9
                    )

                    iterations = len(amounts)

                    # Validate multipliers
                    if increment_multiplier <= 0:
                        logger.warning(
                            f"Row {idx} ({symbol}): Invalid increment_multiplier {increment_multiplier}, skipping"
                        )
                        continue
                    if decrement_multiplier <= 0 or decrement_multiplier >= 1:
                        logger.warning(
                            f"Row {idx} ({symbol}): Invalid decrement_multiplier {decrement_multiplier}, skipping"
                        )
                        continue
                    if iterations <= 0 or iterations > 20:
                        logger.warning(
                            f"Row {idx} ({symbol}): Invalid iterations {iterations}, skipping"
                        )
                        continue

                    # Create order data (validation happens later)
                    # Handle crypto time_in_force: crypto only supports GTC/IOC, not DAY
                    # For ambiguous symbols (BCH, LINK, SOL), check asset class from Alpaca
                    time_in_force = str(row.get("time_in_force", "DAY")).upper()
                    ambiguous_symbols = ["BCH", "LINK", "SOL"]
                    is_crypto = False
                    
                    if symbol.upper() in ambiguous_symbols:
                        # Check asset class from Alpaca API for ambiguous symbols
                        try:
                            from alpaca_client import AlpacaClient
                            alpaca_client = AlpacaClient()
                            asset_info = alpaca_client.get_asset_info(symbol.upper())
                            if asset_info and asset_info.get("class", "").upper() == "CRYPTO":
                                is_crypto = True
                                logger.info(f"Symbol {symbol} detected as crypto via Alpaca asset class")
                            else:
                                logger.info(f"Symbol {symbol} detected as stock via Alpaca asset class")
                        except Exception as e:
                            logger.warning(f"Could not check asset class for {symbol}, defaulting to stock: {e}")
                            is_crypto = False
                    else:
                        is_crypto = is_crypto_symbol(symbol)
                    
                    if is_crypto:
                        if time_in_force == "DAY":
                            logger.info(
                                f"Crypto symbol {symbol} - converting DAY to GTC (crypto doesn't support DAY)"
                            )
                            time_in_force = "GTC"
                        elif time_in_force not in ["GTC", "IOC"]:
                            logger.warning(
                                f"Crypto symbol {symbol} - invalid time_in_force {time_in_force}, defaulting to GTC"
                            )
                            time_in_force = "GTC"

                    order_data = GTTOrderCreate(
                        symbol=symbol,
                        initial_trigger_price=initial_price,
                        initial_quantity=initial_qty,
                        increment_qty_multiplier=increment_multiplier,
                        decrement_price_multiplier=decrement_multiplier,
                        iterations=iterations,
                        time_in_force=time_in_force,
                    )
                    orders_to_validate.append(order_data)
                    logger.info(f"Row {idx} ({symbol}): Parsed successfully")

                except Exception as e:
                    logger.error(f"Row {idx}: Error parsing - {e}", exc_info=True)
                    continue

        # Simple format: symbol, initial_trigger_price, etc.
        elif "symbol" in df.columns or "Symbol" in df.columns:
            symbol_col = "symbol" if "symbol" in df.columns else "Symbol"
            required_columns = [
                symbol_col,
                "initial_trigger_price",
                "initial_quantity",
                "increment_qty_multiplier",
                "decrement_price_multiplier",
                "iterations",
            ]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required columns: {', '.join(missing_columns)}",
                )

            logger.info(f"[CSV Upload] Processing {len(df)} rows in simple format")
            for idx, row in df.iterrows():
                try:
                    symbol = str(row[symbol_col]).upper().strip()
                    # Handle crypto time_in_force: crypto only supports GTC/IOC, not DAY
                    time_in_force = str(row.get("time_in_force", "DAY")).upper()
                    if is_crypto_symbol(symbol):
                        if time_in_force == "DAY":
                            logger.info(
                                f"Crypto symbol {symbol} - converting DAY to GTC (crypto doesn't support DAY)"
                            )
                            time_in_force = "GTC"
                        elif time_in_force not in ["GTC", "IOC"]:
                            logger.warning(
                                f"Crypto symbol {symbol} - invalid time_in_force {time_in_force}, defaulting to GTC"
                            )
                            time_in_force = "GTC"

                    order_data = GTTOrderCreate(
                        symbol=symbol,
                        initial_trigger_price=float(row["initial_trigger_price"]),
                        initial_quantity=float(row["initial_quantity"]),
                        increment_qty_multiplier=float(row["increment_qty_multiplier"]),
                        decrement_price_multiplier=float(
                            row["decrement_price_multiplier"]
                        ),
                        iterations=int(row["iterations"]),
                        time_in_force=time_in_force,
                    )
                    orders_to_validate.append(order_data)
                except Exception as e:
                    logger.warning(f"Row {idx}: Error parsing - {e}")
                    continue
        else:
            available_columns = ", ".join(df.columns.tolist())
            raise HTTPException(
                status_code=400,
                detail=f"CSV format not recognized. Expected either ladder format (Symbol, Amt 1, Price 1, ...) or simple format (symbol, initial_trigger_price, ...). Found columns: {available_columns}",
            )

        if not orders_to_validate:
            raise HTTPException(
                status_code=400,
                detail=f"No valid orders found in CSV. Processed {len(df)} row(s)",
            )

        logger.info(
            f"[CSV Upload] Parsed {len(orders_to_validate)} orders, validating..."
        )

        # Use unified validation for all orders
        from gtt_service import validate_and_prepare_order

        rounding_warnings = []
        duplicate_warnings = []
        valid_orders = []
        failed_orders = []

        # List of ambiguous symbols that are often confused (Stock vs Crypto)
        # These should ALWAYS be validated strictly in CSV
        ambiguous_crypto_tickers = {
            "LINK": "LINK/USD",
            "SOL": "SOL/USD",
            "BCH": "BCH/USD",
            "LTC": "LTC/USD",
            "BTC": "BTC/USD",
            "ETH": "ETH/USD",
            "DOGE": "DOGE/USD",
            "UNI": "UNI/USD",
            "AAVE": "AAVE/USD",
            "AVAX": "AVAX/USD"
        }

        for order_data in orders_to_validate:
            # CSV VALIDATION: Check for ambiguous crypto symbols without /USD suffix
            # If user provides "LINK" (stock) but likely means crypto, fail the row
            symbol_upper = order_data.symbol.upper().strip()
            
            # If it's an ambiguous ticker (e.g. "LINK") AND does NOT have "/" (e.g. not "LINK/USD")
            if symbol_upper in ambiguous_crypto_tickers and "/" not in symbol_upper:
                expected_crypto = ambiguous_crypto_tickers[symbol_upper]
                error_msg = (
                    f"Ambiguous symbol '{symbol_upper}'. Did you mean '{expected_crypto}' (Crypto) "
                    f"or '{symbol_upper}' (Stock)? Please use '{expected_crypto}' for crypto to avoid "
                    f"accidental stock purchases."
                )
                failed_orders.append(
                    {
                        "symbol": symbol_upper,
                        "error": error_msg,
                    }
                )
                continue

            # Validate with auto-rounding (frontend always sends confirm_rounding=true now)
            # Check duplicates based on confirm_duplicates flag
            check_dups = True if not confirm_duplicates_bool else False

            validation = validate_and_prepare_order(
                db, order_data, check_duplicates=check_dups, auto_round=True
            )

            # Collect rounding warnings (for display purposes)
            if validation["warnings"]:
                rounding_warning = next(
                    (
                        w
                        for w in validation["warnings"]
                        if w.get("requires_confirmation")
                    ),
                    None,
                )
                if rounding_warning:
                    rounding_warnings.append(rounding_warning)

            # Collect duplicate warnings
            if validation["duplicate"]:
                duplicate_warnings.append(validation["duplicate"])
                continue  # Skip this order - don't add to valid_orders

            # If order is valid (even with rounding warnings), add to creation list
            # Rounding warnings are informational - we'll still create with rounded values
            if validation["valid"]:
                valid_orders.append(validation["order_data"])
            else:
                # Other validation errors (not rounding or duplicates)
                if not validation["warnings"] and not validation["duplicate"]:
                    failed_orders.append(
                        {
                            "symbol": order_data.symbol,
                            "error": validation["error"] or "Unknown error",
                        }
                    )

        # Proceed with order creation
        # Note: valid_orders already excludes duplicates (they were skipped above)
        # Rounding warnings are informational - orders will be created with rounded values

        # Special case: ALL orders were duplicates or failed
        if not valid_orders:
            # If we have duplicate warnings, return them (not an error - just info)
            if duplicate_warnings:
                logger.info(
                    f"[CSV Upload] All orders are duplicates: {len(duplicate_warnings)}"
                )
                return {
                    "message": f"No orders created - all {len(duplicate_warnings)} order(s) already exist",
                    "orders": [],
                    "created_count": 0,
                    "failed_count": len(failed_orders),
                    "duplicate_warnings": duplicate_warnings,
                    "rounding_warnings": rounding_warnings,
                    "failed_orders": failed_orders if failed_orders else None,
                }

            # Otherwise, it's an error
            error_msg = "No valid orders to create"
            if failed_orders:
                error_details = "; ".join(
                    [f"{fo['symbol']}: {fo['error']}" for fo in failed_orders[:3]]
                )
                error_msg += f". Errors: {error_details}"
            raise HTTPException(status_code=400, detail=error_msg)

        # Create orders (skip validation since we already validated)
        service = GTTService(db)
        created_orders = []
        creation_failed_orders = []

        for order_data in valid_orders:
            try:
                # Skip validation since we already validated and auto-rounded
                order = service.create_gtt_order(order_data, skip_validation=True)
                created_orders.append(order)
                logger.info(f"[CSV Upload] Created GTT order for {order_data.symbol}")
            except Exception as e:
                logger.error(
                    f"[CSV Upload] Error creating order for {order_data.symbol}: {e}",
                    exc_info=True,
                )
                creation_failed_orders.append(
                    {"symbol": order_data.symbol, "error": str(e)}
                )

        # Combine all failures
        all_failed = failed_orders + creation_failed_orders

        response = {
            "message": f"Created {len(created_orders)} GTT order(s)",
            "orders": created_orders,
            "created_count": len(created_orders),
            "failed_count": len(all_failed),
        }

        # Include warnings in response (informational)
        if rounding_warnings:
            response["rounding_warnings"] = rounding_warnings
        if duplicate_warnings:
            response["duplicate_warnings"] = duplicate_warnings
        if all_failed:
            response["failed_orders"] = all_failed

        logger.info(
            f"[CSV Upload] Complete: {len(created_orders)} created, {len(all_failed)} failed, {len(duplicate_warnings)} duplicates, {len(rounding_warnings)} rounding warnings"
        )

        # Broadcast SSE event for bulk order creation
        if created_orders:
            import asyncio

            asyncio.create_task(
                sse_manager.broadcast(
                    "orders_bulk_created",
                    {
                        "count": len(created_orders),
                        "symbols": [o.symbol for o in created_orders[:10]],
                    },  # Limit to first 10 symbols
                )
            )

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}")
async def delete_gtt_order(order_id: int, db: Session = Depends(get_db)):
    """Delete a GTT order."""
    try:
        service = GTTService(db)

        # Get order symbol before deleting (for SSE broadcast)
        order = service.get_gtt_order(order_id)
        order_symbol = order.symbol if order else None

        success = service.delete_gtt_order(order_id)
        if not success:
            raise HTTPException(status_code=404, detail="GTT order not found")

        # Broadcast SSE event for real-time updates
        import asyncio

        asyncio.create_task(
            sse_manager.broadcast(
                "order_deleted", {"order_id": order_id, "symbol": order_symbol}
            )
        )

        return {"message": "GTT order deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting GTT order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}/details/{detail_id}")
async def delete_order_detail(
    order_id: int, detail_id: int, db: Session = Depends(get_db)
):
    """Delete an individual order detail from a GTT order."""
    try:
        logger.info(f"Deleting order detail: OrderID={order_id}, DetailID={detail_id}")
        service = GTTService(db)

        # Verify the detail exists and belongs to the order
        detail = (
            db.query(GTTOrderDetail)
            .filter(
                GTTOrderDetail.id == detail_id, GTTOrderDetail.gtt_order_id == order_id
            )
            .first()
        )

        if not detail:
            logger.warning(f"Order detail {detail_id} not found for order {order_id}")
            detail_exists = (
                db.query(GTTOrderDetail).filter(GTTOrderDetail.id == detail_id).first()
            )
            if detail_exists:
                logger.warning(
                    f"Order detail {detail_id} exists but belongs to order {detail_exists.gtt_order_id}, not {order_id}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Order detail {detail_id} belongs to a different order ({detail_exists.gtt_order_id}), not {order_id}",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Order detail {detail_id} not found for order {order_id}. It may have already been deleted.",
            )

        logger.debug(
            f"Order detail found: OrderID={order_id}, DetailID={detail_id}, Symbol={detail.gtt_order.symbol}"
        )
        success = service.delete_order_detail(detail_id)

        if not success:
            logger.warning(f"Delete operation returned False for detail {detail_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Order detail {detail_id} not found. It may have already been deleted.",
            )

        logger.info(f"Order detail deleted: OrderID={order_id}, DetailID={detail_id}")

        # Broadcast SSE event for real-time updates
        import asyncio

        asyncio.create_task(
            sse_manager.broadcast(
                "order_updated",
                {
                    "order_id": order_id,
                    "action": "detail_deleted",
                    "detail_id": detail_id,
                },
            )
        )

        return {"message": "Order detail deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        import traceback

        error_traceback = traceback.format_exc()
        logger.error(
            f"Error deleting order detail {detail_id} for order {order_id}: [{error_type}] {error_msg}\n{error_traceback}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete order detail: [{error_type}] {error_msg}",
        )


@router.put("/{order_id}/details/{detail_id}")
async def update_order_detail(
    order_id: int,
    detail_id: int,
    update_data: GTTOrderDetailUpdate,
    db: Session = Depends(get_db),
    alpaca_client: AlpacaClientDep = ...,
):
    """Update an order detail (edit price, quantity, etc.)."""
    try:
        # Verify the detail exists and belongs to the order
        detail = (
            db.query(GTTOrderDetail)
            .filter(
                GTTOrderDetail.id == detail_id, GTTOrderDetail.gtt_order_id == order_id
            )
            .first()
        )

        if not detail:
            raise HTTPException(
                status_code=404, detail=f"Order detail {detail_id} not found"
            )

        # Cannot edit if already linked to an Alpaca order
        if detail.is_manually_linked or detail.alpaca_order_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot edit order detail that is already linked to an Alpaca order",
            )

        # Cannot edit if already filled (check cache for status)
        if detail.alpaca_order_id:
            from alpaca_order_cache import get_alpaca_order_data

            cache_data = get_alpaca_order_data(
                db, alpaca_client, detail.alpaca_order_id, force_refresh=False
            )
            if cache_data and cache_data.get("status") == "FILLED":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot edit order detail that is already filled",
                )

        # Update fields
        if update_data.trigger_price is not None:
            detail.trigger_price = update_data.trigger_price

        if update_data.quantity is not None:
            detail.quantity = update_data.quantity

        if update_data.limit_price is not None:
            detail.limit_price = update_data.limit_price

        if update_data.time_in_force is not None:
            detail.time_in_force = update_data.time_in_force

        # Recalculate amount
        detail.amount = detail.quantity * detail.limit_price
        detail.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(detail)

        logger.info(f"Updated order detail {detail_id} for order {order_id}")

        # Broadcast SSE event for real-time updates
        import asyncio

        asyncio.create_task(
            sse_manager.broadcast(
                "order_updated",
                {
                    "order_id": order_id,
                    "action": "detail_updated",
                    "detail_id": detail_id,
                },
            )
        )

        return {"message": "Order detail updated successfully", "detail": detail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order detail: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/details/{detail_id}/link")
async def link_order_detail(
    order_id: int,
    detail_id: int,
    link_data: GTTOrderDetailLink,
    db: Session = Depends(get_db),
    alpaca_client: AlpacaClientDep = ...,
):
    """Manually link an order detail to an executed Alpaca order."""
    try:
        # Verify the detail exists and belongs to the order
        detail = (
            db.query(GTTOrderDetail)
            .filter(
                GTTOrderDetail.id == detail_id, GTTOrderDetail.gtt_order_id == order_id
            )
            .first()
        )

        if not detail:
            raise HTTPException(
                status_code=404, detail=f"Order detail {detail_id} not found"
            )

        # Check if this Alpaca order is already linked to another order detail
        existing_link = (
            db.query(GTTOrderDetail)
            .filter(
                GTTOrderDetail.alpaca_order_id == link_data.alpaca_order_id,
                GTTOrderDetail.id != detail_id,  # Exclude the current detail
            )
            .first()
        )

        if existing_link:
            raise HTTPException(
                status_code=400,
                detail=f"Alpaca order {link_data.alpaca_order_id} is already linked to order detail #{existing_link.id}",
            )

        # Link order and cache Alpaca data immediately
        detail.alpaca_order_id = link_data.alpaca_order_id
        detail.is_manually_linked = True

        # Cache Alpaca order data immediately (force refresh to get latest)
        from alpaca_order_cache import get_alpaca_order_data

        cache_data = get_alpaca_order_data(
            db, alpaca_client, link_data.alpaca_order_id, force_refresh=True
        )

        if not cache_data:
            raise HTTPException(
                status_code=404,
                detail=f"Alpaca order {link_data.alpaca_order_id} not found",
            )

        # Update order parameters from Alpaca order if available (with rate limiting)
        try:
            await rate_limit_alpaca_call()
            alpaca_order = await asyncio.wait_for(
                run_in_threadpool(alpaca_client.get_order, link_data.alpaca_order_id),
                timeout=ALPACA_API_TIMEOUT,
            )
        except TimeoutError:
            logger.warning(
                f"Timeout fetching Alpaca order {link_data.alpaca_order_id} - continuing without update"
            )
            alpaca_order = None
        except Exception as e:
            logger.error(
                f"Error fetching Alpaca order {link_data.alpaca_order_id}: {e}",
                exc_info=True,
            )
            alpaca_order = None

        if alpaca_order:
            if alpaca_order.get("limit_price"):
                detail.limit_price = float(alpaca_order["limit_price"])

            if alpaca_order.get("filled_qty"):
                detail.quantity = int(float(alpaca_order["filled_qty"]))
            elif alpaca_order.get("quantity"):
                detail.quantity = int(float(alpaca_order["quantity"]))

            # Recalculate amount
            detail.amount = detail.quantity * detail.limit_price

        detail.updated_at = datetime.utcnow()

        # Update parent GTT order filled_count based on cached status
        gtt_order = detail.gtt_order
        from alpaca_order_cache import get_alpaca_order_data

        filled_count = 0
        for d in gtt_order.order_details:
            if d.alpaca_order_id:
                d_cache = get_alpaca_order_data(
                    db, alpaca_client, d.alpaca_order_id, force_refresh=False
                )
                if d_cache and d_cache.get("status") == "FILLED":
                    filled_count += 1

        gtt_order.filled_count = filled_count

        if filled_count == gtt_order.total_count:
            gtt_order.status = OrderStatus.FILLED
        elif filled_count > 0:
            gtt_order.status = OrderStatus.PARTIALLY_FILLED

        # Recalculate locked buying power based on order statuses
        from core.gtt_order_status_service import GTTOrderStatusService
        locked_amount = GTTOrderStatusService._calculate_locked_buying_power(
            db, alpaca_client, gtt_order
        )
        gtt_order.locked_buying_power = locked_amount

        db.commit()
        db.refresh(detail)

        logger.info(
            f"Linked order detail {detail_id} to Alpaca order {link_data.alpaca_order_id}"
        )

        # Enrich the detail with Alpaca data before returning (includes filled_avg_price)
        enriched_detail = enrich_order_details_with_alpaca_data(db, alpaca_client, [detail])
        enriched_detail_dict = enriched_detail[0] if enriched_detail else None

        # Broadcast SSE event for real-time updates
        asyncio.create_task(
            sse_manager.broadcast(
                "order_updated",
                {
                    "order_id": order_id,
                    "action": "detail_linked",
                    "detail_id": detail_id,
                },
            )
        )

        return {
            "message": "Order detail linked successfully", 
            "detail": enriched_detail_dict if enriched_detail_dict else detail
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking order detail: {e}")
        import traceback

        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}/details/{detail_id}/link")
async def unlink_order_detail(
    order_id: int,
    detail_id: int,
    db: Session = Depends(get_db),
    alpaca_client: AlpacaClientDep = ...,
):
    """Unlink an order detail from its Alpaca order."""
    try:
        # Verify the detail exists and belongs to the order
        detail = (
            db.query(GTTOrderDetail)
            .filter(
                GTTOrderDetail.id == detail_id, GTTOrderDetail.gtt_order_id == order_id
            )
            .first()
        )

        if not detail:
            raise HTTPException(
                status_code=404, detail=f"Order detail {detail_id} not found"
            )

        if not detail.alpaca_order_id:
            raise HTTPException(
                status_code=400,
                detail="Order detail is not linked to an Alpaca order",
            )

        # Store the Alpaca order ID before unlinking (for logging)
        alpaca_order_id = detail.alpaca_order_id

        # Unlink the order
        detail.alpaca_order_id = None
        detail.is_manually_linked = False
        detail.updated_at = datetime.utcnow()

        # Update parent GTT order filled_count based on remaining linked orders
        gtt_order = detail.gtt_order
        from alpaca_order_cache import get_alpaca_order_data

        filled_count = 0
        for d in gtt_order.order_details:
            if d.alpaca_order_id:
                d_cache = get_alpaca_order_data(
                    db, alpaca_client, d.alpaca_order_id, force_refresh=False
                )
                if d_cache and d_cache.get("status") == "FILLED":
                    filled_count += 1

        gtt_order.filled_count = filled_count

        if filled_count == gtt_order.total_count:
            gtt_order.status = OrderStatus.FILLED
        elif filled_count > 0:
            gtt_order.status = OrderStatus.PARTIALLY_FILLED
        else:
            gtt_order.status = OrderStatus.PENDING

        # Recalculate locked buying power based on order statuses
        from core.gtt_order_status_service import GTTOrderStatusService
        locked_amount = GTTOrderStatusService._calculate_locked_buying_power(
            db, alpaca_client, gtt_order
        )
        gtt_order.locked_buying_power = locked_amount

        db.commit()
        db.refresh(detail)

        logger.info(
            f"Unlinked order detail {detail_id} from Alpaca order {alpaca_order_id}"
        )

        # Broadcast SSE event for real-time updates
        asyncio.create_task(
            sse_manager.broadcast(
                "order_updated",
                {
                    "order_id": order_id,
                    "action": "detail_unlinked",
                    "detail_id": detail_id,
                },
            )
        )

        return {"message": "Order detail unlinked successfully", "detail": detail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking order detail: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
