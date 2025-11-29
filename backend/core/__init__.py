"""Core application infrastructure."""

from .background_tasks import price_monitoring_loop, set_alpaca_client_for_monitoring
from .dependencies import get_alpaca_client
from .lifespan import lifespan

__all__ = [
    "get_alpaca_client",
    "lifespan",
    "price_monitoring_loop",
    "set_alpaca_client_for_monitoring",
]
