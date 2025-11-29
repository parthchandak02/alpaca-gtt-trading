"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Annotated, Any

from models import ActivityType, OrderStatus
from pydantic import BaseModel, Field, validator, field_validator, model_validator, BeforeValidator


# GTT Order Schemas
class GTTOrderCreate(BaseModel):
    """Schema for creating a new GTT order."""

    symbol: str = Field(..., description="Stock ticker symbol")
    initial_trigger_price: float = Field(..., gt=0, description="Initial trigger price")
    initial_quantity: float = Field(
        ..., gt=0, description="Initial quantity (supports fractional trading)"
    )
    increment_qty_multiplier: float = Field(
        ..., gt=0, description="Quantity multiplier (e.g., 1.2, 1.5, 2.0)"
    )
    decrement_price_multiplier: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Price decrement multiplier (e.g., 0.9 = 10% decrease)",
    )
    iterations: int = Field(
        ..., gt=0, le=20, description="Number of orders to create in ladder"
    )
    time_in_force: str = Field(default="DAY", description="Time in force: DAY or GTC")

    @validator("symbol")
    def symbol_uppercase(cls, v):
        return v.upper().strip()


class GTTOrderDetailResponse(BaseModel):
    """Schema for GTT order detail response with Alpaca data fetched from cache."""

    id: int
    gtt_order_id: int
    order_index: int
    trigger_price: float
    quantity: float  # Changed to float to support fractional quantities
    fractional_quantity: float | None = (
        None  # Original fractional quantity for placing orders
    )
    limit_price: float
    amount: float
    alpaca_order_id: str | None
    is_manually_linked: bool
    time_in_force: str
    # Alpaca order data (fetched from cache, not stored in GTTOrderDetail)
    status: str | None = None  # From Alpaca cache
    submitted_at: datetime | None = None  # From Alpaca cache
    filled_at: datetime | None = None  # From Alpaca cache
    expired_at: datetime | None = None  # From Alpaca cache
    filled_avg_price: float | None = None  # From Alpaca cache - average fill price

    class Config:
        from_attributes = True


class GTTOrderDetailUpdate(BaseModel):
    """Schema for updating an order detail."""

    trigger_price: float | None = None
    quantity: int | None = None
    limit_price: float | None = None
    time_in_force: str | None = None


class GTTOrderDetailLink(BaseModel):
    """Schema for linking an order detail to an Alpaca order."""

    alpaca_order_id: str


class GTTOrderResponse(BaseModel):
    """Schema for GTT order response."""

    id: int
    symbol: str
    initial_trigger_price: float
    initial_quantity: float  # Can be fractional for fractionable assets
    increment_qty_multiplier: float
    decrement_price_multiplier: float
    iterations: int
    status: OrderStatus
    filled_count: int
    total_count: int
    total_value: float
    locked_buying_power: float
    created_at: datetime
    updated_at: datetime
    order_details: list[GTTOrderDetailResponse]

    class Config:
        from_attributes = True


# Activity Schemas
class ActivityResponse(BaseModel):
    """Schema for activity response."""

    id: int
    gtt_order_id: int | None
    activity_type: ActivityType
    symbol: str
    description: str
    quantity: float | None
    price: float | None
    side: str | None
    amount: float | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# Position Schemas
class PositionResponse(BaseModel):
    """Schema for position response."""

    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float | None
    market_value: float | None
    cost_basis: float
    unrealized_pl: float | None
    unrealized_plpc: float | None

    class Config:
        from_attributes = True


# Price Schemas
class PriceResponse(BaseModel):
    """Schema for price response."""

    symbol: str
    price: float
    timestamp: datetime
    is_market_open: bool | None = None


class PricesResponse(BaseModel):
    """Schema for multiple prices response."""

    prices: list[PriceResponse]


# CSV Upload Schema
class CSVGTTOrderRow(BaseModel):
    """Schema for a single CSV row."""

    symbol: str
    initial_trigger_price: float
    initial_quantity: int
    increment_qty_multiplier: float
    decrement_price_multiplier: float
    iterations: int
    time_in_force: str = "DAY"


class CSVGTTOrderBulk(BaseModel):
    """Schema for bulk CSV GTT order creation."""

    orders: list[CSVGTTOrderRow]


# Account Schema
class AccountResponse(BaseModel):
    """Comprehensive schema for account information."""

    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    day_trading_buying_power: float
    # Optional fields for comprehensive account documentation
    long_market_value: float | None = None
    short_market_value: float | None = None
    unsettled_funds: float | None = None
    pending_transfer_in: float | None = None
    pending_transfer_out: float | None = None
    non_marginable_buying_power: float | None = None
    regt_buying_power: float | None = None
    initial_margin: float | None = None
    maintenance_margin: float | None = None
    last_equity: float | None = None
    accrued_fees: float | None = None
    non_tradable_assets: float | None = None
    sma: float | None = None  # Special Memorandum Account


# Portfolio History Schema
class PortfolioHistoryResponse(BaseModel):
    """Schema for portfolio history data from Alpaca."""

    timestamp: list[int]  # UNIX epoch timestamps
    equity: list[float | None]  # Equity values in dollars (can be None)
    profit_loss: list[float | None]  # P/L in dollars from base_value (can be None)
    profit_loss_pct: list[float | None]  # P/L in percentage from base_value (can be None)
    base_value: float | None  # Basis value for P/L calculation
    base_value_asof: str | None = None  # Timestamp when base_value was set (RFC3339)
    timeframe: str  # Resolution used (1Min, 5Min, 15Min, 1H, 1D)

    @model_validator(mode='before')
    @classmethod
    def sanitize_history(cls, data: Any) -> Any:
        """Ensure base_value is not None and convert None in lists if needed."""
        if isinstance(data, dict):
            if data.get("base_value") is None:
                 data["base_value"] = 0.0
        return data


# Helper function to convert None to 0.0 for float fields
def none_to_zero(v):
    """Convert None to 0.0, otherwise return the value."""
    if v is None:
        return 0.0
    return v

# Annotated types with BeforeValidator - runs BEFORE Pydantic's type validation
SafeFloat = Annotated[float, BeforeValidator(none_to_zero)]


# Portfolio P/L Summary Schema
class PortfolioPLSummary(BaseModel):
    """Schema for portfolio P/L summary (Today, Weekly, Monthly, Yearly, All-Time)."""

    period: str  # "today", "weekly", "monthly", "yearly", "all_time"
    
    # Use float | None to allow None values to pass initial type check
    # Then use model_validator to convert them to 0.0
    profit_loss_dollars: float | None = 0.0  # P/L in dollars
    profit_loss_percent: float | None = 0.0  # P/L in percentage
    equity: float | None = 0.0  # Current equity
    base_value: float | None = 0.0  # Base value for calculation
    
    base_value_asof: str | None = None  # When base_value was set
    data_points: int = 0  # Number of data points in the period

    @model_validator(mode='before')
    @classmethod
    def sanitize_none_values(cls, data: Any) -> Any:
        """Convert None values to 0.0 for numeric fields."""
        if isinstance(data, dict):
            fields = ["profit_loss_dollars", "profit_loss_percent", "equity", "base_value"]
            for field in fields:
                if data.get(field) is None:
                    data[field] = 0.0
        return data
