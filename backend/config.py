"""Configuration settings for the application."""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Force reload .env file on every restart (even if already loaded)
# This ensures PM2 restarts pick up new environment variables
# Note: PM2 doesn't auto-reload .env changes - use 'pm2 reload --update-env' or restart
load_dotenv("../.env", override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Trading Mode
    use_paper_trading: bool = True

    # Alpaca API - Paper Trading
    alpaca_paper_api_key: str = ""
    alpaca_paper_secret_key: str = ""
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"

    # Alpaca API - Live Trading
    alpaca_live_api_key: str = ""
    alpaca_live_secret_key: str = ""
    alpaca_live_base_url: str = "https://api.alpaca.markets"

    # Alpaca Data API (same for both)
    alpaca_data_url: str = "https://data.alpaca.markets"

    # Database
    # Separate databases for paper and live trading to prevent data mixing
    # Paper trading: alpaca_orders_paper.db
    # Live trading: alpaca_orders_live.db
    database_url: str = ""  # Will be set dynamically based on trading mode

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Price Monitoring
    price_poll_interval: int = 60  # seconds

    # CORS (can be comma-separated string in .env)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Authentication
    ui_password: str = ""
    jwt_secret_key: str = ""

    # Logging
    log_level: str = "INFO"
    debug: bool = False

    # Frontend
    next_public_api_url: str = "http://localhost:8000"

    # Cloudflare (optional)
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""

    # WhatsApp/WAHA (optional)
    whatsapp_enabled: bool = False
    waha_api_url: str = "http://localhost:3001"  # Default port 3001 (3000 used by frontend)
    waha_api_key: str = ""  # WAHA API key (check docker logs for generated key)
    waha_session_name: str = "default"
    whatsapp_phone_number: str = ""  # Your phone number (digits only, no + or spaces)

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env that aren't in the model


_settings = Settings()

# Parse CORS origins from comma-separated string
_cors_origins_list = [
    origin.strip() for origin in _settings.cors_origins.split(",") if origin.strip()
]


# Create a simple object to hold settings with parsed CORS and computed properties
class SettingsWrapper:
    def __init__(self, base_settings: Settings, cors_list: list[str]):
        for key, value in base_settings.model_dump().items():
            # Skip properties that are computed dynamically
            if key not in ["cors_origins", "database_url"]:
                setattr(self, key, value)
        self.cors_origins = cors_list
        # database_url is a property, don't set it here

    @property
    def alpaca_api_key(self) -> str:
        """Get API key based on trading mode."""
        # Use paper keys for paper trading, live keys for live trading
        return (
            self.alpaca_paper_api_key
            if self.use_paper_trading
            else self.alpaca_live_api_key
        )

    @property
    def alpaca_secret_key(self) -> str:
        """Get secret key based on trading mode."""
        # Use paper keys for paper trading, live keys for live trading
        return (
            self.alpaca_paper_secret_key
            if self.use_paper_trading
            else self.alpaca_live_secret_key
        )

    @property
    def alpaca_base_url(self) -> str:
        """Get base URL based on trading mode."""
        return (
            self.alpaca_paper_base_url
            if self.use_paper_trading
            else self.alpaca_live_base_url
        )

    @property
    def database_url(self) -> str:
        """Get database URL based on trading mode.

        Uses separate databases for paper and live trading to prevent data mixing.
        This is a critical safety feature - paper and live trading data must never mix.
        """
        if self.use_paper_trading:
            return "sqlite:///./database/alpaca_orders_paper.db"
        return "sqlite:///./database/alpaca_orders_live.db"


settings = SettingsWrapper(_settings, _cors_origins_list)
