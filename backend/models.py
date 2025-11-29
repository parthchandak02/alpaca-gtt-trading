"""Database models for GTT orders, activities, and positions."""

import enum
from datetime import datetime

from database import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship


class OrderStatus(str, enum.Enum):
    """Order status enumeration - matches Alpaca API statuses.

    See: https://docs.alpaca.markets/docs/trading/orders/
    """

    # Active/Open statuses (can be modified/cancelled)
    PENDING = "PENDING"  # Our internal status for orders not yet submitted to Alpaca
    NEW = "new"  # Order received by Alpaca and routed to exchanges
    ACCEPTED = (
        "accepted"  # Order received but not yet routed (rare, outside trading hours)
    )
    PENDING_NEW = "pending_new"  # Order routed but not yet accepted (rare)
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Order partially filled
    PENDING_CANCEL = "pending_cancel"  # Order waiting to be cancelled
    PENDING_REPLACE = "pending_replace"  # Order waiting to be replaced

    # Terminal/Closed statuses (no further updates)
    FILLED = "FILLED"  # Order completely filled
    CANCELLED = "CANCELLED"  # Order cancelled
    EXPIRED = "EXPIRED"  # Order expired (time-in-force)
    REJECTED = "rejected"  # Order rejected by exchange (rare)
    DONE_FOR_DAY = "done_for_day"  # Order done for the day
    REPLACED = "replaced"  # Order replaced by another order
    FAILED = "FAILED"  # Internal status for failed orders

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """Check if a status is terminal (no further updates expected)."""
        terminal_statuses = {
            cls.FILLED.value,
            cls.CANCELLED.value,
            cls.EXPIRED.value,
            cls.REJECTED.value,
            cls.DONE_FOR_DAY.value,
            cls.REPLACED.value,
            cls.FAILED.value,
        }
        return status in terminal_statuses

    @classmethod
    def is_active(cls, status: str) -> bool:
        """Check if a status represents an active order (can be modified/cancelled)."""
        return not cls.is_terminal(status)

    @classmethod
    def locks_buying_power(cls, status: str) -> bool:
        """Check if an Alpaca order status locks buying power.
        
        NOTE: This only applies to orders SUBMITTED TO ALPACA (have alpaca_order_id).
        Our internal PENDING status (no alpaca_order_id) does NOT lock buying power
        because the order hasn't been submitted yet.
        
        According to Alpaca API docs, orders that lock buying power are those that:
        - Are submitted but not yet filled (NEW, ACCEPTED, PENDING_NEW)
        - Are partially filled (PARTIALLY_FILLED - remaining quantity locks buying power)
        - Are waiting to be cancelled/replaced (PENDING_CANCEL, PENDING_REPLACE - still locks until cancelled)
        - Any Alpaca "pending" status (submitted to Alpaca)
        
        Orders that DO NOT lock buying power:
        - Our internal PENDING (no alpaca_order_id - not yet triggered/submitted)
        - FILLED (executed, money deducted from account)
        - CANCELLED (cancelled, buying power released)
        - EXPIRED (expired, buying power released)
        - REJECTED (rejected, buying power released)
        - DONE_FOR_DAY, REPLACED, FAILED (terminal states)
        
        Args:
            status: Alpaca order status string (case-insensitive)
            
        Returns:
            True if the status locks buying power, False otherwise
        """
        status_upper = status.upper() if status else ""
        
        # Statuses that lock buying power (only for orders submitted to Alpaca)
        # Note: PENDING is NOT included here because our internal PENDING (no alpaca_order_id)
        # does NOT lock buying power. Only Alpaca's pending statuses do.
        locking_statuses = {
            cls.NEW.value,
            cls.ACCEPTED.value,
            cls.PENDING_NEW.value,
            cls.PARTIALLY_FILLED.value,
            cls.PENDING_CANCEL.value,
            cls.PENDING_REPLACE.value,
            # Also handle lowercase variants from Alpaca API
            "new",
            "accepted",
            "pending_new",
            "pending_cancel",
            "pending_replace",
            "partially_filled",
        }
        
        return status_upper in locking_statuses


