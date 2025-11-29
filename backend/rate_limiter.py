"""Rate limiter for Alpaca API calls.

Alpaca API limits:
- 200 requests per minute per account
- Burst limit: 10 requests per second

This module implements a token bucket rate limiter to ensure we stay within limits.
"""

import asyncio
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for Alpaca API calls.

    Implements:
    - 200 requests per minute (3.33 requests/second average)
    - 10 requests per second burst limit

    Uses a conservative approach: 3 requests/second average with 10 burst capacity.
    """

    def __init__(self, rate: float = 3.0, burst: int = 10):
        """
        Args:
            rate: Average requests per second (default: 3.0 to stay well under 200/min)
            burst: Maximum burst capacity (default: 10 to match Alpaca's burst limit)
        """
        self.rate = rate  # tokens per second
        self.burst = burst  # maximum tokens
        self.tokens = burst  # current tokens
        self.last_update = time.time()
        self.lock = Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary.

        This respects both the average rate (200/min) and burst limit (10/sec).
        """
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update

                # Add tokens based on elapsed time
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

            # Not enough tokens, wait
            wait_time = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)

    def try_acquire(self) -> bool:
        """Try to acquire a token without waiting.

        Returns:
            True if token acquired, False if rate limit exceeded
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True

            return False


# Global rate limiter instance
_global_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        # Conservative: 3 req/sec average (180/min) with 10 burst
        # This leaves headroom under the 200/min limit
        _global_limiter = RateLimiter(rate=3.0, burst=10)
    return _global_limiter


async def rate_limit_alpaca_call():
    """Rate limit an Alpaca API call.

    Call this before making any Alpaca API request to ensure we stay within limits.
    """
    limiter = get_rate_limiter()
    await limiter.acquire()


def rate_limit_alpaca_call_sync():
    """Rate limit an Alpaca API call (synchronous version for use in sync code).

    Call this before making any Alpaca API request in synchronous code paths.
    Uses synchronous polling to avoid blocking issues in background tasks.
    """
    limiter = get_rate_limiter()
    import time

    # Poll with exponential backoff to avoid busy-waiting
    max_wait = 5.0  # Maximum wait time (5 seconds)
    wait_time = 0.01  # Start with 10ms
    total_waited = 0.0

    while not limiter.try_acquire():
        if total_waited >= max_wait:
            # If we've waited too long, log warning but proceed anyway
            # This prevents the background task from being blocked indefinitely
            logger.warning(f"Rate limiter wait exceeded {max_wait}s, proceeding anyway")
            break

        time.sleep(wait_time)
        total_waited += wait_time
        wait_time = min(wait_time * 1.5, 0.5)  # Exponential backoff, max 500ms
