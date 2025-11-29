"""Shared dependencies for routers."""

from typing import Annotated

from alpaca_client import AlpacaClient
from fastapi import Depends

# Global Alpaca client instance (set during lifespan startup)
_alpaca_client: AlpacaClient | None = None


def set_alpaca_client(client: AlpacaClient):
    """Set the global Alpaca client instance."""
    global _alpaca_client
    _alpaca_client = client


def get_alpaca_client() -> AlpacaClient:
    """Dependency to get the Alpaca client."""
    if _alpaca_client is None:
        raise RuntimeError("Alpaca client not initialized")
    return _alpaca_client


# Type alias for dependency injection
AlpacaClientDep = Annotated[AlpacaClient, Depends(get_alpaca_client)]
