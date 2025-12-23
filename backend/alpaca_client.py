"""Alpaca API client wrapper."""

import logging
from datetime import datetime, timedelta

import requests
from alpaca.common.exceptions import APIError
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import (
    CryptoBarsRequest,
    StockBarsRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest
from config import settings

logger = logging.getLogger(__name__)


def is_crypto_symbol(symbol: str, check_asset_class: bool = False) -> bool:
    """Check if symbol is a crypto pair.

    Crypto symbols can be in two formats:
    - Trading format: BTC/USD, ETH/USD, SOL/USD (with '/' separator)
    - Position format: BTCUSD, ETHUSD (without '/' separator, legacy format)

    Stock symbols: TSLA, AAPL, MSFT (no crypto pairs)

    Detection logic:
    1. Contains '/' -> definitely crypto
    2. Ends with USD/USDT/USDC and length > 3 -> likely crypto (e.g., BTCUSD, ETHUSD)
    3. Common crypto prefixes: BTC, ETH, SOL, DOGE, MATIC, etc.
    4. If check_asset_class=True and symbol is ambiguous, check Alpaca API for asset class
    
    Ambiguous symbols (can be both crypto and stock):
    - BCH (Bitcoin Cash crypto vs Banco de Chile stock)
    - LINK (Chainlink crypto vs Interlink Electronics stock)
    - SOL (Solana crypto vs Emeren Group stock)
    """
    symbol_upper = symbol.upper()

    # Check for '/' separator (trading format) - definitely crypto
    if "/" in symbol_upper:
        return True

    # Check for crypto pair format without slash (position format)
    # Common crypto quote currencies
    crypto_quotes = ["USD", "USDT", "USDC", "BTC", "ETH"]
    for quote in crypto_quotes:
        if symbol_upper.endswith(quote) and len(symbol_upper) > len(quote):
            # Check if it's a known crypto base (not a stock ticker)
            base = symbol_upper[: -len(quote)]
            # Common crypto bases (3-5 letters typically)
            # NOTE: Removed ambiguous symbols (BCH, LINK, SOL) - check asset class instead
            common_crypto_bases = [
                "BTC",
                "ETH",
                "DOGE",
                "MATIC",
                "AVAX",
                "ALGO",
                "SHIB",
                "ADA",
                "DOT",
                "LTC",
                "XRP",
                "ETC",
            ]
            if base in common_crypto_bases:
                return True

    # Ambiguous symbols that could be crypto or stock
    # Check asset class from Alpaca if requested
    ambiguous_symbols = ["BCH", "LINK", "SOL"]
    if symbol_upper in ambiguous_symbols and check_asset_class:
        try:
            # Try to get asset info to check class
            # Note: This requires AlpacaClient instance, so we'll handle it at call site
            # For now, return False (treat as stock) if ambiguous and not checking
            pass
        except Exception:
            pass
    
    # If ambiguous symbol and not checking asset class, default to False (stock)
    if symbol_upper in ambiguous_symbols:
        return False

    return False


def normalize_crypto_symbol(symbol: str) -> str:
    """Normalize crypto symbol to trading format (BTC/USD).

    Converts position format (BTCUSD) to trading format (BTC/USD).
    Returns symbol unchanged if already in trading format or not crypto.
    """
    symbol_upper = symbol.upper()

    # Already in trading format
    if "/" in symbol_upper:
        return symbol_upper

    # Try to convert position format to trading format
    crypto_quotes = ["USD", "USDT", "USDC"]
    for quote in crypto_quotes:
        if symbol_upper.endswith(quote) and len(symbol_upper) > len(quote):
            base = symbol_upper[: -len(quote)]
            # Return in trading format
            return f"{base}/{quote}"

    # Return unchanged if not crypto or can't normalize
    return symbol_upper


class AlpacaClient:
    """Wrapper for Alpaca Trading API."""

    def __init__(self):
        """Initialize Alpaca client with credentials."""
        self.trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.use_paper_trading,
        )

        # Data clients for getting prices (stocks and crypto use different clients)
        self.data_client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key, secret_key=settings.alpaca_secret_key
        )
        # CryptoHistoricalDataClient can work without API keys for free data,
        # but we use API keys for authenticated access (rate limits, etc.)
        try:
            self.crypto_data_client = CryptoHistoricalDataClient(
                api_key=settings.alpaca_api_key, secret_key=settings.alpaca_secret_key
            )
            logger.info("CryptoHistoricalDataClient initialized with API keys")
        except Exception as e:
            logger.warning(
                f"Failed to initialize CryptoHistoricalDataClient with API keys: {e}"
            )
            # Fallback: try without API keys (free tier)
            try:
                self.crypto_data_client = CryptoHistoricalDataClient()
                logger.info(
                    "CryptoHistoricalDataClient initialized without API keys (free tier)"
                )
            except Exception as e2:
                logger.error(f"Failed to initialize CryptoHistoricalDataClient: {e2}")
                raise

        logger.info(f"Alpaca client initialized (Paper: {settings.use_paper_trading})")

    def get_account(self) -> dict:
        """Get comprehensive account information.

        Note: Timeout is handled at the FastAPI endpoint level to prevent hanging requests.
        """
        try:
            account = self.trading_client.get_account()
            result = {
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "day_trading_buying_power": float(account.daytrading_buying_power)
                if hasattr(account, "daytrading_buying_power")
                else float(account.buying_power),
            }

            # Add all available account fields for comprehensive documentation
            # Only add fields if they exist AND are not None
            if (
                hasattr(account, "long_market_value")
                and account.long_market_value is not None
            ):
                result["long_market_value"] = float(account.long_market_value)
            if (
                hasattr(account, "short_market_value")
                and account.short_market_value is not None
            ):
                result["short_market_value"] = float(account.short_market_value)
            if (
                hasattr(account, "unsettled_funds")
                and account.unsettled_funds is not None
            ):
                result["unsettled_funds"] = float(account.unsettled_funds)
            if (
                hasattr(account, "pending_transfer_in")
                and account.pending_transfer_in is not None
            ):
                result["pending_transfer_in"] = float(account.pending_transfer_in)
            if (
                hasattr(account, "pending_transfer_out")
                and account.pending_transfer_out is not None
            ):
                result["pending_transfer_out"] = float(account.pending_transfer_out)
            if (
                hasattr(account, "non_marginable_buying_power")
                and account.non_marginable_buying_power is not None
            ):
                result["non_marginable_buying_power"] = float(
                    account.non_marginable_buying_power
                )
            if (
                hasattr(account, "regt_buying_power")
                and account.regt_buying_power is not None
            ):
                result["regt_buying_power"] = float(account.regt_buying_power)
            if (
                hasattr(account, "initial_margin")
                and account.initial_margin is not None
            ):
                result["initial_margin"] = float(account.initial_margin)
            if (
                hasattr(account, "maintenance_margin")
                and account.maintenance_margin is not None
            ):
                result["maintenance_margin"] = float(account.maintenance_margin)
            if hasattr(account, "last_equity") and account.last_equity is not None:
                result["last_equity"] = float(account.last_equity)
            if hasattr(account, "accrued_fees") and account.accrued_fees is not None:
                result["accrued_fees"] = float(account.accrued_fees)
            if (
                hasattr(account, "non_tradable_assets")
                and account.non_tradable_assets is not None
            ):
                result["non_tradable_assets"] = float(account.non_tradable_assets)
            if hasattr(account, "sma") and account.sma is not None:
                result["sma"] = float(account.sma)  # Special Memorandum Account

            return result
        except APIError as e:
            logger.error(f"Error getting account: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting account: {e}", exc_info=True)
            raise

    def get_positions(self) -> list[dict]:
        """Get current positions.

        Note: Crypto positions may return symbols in BTCUSD format (without slash),
        but we normalize them to BTC/USD format for consistency with trading API.
        """
        try:
            positions = self.trading_client.get_all_positions()
            result = []
            for pos in positions:
                symbol = pos.symbol
                # Normalize crypto symbols from position format (BTCUSD) to trading format (BTC/USD)
                if is_crypto_symbol(symbol) and "/" not in symbol:
                    normalized_symbol = normalize_crypto_symbol(symbol)
                    logger.debug(
                        f"Normalizing crypto position symbol: {symbol} -> {normalized_symbol}"
                    )
                    symbol = normalized_symbol

                result.append(
                    {
                        "symbol": symbol,
                        "quantity": float(pos.qty) if pos.qty else 0,
                        "avg_entry_price": float(pos.avg_entry_price),
                        "current_price": float(pos.current_price)
                        if pos.current_price
                        else None,
                        "market_value": float(pos.market_value),
                        "cost_basis": float(pos.cost_basis),
                        "unrealized_pl": float(pos.unrealized_pl),
                        "unrealized_plpc": float(pos.unrealized_plpc),
                    }
                )
            return result
        except APIError as e:
            logger.error(f"Error getting positions: {e}")
            raise

    def get_latest_price(self, symbol: str) -> float | None:
        """Get latest bar close price for a symbol (consistent with chart data).

        Supports both stocks and crypto by detecting symbol format and using appropriate API.
        Normalizes crypto symbols to trading format (BTC/USD) if needed.
        """
        try:
            # Normalize crypto symbol to trading format if needed (BTCUSD -> BTC/USD)
            if is_crypto_symbol(symbol) and "/" not in symbol.upper():
                symbol = normalize_crypto_symbol(symbol)
                logger.debug(f"Normalizing crypto symbol for price fetch: {symbol}")

            # Detect crypto vs stock and use appropriate API
            is_crypto = is_crypto_symbol(symbol)

            # Get the most recent bar to use its close price (consistent with chart)
            from datetime import timedelta

            if is_crypto:
                # Use crypto API for crypto symbols
                logger.info(f"Fetching crypto price for {symbol}")

                # Research finding: Alpaca crypto bars API works better with explicit date ranges
                # Use explicit start and end dates, and try multiple timeframes
                now = datetime.utcnow()

                # Strategy: Try multiple timeframes with explicit date ranges
                # 1. Try Minute bars (most recent, last hour)
                # 2. Try Hour bars (last 24 hours)
                # 3. Try Day bars (last 7 days with explicit dates)

                timeframes_to_try = [
                    (TimeFrame.Minute, timedelta(hours=1), "Minute"),
                    (TimeFrame.Hour, timedelta(hours=24), "Hour"),
                    (TimeFrame.Day, timedelta(days=7), "Day"),
                ]

                for timeframe, lookback, timeframe_name in timeframes_to_try:
                    try:
                        start_date = now - lookback
                        request = CryptoBarsRequest(
                            symbol_or_symbols=[symbol],
                            timeframe=timeframe,
                            start=start_date,
                            end=now,  # Explicit end date
                            limit=100,  # Get more bars, then take the latest
                        )
                        bars = self.crypto_data_client.get_crypto_bars(request)

                        # Debug: Log response structure
                        logger.debug(
                            f"Crypto {timeframe_name} bars response type: {type(bars)}"
                        )

                        # BarSet object has data attribute which is a dict
                        # Structure: bars.data['BTC/USD'] = [list of bars]
                        if hasattr(bars, "data") and bars.data:
                            bars_dict = bars.data
                            logger.debug(
                                f"Response data keys: {list(bars_dict.keys()) if hasattr(bars_dict, 'keys') else 'N/A'}"
                            )

                            # Check if we got data for this symbol
                            if (
                                symbol in bars_dict
                                and bars_dict[symbol]
                                and len(bars_dict[symbol]) > 0
                            ):
                                # Get the most recent bar (last in the list)
                                latest_bar = bars_dict[symbol][-1]
                                price = float(latest_bar.close)
                                logger.info(
                                    f"Got crypto price for {symbol} from {timeframe_name} bars: {price}"
                                )
                                return price
                            logger.debug(
                                f"No {timeframe_name} bars found for {symbol} in response data"
                            )
                        else:
                            logger.debug(
                                f"No data attribute in {timeframe_name} bars response for {symbol}"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Error fetching {timeframe_name} bars for {symbol}: {e}",
                            exc_info=True,
                        )
                        continue

                # Fallback: Try to get price from positions if we have one
                try:
                    logger.debug(
                        f"Trying to get crypto price from positions for {symbol}"
                    )
                    positions = self.get_positions()
                    for pos in positions:
                        if pos["symbol"].upper() == symbol.upper():
                            price = float(pos["current_price"])
                            logger.info(
                                f"Got crypto price for {symbol} from position: {price}"
                            )
                            return price
                except Exception as e:
                    logger.debug(
                        f"Could not get price from positions for {symbol}: {e}"
                    )

                logger.warning(
                    f"No crypto price data available for {symbol} after trying all methods"
                )
            else:
                # Use stock API for stock symbols
                # Prefer latest trade for real-time monitoring
                try:
                    trade_request = StockLatestTradeRequest(symbol_or_symbols=[symbol])
                    latest_trade = self.data_client.get_stock_latest_trade(trade_request)
                    if latest_trade.get(symbol):
                        price = float(latest_trade[symbol].price)
                        logger.debug(f"Got stock price for {symbol} from latest trade: {price}")
                        return price
                except Exception as e:
                    logger.debug(f"Could not get latest trade for {symbol}, falling back to bars: {e}")

                # Fallback to bars if trade not available
                request = StockBarsRequest(
                    symbol_or_symbols=[symbol],
                    timeframe=TimeFrame.Day,
                    start=datetime.utcnow() - timedelta(days=1),
                    limit=1,
                )
                bars = self.data_client.get_stock_bars(request)

                # Stock BarSet also has data attribute
                if hasattr(bars, "data") and bars.data and symbol in bars.data:
                    bars_dict = bars.data
                    if bars_dict[symbol] and len(bars_dict[symbol]) > 0:
                        # Return the close price of the most recent bar
                        price = float(bars_dict[symbol][-1].close)
                        logger.debug(f"Got stock price for {symbol} from bars: {price}")
                        return price

            # Fallback: try direct access for backward compatibility (shouldn't be needed)
            if hasattr(bars, "data") and bars.data:
                bars_dict = bars.data
                if (
                    symbol in bars_dict
                    and bars_dict[symbol]
                    and len(bars_dict[symbol]) > 0
                ):
                    price = float(bars_dict[symbol][-1].close)
                    logger.debug(f"Got price for {symbol} from data dict: {price}")
                    return price

            # Fallback to latest trade if no bars available (stocks only - crypto doesn't have latest trade endpoint)
            if not is_crypto:
                try:
                    trade_request = StockLatestTradeRequest(symbol_or_symbols=[symbol])
                    latest_trade = self.data_client.get_stock_latest_trade(
                        trade_request
                    )
                    if latest_trade.get(symbol):
                        price = float(latest_trade[symbol].price)
                        logger.debug(
                            f"Got stock price for {symbol} from latest trade: {price}"
                        )
                        return price
                except Exception as e:
                    logger.debug(f"Could not get latest trade for {symbol}: {e}")

            logger.warning(f"No price data available for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error getting latest price for {symbol}: {e}", exc_info=True)
            return None

    def get_latest_prices(self, symbols: list[str]) -> dict[str, float | None]:
        """Get latest bar close prices for multiple symbols (consistent with chart data).

        Supports both stocks and crypto by detecting symbol format and using appropriate API.
        Normalizes crypto symbols to trading format (BTC/USD) if needed.
        Batches crypto and stocks separately for efficiency.
        """
        try:
            # Normalize crypto symbols and create mapping
            symbol_mapping = {}  # Maps original -> normalized
            normalized_symbols = []
            for s in symbols:
                if is_crypto_symbol(s) and "/" not in s.upper():
                    normalized = normalize_crypto_symbol(s)
                    symbol_mapping[normalized] = s  # Map normalized -> original
                    normalized_symbols.append(normalized)
                else:
                    normalized_symbols.append(s)
                    symbol_mapping[s] = s

            # Separate crypto and stock symbols (using normalized symbols)
            crypto_symbols = [s for s in normalized_symbols if is_crypto_symbol(s)]
            stock_symbols = [s for s in normalized_symbols if not is_crypto_symbol(s)]

            result = {}
            from datetime import timedelta

            # Fetch crypto prices
            if crypto_symbols:
                try:
                    logger.debug(f"Fetching crypto prices for: {crypto_symbols}")
                    now = datetime.utcnow()

                    # Initialize all symbols to None
                    for normalized_symbol in crypto_symbols:
                        original_symbol = symbol_mapping.get(
                            normalized_symbol, normalized_symbol
                        )
                        result[original_symbol] = None

                    # Try multiple timeframes with explicit date ranges (same strategy as get_latest_price)
                    timeframes_to_try = [
                        (TimeFrame.Minute, timedelta(hours=1), "Minute"),
                        (TimeFrame.Hour, timedelta(hours=24), "Hour"),
                        (TimeFrame.Day, timedelta(days=7), "Day"),
                    ]

                    for timeframe, lookback, timeframe_name in timeframes_to_try:
                        # Check if we still need prices for any symbols
                        missing_symbols = [
                            s
                            for s in crypto_symbols
                            if result[symbol_mapping.get(s, s)] is None
                        ]
                        if not missing_symbols:
                            break  # All prices found

                        try:
                            start_date = now - lookback
                            crypto_request = CryptoBarsRequest(
                                symbol_or_symbols=missing_symbols,
                                timeframe=timeframe,
                                start=start_date,
                                end=now,  # Explicit end date
                                limit=100,  # Get more bars, then take the latest
                            )
                            crypto_bars = self.crypto_data_client.get_crypto_bars(
                                crypto_request
                            )
                            logger.debug(
                                f"Crypto {timeframe_name} bars response type: {type(crypto_bars)}"
                            )

                            # BarSet object has data attribute which is a dict
                            # Structure: crypto_bars.data['BTC/USD'] = [list of bars]
                            if hasattr(crypto_bars, "data") and crypto_bars.data:
                                bars_dict = crypto_bars.data

                                # Process results for each symbol
                                for normalized_symbol in missing_symbols:
                                    original_symbol = symbol_mapping.get(
                                        normalized_symbol, normalized_symbol
                                    )
                                    if (
                                        normalized_symbol in bars_dict
                                        and bars_dict[normalized_symbol]
                                        and len(bars_dict[normalized_symbol]) > 0
                                    ):
                                        result[original_symbol] = float(
                                            bars_dict[normalized_symbol][-1].close
                                        )
                                        logger.debug(
                                            f"Got crypto price for {normalized_symbol} (original: {original_symbol}) from {timeframe_name} bars: {result[original_symbol]}"
                                        )
                        except Exception as e:
                            logger.debug(
                                f"Error fetching {timeframe_name} bars for crypto symbols: {e}",
                                exc_info=True,
                            )
                            continue

                    # Fallback: Try to get prices from positions for any missing symbols
                    missing_symbols = [
                        s
                        for s in crypto_symbols
                        if result[symbol_mapping.get(s, s)] is None
                    ]
                    if missing_symbols:
                        try:
                            logger.debug(
                                f"Trying to get crypto prices from positions for: {missing_symbols}"
                            )
                            positions = self.get_positions()
                            for pos in positions:
                                pos_symbol = pos["symbol"].upper()
                                for normalized_symbol in missing_symbols:
                                    original_symbol = symbol_mapping.get(
                                        normalized_symbol, normalized_symbol
                                    )
                                    if pos_symbol == normalized_symbol.upper():
                                        result[original_symbol] = float(
                                            pos["current_price"]
                                        )
                                        logger.debug(
                                            f"Got crypto price for {normalized_symbol} from position: {result[original_symbol]}"
                                        )
                        except Exception as e:
                            logger.debug(f"Could not get prices from positions: {e}")

                    # Log warnings for symbols without prices
                    for normalized_symbol in crypto_symbols:
                        original_symbol = symbol_mapping.get(
                            normalized_symbol, normalized_symbol
                        )
                        if result[original_symbol] is None:
                            logger.warning(
                                f"No crypto price data available for {normalized_symbol} (original: {original_symbol})"
                            )

                except Exception as e:
                    logger.error(
                        f"Error getting crypto prices for {crypto_symbols}: {e}",
                        exc_info=True,
                    )
                    for normalized_symbol in crypto_symbols:
                        original_symbol = symbol_mapping.get(
                            normalized_symbol, normalized_symbol
                        )
                        result[original_symbol] = None

            # Fetch stock prices
            if stock_symbols:
                # Try getting latest trades first (real-time)
                try:
                    stock_trade_request = StockLatestTradeRequest(symbol_or_symbols=stock_symbols)
                    stock_trades = self.data_client.get_stock_latest_trade(stock_trade_request)
                    for normalized_symbol in stock_symbols:
                        original_symbol = symbol_mapping.get(normalized_symbol, normalized_symbol)
                        if stock_trades.get(normalized_symbol):
                            result[original_symbol] = float(stock_trades[normalized_symbol].price)
                            logger.debug(f"Got stock price for {normalized_symbol} from latest trade: {result[original_symbol]}")
                        else:
                            result[original_symbol] = None
                except Exception as e:
                    logger.warning(f"Error getting stock latest trades: {e}")
                    for normalized_symbol in stock_symbols:
                        original_symbol = symbol_mapping.get(normalized_symbol, normalized_symbol)
                        result[original_symbol] = None

                # For any missing prices, fallback to bars
                missing_stocks = [s for s in stock_symbols if result.get(symbol_mapping.get(s, s)) is None]
                
                if missing_stocks:
                    try:
                        stock_request = StockBarsRequest(
                            symbol_or_symbols=missing_stocks,
                            timeframe=TimeFrame.Day,
                            start=datetime.utcnow() - timedelta(days=1),
                            limit=1,
                        )
                        stock_bars = self.data_client.get_stock_bars(stock_request)

                        # Stock BarSet also has data attribute
                        if hasattr(stock_bars, "data") and stock_bars.data:
                            bars_dict = stock_bars.data
                            for normalized_symbol in missing_stocks:
                                original_symbol = symbol_mapping.get(normalized_symbol, normalized_symbol)
                                if (
                                    normalized_symbol in bars_dict
                                    and bars_dict[normalized_symbol]
                                    and len(bars_dict[normalized_symbol]) > 0
                                ):
                                    result[original_symbol] = float(
                                        bars_dict[normalized_symbol][-1].close
                                    )
                                    logger.debug(f"Got stock price for {normalized_symbol} from bars (fallback): {result[original_symbol]}")
                    except Exception as e:
                        logger.error(f"Error getting stock bars fallback: {e}")

            return result
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return dict.fromkeys(symbols)

    def place_limit_order(
        self,
        symbol: str,
        quantity: float,  # Changed from int to float to support fractional shares
        limit_price: float,
        time_in_force: str = "DAY",
    ) -> dict | None:
        """Place a limit buy order. Supports fractional quantities.

        Automatically handles crypto vs stock differences:
        - Crypto only supports GTC and IOC (not DAY)
        - Auto-converts DAY to GTC for crypto symbols
        """
        try:
            # Round price to 2 decimal places to avoid precision issues
            limit_price = round(limit_price, 2)

            # Detect crypto and handle time_in_force appropriately
            is_crypto = is_crypto_symbol(symbol)
            if is_crypto:
                # Crypto only supports GTC and IOC - convert DAY to GTC
                if time_in_force.upper() == "DAY":
                    logger.info(
                        f"Crypto symbol {symbol} - converting DAY to GTC (crypto doesn't support DAY)"
                    )
                    time_in_force = "GTC"
                elif time_in_force.upper() not in ["GTC", "IOC"]:
                    logger.warning(
                        f"Crypto symbol {symbol} - invalid time_in_force {time_in_force}, defaulting to GTC"
                    )
                    time_in_force = "GTC"

            # Map time_in_force string to enum
            tif_map = {
                "DAY": TimeInForce.DAY,
                "GTC": TimeInForce.GTC,
                "IOC": TimeInForce.IOC,
                "FOK": TimeInForce.FOK,
            }
            tif_enum = tif_map.get(time_in_force.upper(), TimeInForce.GTC)

            order_request = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,  # Alpaca SDK supports float for fractional shares
                side=OrderSide.BUY,
                limit_price=limit_price,
                time_in_force=tif_enum,
            )

            order = self.trading_client.submit_order(order_data=order_request)

            return {
                "id": str(order.id),
                "symbol": order.symbol,
                "quantity": float(order.qty),
                "limit_price": float(order.limit_price)
                if order.limit_price
                else limit_price,
                "status": order.status.value
                if hasattr(order.status, "value")
                else str(order.status),
                "side": order.side.value
                if hasattr(order.side, "value")
                else str(order.side),
                "time_in_force": order.time_in_force.value
                if hasattr(order.time_in_force, "value")
                else str(order.time_in_force),
                "submitted_at": order.submitted_at.isoformat()
                if order.submitted_at
                else None,
            }
        except APIError as e:
            logger.error(f"Error placing limit order for {symbol}: {e}")
            raise

    def get_order(self, order_id: str) -> dict | None:
        """Get order details by ID."""
        try:
            order = self.trading_client.get_order_by_id(order_id)
            return {
                "id": str(order.id),
                "symbol": order.symbol,
                "quantity": float(order.qty),
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else None,
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "status": order.status.value
                if hasattr(order.status, "value")
                else str(order.status),
                "side": order.side.value
                if hasattr(order.side, "value")
                else str(order.side),
                "time_in_force": order.time_in_force.value
                if hasattr(order.time_in_force, "value")
                else str(order.time_in_force),
                "submitted_at": order.submitted_at.isoformat()
                if order.submitted_at
                else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            }
        except APIError as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except APIError as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_activities(self, activity_types: list[str] | None = None) -> list[dict]:
        """Get account activities."""
        try:
            # Note: Alpaca-py doesn't have a direct get_activities method
            # We'll need to use account activities endpoint or track via orders
            # For now, return empty list - we'll track activities in our own database
            return []
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            return []

    def get_historical_bars(
        self, symbol: str, days: int = 30, timeframe: str = "Day"
    ) -> list[dict]:
        """Get historical bars for a symbol.

        Uses Alpaca's data API to fetch real historical bar data.
        Supports both stocks and crypto by detecting symbol format.
        Normalizes crypto symbols to trading format (BTC/USD) if needed.
        BarSet is accessed like a dictionary: bars[symbol]
        """
        try:
            # Normalize crypto symbol to trading format if needed (BTCUSD -> BTC/USD)
            if is_crypto_symbol(symbol) and "/" not in symbol.upper():
                symbol = normalize_crypto_symbol(symbol)
                logger.debug(f"Normalizing crypto symbol for historical bars: {symbol}")

            # Map timeframe string to TimeFrame enum
            timeframe_map = {
                "Minute": TimeFrame.Minute,
                "Hour": TimeFrame.Hour,
                "Day": TimeFrame.Day,
                "Week": TimeFrame.Week,
                "Month": TimeFrame.Month,
            }
            tf = timeframe_map.get(timeframe, TimeFrame.Day)

            # Calculate start date - Alpaca requires start date to be before end date
            # End defaults to now if not specified
            start_date = datetime.utcnow() - timedelta(days=days)

            # Detect crypto vs stock and use appropriate API
            is_crypto = is_crypto_symbol(symbol)

            if is_crypto:
                # Use crypto API for crypto symbols
                logger.info(
                    f"Fetching crypto historical bars for {symbol} (timeframe: {timeframe}, days: {days}, start: {start_date})"
                )
                request = CryptoBarsRequest(
                    symbol_or_symbols=[symbol], timeframe=tf, start=start_date
                )
                # Get bars from Alpaca - returns BarSet object
                bars = self.crypto_data_client.get_crypto_bars(request)

                # BarSet object has data attribute which is a dict
                # Structure: bars.data['BTC/USD'] = [list of bars]
                if hasattr(bars, "data") and bars.data:
                    bars_dict = bars.data
                    logger.info(
                        f"Crypto bars response type: {type(bars)}, data keys: {list(bars_dict.keys()) if hasattr(bars_dict, 'keys') else 'N/A'}"
                    )
                    logger.info(
                        f"Crypto bars for {symbol}: {len(bars_dict.get(symbol, [])) if symbol in bars_dict else 0} bars found"
                    )

                    # Check if symbol is in bars
                    if symbol not in bars_dict:
                        logger.warning(
                            f"Symbol {symbol} not found in crypto bars response. Available keys: {list(bars_dict.keys()) if hasattr(bars_dict, 'keys') else 'N/A'}"
                        )
                        return []

                    # Use bars_dict for crypto
                    symbol_bars = bars_dict[symbol]
                else:
                    logger.warning(
                        f"No data attribute in crypto bars response for {symbol}"
                    )
                    return []
            else:
                # Use stock API for stock symbols
                request = StockBarsRequest(
                    symbol_or_symbols=[symbol], timeframe=tf, start=start_date
                )
                # Get bars from Alpaca - returns BarSet object
                bars = self.data_client.get_stock_bars(request)

                # Stock BarSet also has data attribute
                if hasattr(bars, "data") and bars.data:
                    bars_dict = bars.data
                    if symbol not in bars_dict:
                        logger.warning(
                            f"Symbol {symbol} not found in stock bars response. Available keys: {list(bars_dict.keys()) if hasattr(bars_dict, 'keys') else 'N/A'}"
                        )
                        return []
                    symbol_bars = bars_dict[symbol]
                else:
                    # Fallback: try direct access (for backward compatibility)
                    try:
                        symbol_bars = bars[symbol]
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Symbol {symbol} not found in BarSet: {e}")
                        return []

            bar_count = len(symbol_bars)
            logger.info(
                f"Fetched {bar_count} bars for {symbol} (timeframe: {timeframe}, days: {days})"
            )

            # Convert Bar objects to dictionaries
            result = []
            for bar in symbol_bars:
                result.append(
                    {
                        "timestamp": bar.timestamp.isoformat()
                        if bar.timestamp
                        else None,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume) if bar.volume else 0,
                    }
                )

            if result:
                logger.info(
                    f"Historical bars for {symbol}: first={result[0]['close']:.2f}, last={result[-1]['close']:.2f}, count={len(result)}"
                )

            return result

        except KeyError as e:
            logger.error(f"Symbol {symbol} not found in BarSet: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting historical bars for {symbol}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    def get_all_orders(self, status: str | None = None, limit: int = 100) -> list[dict]:
        """Get all orders with optional status filter.

        Uses GetOrdersRequest with QueryOrderStatus for efficient filtering.
        For specific statuses like 'filled', filters manually after fetching.

        Args:
            status: Filter by status. Supports:
                - 'open' or 'OPEN' -> QueryOrderStatus.OPEN
                - 'closed' or 'CLOSED' -> QueryOrderStatus.CLOSED
                - 'all' or 'ALL' -> QueryOrderStatus.ALL
                - 'filled', 'new', 'canceled', etc. -> Filter manually from CLOSED/ALL
            limit: Maximum number of orders to return
        """
        try:
            # Map status string to QueryOrderStatus enum
            query_status = QueryOrderStatus.ALL  # Default

            if status:
                status_upper = status.upper()
                if status_upper in ["OPEN", "NEW", "PENDING"]:
                    query_status = QueryOrderStatus.OPEN
                elif status_upper == "CLOSED":
                    query_status = QueryOrderStatus.CLOSED
                elif status_upper in [
                    "FILLED",
                    "CANCELED",
                    "EXPIRED",
                    "REJECTED",
                ]:
                    # For specific statuses like 'filled', query ALL to ensure we get them
                    # (CLOSED might have many expired orders before filled ones)
                    query_status = QueryOrderStatus.ALL
                # else: use ALL for other statuses

            # Create request with proper filter
            request_params = GetOrdersRequest(status=query_status, limit=limit)

            # Get orders from Alpaca using proper SDK method
            orders = self.trading_client.get_orders(filter=request_params)

            # Convert to dict format
            orders_list = [
                {
                    "id": str(order.id),
                    "symbol": order.symbol,
                    "quantity": float(order.qty) if order.qty else 0,
                    "filled_qty": float(order.filled_qty)
                    if order.filled_qty
                    else 0,
                    "filled_avg_price": float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else None,
                    "limit_price": float(order.limit_price)
                    if order.limit_price
                    else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "status": order.status.value
                    if hasattr(order.status, "value")
                    else str(order.status),
                    "side": order.side.value
                    if hasattr(order.side, "value")
                    else str(order.side),
                    "order_type": order.order_type.value
                    if hasattr(order.order_type, "value")
                    else str(order.order_type),
                    "time_in_force": order.time_in_force.value
                    if hasattr(order.time_in_force, "value")
                    else str(order.time_in_force),
                    "submitted_at": order.submitted_at.isoformat()
                    if order.submitted_at
                    else None,
                    "filled_at": order.filled_at.isoformat()
                    if order.filled_at
                    else None,
                    "canceled_at": order.canceled_at.isoformat()
                    if order.canceled_at
                    else None,
                }
                for order in orders
            ]

            # Filter by specific status if needed (e.g., 'filled', 'new', 'canceled')
            if status:
                status_upper = status.upper()
                # Only filter if it's a specific status that requires manual filtering
                if status_upper not in ["OPEN", "CLOSED", "ALL"]:
                    orders_list = [
                        o
                        for o in orders_list
                        if o.get("status", "").upper() == status_upper
                    ]

            return orders_list
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    def get_asset_info(self, symbol: str) -> dict | None:
        """Get asset information including company name."""
        try:
            asset = self.trading_client.get_asset(symbol)
            return {
                "symbol": asset.symbol,
                "name": asset.name if hasattr(asset, "name") else symbol,
                "exchange": asset.exchange.value
                if hasattr(asset.exchange, "value")
                else str(asset.exchange),
                "class": asset.asset_class.value
                if hasattr(asset.asset_class, "value")
                else str(asset.asset_class),
                "tradable": asset.tradable if hasattr(asset, "tradable") else True,
                "fractionable": asset.fractionable
                if hasattr(asset, "fractionable")
                else False,
            }
        except Exception as e:
            logger.error(f"Error getting asset info for {symbol}: {e}")
            return None

    def get_all_assets(self) -> list[dict]:
        """Get all tradable assets (stocks and crypto) with fractional trading status.

        Uses Alpaca REST API directly since the SDK doesn't have a list_assets method.
        """
        try:
            # Use REST API to get all assets
            base_url = settings.alpaca_base_url
            url = f"{base_url}/v2/assets"

            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }

            params = {
                "status": "active",
            }

            # Fetch assets - Alpaca API returns a list directly
            response = requests.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            # Alpaca API returns a list directly, not a dict
            if isinstance(data, list):
                all_assets = data
            elif isinstance(data, dict):
                # Handle paginated response if needed
                all_assets = data.get("assets", [])
            else:
                all_assets = []

            result = []
            for asset in all_assets:
                # Only include tradable assets
                if asset.get("tradable", False):
                    asset_dict = {
                        "symbol": asset.get("symbol", "").upper(),
                        "name": asset.get("name", asset.get("symbol", "")),
                        "exchange": asset.get("exchange", ""),
                        "class": asset.get("class", ""),
                        "tradable": True,
                        "fractionable": asset.get("fractionable", False),
                    }
                    result.append(asset_dict)

            logger.info(f"Fetched {len(result)} tradable assets from Alpaca")
            return result
        except Exception as e:
            logger.error(f"Error getting all assets: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    def get_market_clock(self) -> dict:
        """Get market clock information."""
        try:
            clock = self.trading_client.get_clock()
            return {
                "is_open": clock.is_open,
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat()
                if clock.next_close
                else None,
            }
        except Exception as e:
            logger.error(f"Error getting market clock: {e}")
            # Default to closed if we can't get clock
            return {
                "is_open": False,
                "timestamp": None,
                "next_open": None,
                "next_close": None,
            }

    def get_portfolio_history(
        self,
        period: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        intraday_reporting: str = "market_hours",
        pnl_reset: str = "per_day",
    ) -> dict:
        """Get portfolio history (equity and P/L over time) from Alpaca.
        
        Uses Alpaca REST API directly since the SDK doesn't have this method.
        
        Args:
            period: Duration in format like "1D", "1W", "1M", "1A" (day/week/month/year)
            timeframe: Resolution - "1Min", "5Min", "15Min", "1H", or "1D"
            start: Start timestamp in RFC3339 format (e.g., "2024-01-01T00:00:00Z")
            end: End timestamp in RFC3339 format (defaults to current time)
            intraday_reporting: "market_hours", "extended_hours", or "continuous"
            pnl_reset: "per_day" (default) or "no_reset" (for crypto)
            
        Returns:
            Dict with portfolio history data:
            {
                "timestamp": [int, ...],  # UNIX epoch timestamps
                "equity": [float, ...],    # Equity values
                "profit_loss": [float, ...],  # P/L in dollars
                "profit_loss_pct": [float, ...],  # P/L in percentage
                "base_value": float,  # Basis for P/L calculation
                "base_value_asof": str | None,  # Timestamp when base_value was set
                "timeframe": str,  # Resolution used
            }
            
        Note:
            - Only two of start, end, and period can be specified
            - For intraday timeframes (<1D), period must be <= 30 days
            - For periods > 30 days, timeframe must be "1D"
        """
        try:
            base_url = settings.alpaca_base_url
            url = f"{base_url}/v2/account/portfolio/history"
            
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }
            
            params = {}
            if period:
                params["period"] = period
            if timeframe:
                params["timeframe"] = timeframe
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            if intraday_reporting:
                params["intraday_reporting"] = intraday_reporting
            if pnl_reset:
                params["pnl_reset"] = pnl_reset
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Alpaca returns arrays for timestamp, equity, profit_loss, profit_loss_pct
            # and single values for base_value, base_value_asof, timeframe
            # Handle None values from API - Alpaca may return None for base_value or profit_loss_pct
            base_value = data.get("base_value")
            base_value = base_value if base_value is not None else 0.0
            
            result = {
                "timestamp": data.get("timestamp", []),
                "equity": data.get("equity", []),
                "profit_loss": data.get("profit_loss", []),
                "profit_loss_pct": data.get("profit_loss_pct", []),
                "base_value": base_value,
                "base_value_asof": data.get("base_value_asof"),
                "timeframe": data.get("timeframe", "1D"),
            }
            
            logger.debug(
                f"Fetched portfolio history: {len(result['timestamp'])} data points, "
                f"timeframe={result['timeframe']}, base_value={result['base_value']}"
            )
            return result
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching portfolio history: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}", exc_info=True)
            raise

    def get_corporate_actions(
        self,
        symbols: list[str] | None = None,
        action_types: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Get corporate actions announcements from Alpaca.

        Args:
            symbols: List of symbols to filter by (optional)
            action_types: List of action types to filter by (e.g., ['SPLIT', 'MERGER', 'DIVIDEND'])
            date_from: Start date for filtering (optional)
            date_to: End date for filtering (optional)

        Returns:
            List of corporate action dictionaries
        """
        try:
            # Use Alpaca Data API for corporate actions
            # The endpoint is: https://data.alpaca.markets/v1/corporate-actions
            # Note: The /announcements endpoint was deprecated in favor of this endpoint
            base_url = "https://data.alpaca.markets"
            url = f"{base_url}/v1/corporate-actions"

            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }

            params = {}

            # Add symbol filter if provided
            # Alpaca API accepts comma-separated symbols or can be passed as array
            if symbols:
                params["symbols"] = ",".join([s.upper() for s in symbols])

            # Add action type filter if provided
            # Valid types: forward_split, reverse_split, cash_merger, stock_merger,
            # cash_dividend, stock_dividend, spinoff, etc.
            # Note: API uses 'types' parameter (not 'ca_types')
            if action_types:
                # Convert to format that Alpaca expects
                # API expects singular forms and specific spellings (e.g. spin_off)
                type_map = {
                    "forward_split": "forward_split",
                    "reverse_split": "reverse_split",
                    "cash_merger": "cash_merger",
                    "stock_merger": "stock_merger",
                    "cash_dividend": "cash_dividend",
                    "stock_dividend": "stock_dividend",
                    "spinoff": "spin_off",
                }
                mapped_types = [
                    type_map.get(at.lower(), at.lower()) for at in action_types
                ]
                params["types"] = ",".join(mapped_types)

            # Note: Date filters may not be supported by this endpoint
            # The API response structure suggests it returns all available actions
            # We'll filter by date in our code if needed

            logger.debug(f"Fetching corporate actions from {url} with params: {params}")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Alpaca API returns a dict with structure:
            # {
            #   "corporate_actions": {
            #     "forward_splits": [...],
            #     "reverse_splits": [...],
            #     "cash_mergers": [...],
            #     ...
            #   },
            #   "next_page_token": "..."
            # }
            if isinstance(data, dict):
                corporate_actions = data.get("corporate_actions", {})

                # Flatten the nested structure into a single list
                # Each action type (e.g., "forward_splits") contains a list of actions
                flattened_actions = []
                if isinstance(corporate_actions, dict):
                    for action_type, actions_list in corporate_actions.items():
                        if isinstance(actions_list, list):
                            for action in actions_list:
                                # Add the action type to each action for easier filtering
                                if isinstance(action, dict):
                                    action["_action_type"] = action_type
                                flattened_actions.append(action)
                        elif isinstance(actions_list, dict):
                            # Some action types might be single dicts
                            actions_list["_action_type"] = action_type
                            flattened_actions.append(actions_list)

                logger.debug(
                    f"Received {len(flattened_actions)} corporate action(s) from API"
                )
                return flattened_actions
            if isinstance(data, list):
                # Fallback: if API returns a list directly
                logger.debug(f"Received {len(data)} corporate action(s) as list")
                return data
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching corporate actions: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting corporate actions: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []
