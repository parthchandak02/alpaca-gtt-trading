"""Application-wide constants."""

# Floating point precision tolerance for fractional quantity checks
FLOATING_POINT_TOLERANCE = 1e-6

# Minimum quantity for fractional orders
MIN_FRACTIONAL_QUANTITY = 0.01

# Price tolerance for grouping trigger prices in charts (1 cent)
PRICE_GROUPING_TOLERANCE = 0.01

# Time intervals (in milliseconds for frontend, seconds for backend)
MARKET_OPEN_POLL_INTERVAL_SECONDS = 10
MARKET_CLOSED_POLL_INTERVAL_SECONDS = 60
ACCOUNT_REFRESH_INTERVAL_MS = 30000  # 30 seconds
MARKET_STATUS_CHECK_INTERVAL_MS = 60000  # 60 seconds
MARKET_CLOSED_POLL_INTERVAL_MS = 300000  # 5 minutes

# API timeouts
CSV_UPLOAD_TIMEOUT_MS = 60000  # 60 seconds

# Toast notification durations
TOAST_ERROR_DURATION_MS = 6000
TOAST_WARNING_DURATION_MS = 8000
TOAST_INFO_DURATION_MS = 5000

# Order limits
MAX_GTT_ITERATIONS = 20
DEFAULT_GTT_ITERATIONS = 5
DEFAULT_INCREMENT_MULTIPLIER = 1.2
MAX_CSV_LEVELS = 5  # Maximum number of levels in CSV ladder format

# Cache refresh intervals
CACHE_STALE_THRESHOLD_MINUTES = 5
BACKGROUND_REFRESH_INTERVAL_MINUTES = 2
BATCH_REFRESH_LIMIT = 50

# Price formatting
PRICE_DECIMAL_PLACES = 2

# API defaults
DEFAULT_ACTIVITIES_LIMIT = 100
DEFAULT_ORDERS_LIMIT = 100
DEFAULT_ERROR_DETAILS_LIMIT = 5  # Max error details to show in response

# Background task intervals (seconds)
MARKET_OPEN_POLL_INTERVAL_SECONDS = 10
MARKET_CLOSED_POLL_INTERVAL_SECONDS = 60
