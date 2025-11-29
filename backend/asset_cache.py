"""Asset cache management for storing asset information and fractional trading status."""

import json
import logging
from pathlib import Path

from alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
ASSETS_FILE = CACHE_DIR / "assets.json"


def ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(exist_ok=True)


def load_assets_cache() -> dict[str, dict]:
    """Load assets cache from JSON file."""
    ensure_cache_dir()

    if not ASSETS_FILE.exists():
        logger.warning(f"Assets cache file not found: {ASSETS_FILE}")
        return {}

    try:
        with open(ASSETS_FILE) as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} assets from cache")
            return data
    except Exception as e:
        logger.error(f"Error loading assets cache: {e}")
        return {}


def save_assets_cache(assets: dict[str, dict]):
    """Save assets cache to JSON file."""
    ensure_cache_dir()

    try:
        with open(ASSETS_FILE, "w") as f:
            json.dump(assets, f, indent=2)
        logger.info(f"Saved {len(assets)} assets to cache: {ASSETS_FILE}")
    except Exception as e:
        logger.error(f"Error saving assets cache: {e}")
        raise


def refresh_assets_cache() -> dict[str, dict]:
    """Fetch all assets from Alpaca and update cache."""
    logger.info("Refreshing assets cache from Alpaca...")

    try:
        from rate_limiter import rate_limit_alpaca_call_sync

        alpaca = AlpacaClient()
        # Rate limit before fetching all assets (this is a large operation)
        rate_limit_alpaca_call_sync()
        assets_list = alpaca.get_all_assets()

        # Convert to dictionary keyed by symbol
        assets_dict = {}
        for asset in assets_list:
            symbol = asset["symbol"].upper()
            assets_dict[symbol] = {
                "symbol": symbol,
                "name": asset.get("name", symbol),
                "exchange": asset.get("exchange", ""),
                "class": asset.get("class", ""),
                "tradable": asset.get("tradable", True),
                "fractionable": asset.get("fractionable", False),
            }

        save_assets_cache(assets_dict)
        logger.info(f"Successfully cached {len(assets_dict)} assets")
        return assets_dict
    except Exception as e:
        logger.error(f"Error refreshing assets cache: {e}")
        raise


def get_asset_fractionable(symbol: str) -> bool | None:
    """Check if an asset supports fractional trading."""
    assets = load_assets_cache()
    symbol_upper = symbol.upper()

    if symbol_upper in assets:
        return assets[symbol_upper].get("fractionable", False)

    # If not in cache, try to get from Alpaca directly
    try:
        from rate_limiter import rate_limit_alpaca_call_sync

        alpaca = AlpacaClient()
        # Rate limit before fetching asset info
        rate_limit_alpaca_call_sync()
        asset_info = alpaca.get_asset_info(symbol_upper)
        if asset_info:
            return asset_info.get("fractionable", False)
    except Exception as e:
        logger.warning(f"Could not get fractionable status for {symbol}: {e}")

    return None


def is_asset_fractionable(symbol: str) -> bool:
    """Check if an asset supports fractional trading. Returns False if unknown."""
    fractionable = get_asset_fractionable(symbol)
    return fractionable if fractionable is not None else False