class ActivityType(str, enum.Enum):
    """Activity type enumeration."""

    GTT_TRIGGER = "GTT_TRIGGER"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FAILED = "ORDER_FAILED"
    CORPORATE_ACTION_EXPIRED = "CORPORATE_ACTION_EXPIRED"


class GTTOrder(Base):
    """GTT (Good-Till-Triggered) order model."""

    __tablename__ = "gtt_orders"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    initial_trigger_price = Column(Float, nullable=False)
    initial_quantity = Column(Float, nullable=False)  # Supports fractional trading
    increment_qty_multiplier = Column(Float, nullable=False)  # e.g., 1.2, 1.5, 2.0
    decrement_price_multiplier = Column(
        Float, nullable=False
    )  # e.g., 0.9 = 10% decrease
    iterations = Column(Integer, nullable=False)  # Number of orders to create

    # Status tracking
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    filled_count = Column(Integer, default=0)  # How many orders have been filled
    total_count = Column(Integer, nullable=False)  # Total orders in ladder

    # Calculated fields
    total_value = Column(Float, default=0.0)  # Total value of all orders
    locked_buying_power = Column(Float, default=0.0)  # Buying power locked

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order_details = relationship(
        "GTTOrderDetail", back_populates="gtt_order", cascade="all, delete-orphan"
    )
    activities = relationship("Activity", back_populates="gtt_order")


class GTTOrderDetail(Base):
    """Individual order details within a GTT order ladder."""

    __tablename__ = "gtt_order_details"

    id = Column(Integer, primary_key=True, index=True)
    gtt_order_id = Column(Integer, ForeignKey("gtt_orders.id"), nullable=False)
    order_index = Column(Integer, nullable=False)  # Position in ladder (0, 1, 2, ...)

    # Order parameters
    trigger_price = Column(Float, nullable=False)
    quantity = Column(
        Integer, nullable=False
    )  # Display quantity (rounded for non-fractionable assets)
    fractional_quantity = Column(
        Float, nullable=True
    )  # Original fractional quantity for placing orders
    limit_price = Column(Float, nullable=False)  # Price for limit order
    amount = Column(Float, nullable=False)  # quantity * limit_price

    # Alpaca order tracking (reference only - actual data fetched from Alpaca API via AlpacaOrderCache)
    alpaca_order_id = Column(
        String, nullable=True, index=True
    )  # Alpaca's order ID (reference to AlpacaOrderCache)
    is_manually_linked = Column(
        Boolean, default=False, index=True
    )  # True if manually linked to executed order
    time_in_force = Column(String, default="DAY")  # DAY, GTC, etc.

    # GTT-specific timestamps (when order detail was created/updated in our system)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    gtt_order = relationship("GTTOrder", back_populates="order_details")


class Activity(Base):
    """Activity log for GTT triggers and order executions."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    gtt_order_id = Column(Integer, ForeignKey("gtt_orders.id"), nullable=True)

    # Activity details
    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Order details (if applicable)
    quantity = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)
    side = Column(String, nullable=True)  # BUY, SELL
    amount = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    gtt_order = relationship("GTTOrder", back_populates="activities")


class Position(Base):
    """Cached position data from Alpaca."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    cost_basis = Column(Float, nullable=False)
    unrealized_pl = Column(Float, nullable=True)
    unrealized_plpc = Column(Float, nullable=True)  # Unrealized P&L percentage

    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceCache(Base):
    """Cached price data for symbols."""

    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class AlpacaOrderCache(Base):
    """Cached Alpaca order data (status, timestamps) - source of truth is Alpaca API."""

    __tablename__ = "alpaca_order_cache"

    id = Column(Integer, primary_key=True, index=True)
    alpaca_order_id = Column(
        String, unique=True, nullable=False, index=True
    )  # Alpaca's order ID

    # Alpaca order data (cached, not duplicated)
    status = Column(String, nullable=True)  # FILLED, PENDING, CANCELLED, etc.
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    filled_qty = Column(
        Float, nullable=True
    )  # Actual filled quantity (may differ from requested)
    filled_avg_price = Column(Float, nullable=True)  # Average fill price

    # Cache metadata
    cached_at = Column(
        DateTime, default=datetime.utcnow, index=True
    )  # When we cached this
    last_fetched_at = Column(
        DateTime, default=datetime.utcnow, index=True
    )  # Last time we fetched from Alpaca
