"""Centralized service for PriceCache operations.

This module provides a single source of truth for all price cache operations,
eliminating code duplication across the codebase.
"""

import logging
from datetime import datetime

from database import SessionLocal
from models import PriceCache

logger = logging.getLogger(__name__)


class PriceCacheService:
    """Service for managing price cache operations."""

    @staticmethod
    def update_price(
        symbol: str, price: float, timestamp: datetime | None = None
    ) -> bool:
        """Update price cache for a symbol.

        Args:
            symbol: Symbol to update (will be uppercased)
            price: Price value
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        if not symbol or price is None:
            return False

        symbol_upper = symbol.upper()
        if timestamp is None:
            timestamp = datetime.utcnow()

        try:
            db = SessionLocal()
            try:
                cache = (
                    db.query(PriceCache)
                    .filter(PriceCache.symbol == symbol_upper)
                    .first()
                )
                if cache:
                    cache.price = price
                    cache.timestamp = timestamp
                else:
                    cache = PriceCache(
                        symbol=symbol_upper, price=price, timestamp=timestamp
                    )
                    db.add(cache)

                db.commit()
                logger.debug(f"Updated price cache for {symbol_upper}: {price}")
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(
                f"Error updating price cache for {symbol_upper}: {e}", exc_info=True
            )
            return False

    @staticmethod
    def update_prices(
        prices: dict[str, float], timestamp: datetime | None = None
    ) -> int:
        """Update price cache for multiple symbols.

        Args:
            prices: Dict mapping symbol -> price
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Number of successfully updated prices
        """
        if not prices:
            return 0

        if timestamp is None:
            timestamp = datetime.utcnow()

        updated_count = 0
        try:
            db = SessionLocal()
            try:
                for symbol, price in prices.items():
                    if price is None:
                        continue

                    symbol_upper = symbol.upper()
                    cache = (
                        db.query(PriceCache)
                        .filter(PriceCache.symbol == symbol_upper)
                        .first()
                    )
                    if cache:
                        cache.price = price
                        cache.timestamp = timestamp
                    else:
                        cache = PriceCache(
                            symbol=symbol_upper, price=price, timestamp=timestamp
                        )
                        db.add(cache)

                    updated_count += 1

                db.commit()
                logger.debug(f"Updated price cache for {updated_count} symbols")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating price cache: {e}", exc_info=True)

        return updated_count

    @staticmethod
    def get_price(symbol: str) -> float | None:
        """Get cached price for a symbol.

        Args:
            symbol: Symbol to lookup (will be uppercased)

        Returns:
            Cached price or None if not found
        """
        if not symbol:
            return None

        symbol_upper = symbol.upper()
        try:
            db = SessionLocal()
            try:
                cache = (
                    db.query(PriceCache)
                    .filter(PriceCache.symbol == symbol_upper)
                    .first()
                )
                return cache.price if cache else None
            finally:
                db.close()
        except Exception as e:
            logger.error(
                f"Error getting price cache for {symbol_upper}: {e}", exc_info=True
            )
            return None

    @staticmethod
    def get_prices(symbols: list[str]) -> dict[str, float | None]:
        """Get cached prices for multiple symbols.

        Args:
            symbols: List of symbols to lookup

        Returns:
            Dict mapping symbol -> price (None if not found)
        """
        if not symbols:
            return {}

        result = {}
        try:
            db = SessionLocal()
            try:
                for symbol in symbols:
                    symbol_upper = symbol.upper()
                    cache = (
                        db.query(PriceCache)
                        .filter(PriceCache.symbol == symbol_upper)
                        .first()
                    )
                    result[symbol] = cache.price if cache else None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting price cache: {e}", exc_info=True)

        return result

    @staticmethod
    def get_price_with_timestamp(symbol: str) -> dict | None:
        """Get cached price with timestamp for a symbol.

        Args:
            symbol: Symbol to lookup

        Returns:
            Dict with 'price' and 'timestamp' keys, or None if not found
        """
        if not symbol:
            return None

        symbol_upper = symbol.upper()
        try:
            db = SessionLocal()
            try:
                cache = (
                    db.query(PriceCache)
                    .filter(PriceCache.symbol == symbol_upper)
                    .first()
                )
                if cache:
                    return {"price": cache.price, "timestamp": cache.timestamp}
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(
                f"Error getting price cache with timestamp for {symbol_upper}: {e}",
                exc_info=True,
            )
            return None
