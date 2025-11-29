"""Main FastAPI application."""

import logging

# Set up logging (prevent duplicate handlers)
# CRITICAL: Configure logging BEFORE importing any modules that might log
import sys

from config import settings
from core.lifespan import lifespan
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    account,
    activities,
    assets,
    auth,
    csv,
    events,
    gtt_orders,
    historical,
    orders,
    prices,
    version,
    websocket,
)

# Remove ALL existing handlers from root logger
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
    handler.close()

# Disable propagation temporarily to prevent any module loggers from adding handlers
root_logger.propagate = False

# Create single stream handler - explicitly use stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(getattr(logging, settings.log_level))
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# Add ONLY this handler
root_logger.addHandler(handler)
root_logger.setLevel(getattr(logging, settings.log_level))

# Re-enable propagation so child loggers work, but root handles once
root_logger.propagate = True

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Alpaca GTT Order Tracker",
    description="Good-Till-Triggered order tracking and automation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timeout middleware - prevent hanging requests
import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_504_GATEWAY_TIMEOUT


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to timeout requests that take too long."""

    async def dispatch(self, request, call_next):
        # Skip timeout for WebSocket connections
        if request.url.path.startswith("/api/ws/"):
            return await call_next(request)

        try:
            # Set timeout to 29 seconds (fail before frontend's 30s timeout)
            response = await asyncio.wait_for(call_next(request), timeout=29.0)
            return response
        except TimeoutError:
            logger.warning(f"Request timeout: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=HTTP_504_GATEWAY_TIMEOUT,
                content={"detail": "Request timeout: Server took too long to respond"},
            )


app.add_middleware(TimeoutMiddleware)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Alpaca GTT Order Tracker API",
        "version": "1.0.0",
        "trading_mode": "PAPER" if settings.use_paper_trading else "LIVE",
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": "Alpaca GTT Order Tracker API",
        "version": "1.0.0",
    }


# Register routers
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(prices.router)
app.include_router(gtt_orders.router)
app.include_router(activities.router)
app.include_router(orders.router)
app.include_router(assets.router)
app.include_router(historical.router)
app.include_router(csv.router)
app.include_router(events.router)
app.include_router(websocket.router)
app.include_router(version.router)


if __name__ == "__main__":
    import logging.config

    import uvicorn

    # Ensure uvicorn uses our logging configuration
    # Disable uvicorn's default access logging to prevent duplicates
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Use our logging configuration, not uvicorn's
        access_log=False,  # Disable uvicorn access logs (prevents duplicate HTTP logs)
        use_colors=False,  # Disable colors for cleaner PM2 logs
    )
