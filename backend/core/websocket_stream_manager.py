"""Base class for managing WebSocket streams with common reconnection logic.

This module provides a reusable base class for WebSocket stream management,
eliminating code duplication in reconnection logic.
"""

import asyncio
import logging
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


class WebSocketStreamManager:
    """Base class for managing WebSocket streams with reconnection logic."""

    def __init__(self, stream_name: str, max_reconnect_attempts: int = 10):
        """Initialize stream manager.

        Args:
            stream_name: Name of the stream (for logging)
            max_reconnect_attempts: Maximum reconnection attempts before giving up
        """
        self.stream_name = stream_name
        self._stream: object | None = None
        self._is_connected = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = max_reconnect_attempts
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the stream."""
        self._task = asyncio.create_task(self._run_stream())

    async def stop(self):
        """Stop the stream."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._stream:
            try:
                self._stream.stop()
            except Exception as e:
                logger.error(f"Error stopping {self.stream_name}: {e}")

    def is_connected(self) -> bool:
        """Check if stream is connected."""
        return self._is_connected

    async def _run_stream(self):
        """Run the stream with reconnection logic (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement _run_stream")

    async def _create_stream(self):
        """Create the stream instance (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement _create_stream")

    async def _setup_stream(self):
        """Set up stream subscriptions (to be implemented by subclasses)."""

    async def _run_blocking_stream(self, stream_run_func: Callable):
        """Run a blocking stream function with reconnection logic.

        Args:
            stream_run_func: Function that runs the stream (blocking)
        """
        while True:
            try:
                logger.info(f"Connecting to {self.stream_name}...")

                # Create stream
                await self._create_stream()

                # Set up subscriptions
                await self._setup_stream()

                # Run the stream (blocking call - run in thread pool)
                await run_in_threadpool(stream_run_func)

                # If we get here, stream ended normally
                self._is_connected = True
                self._reconnect_attempts = 0
                self._reconnect_delay = 1.0

                logger.info(f"{self.stream_name} connected")

            except asyncio.CancelledError:
                logger.info(f"{self.stream_name} cancelled")
                break
            except Exception as e:
                self._is_connected = False
                logger.error(f"{self.stream_name} error: {e}", exc_info=True)

                # Exponential backoff reconnection
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    self._reconnect_attempts += 1
                    delay = min(
                        self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                        self._max_reconnect_delay,
                    )
                    logger.info(
                        f"Reconnecting {self.stream_name} in {delay:.1f}s "
                        f"(attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Max reconnection attempts reached for {self.stream_name}"
                    )
                    await asyncio.sleep(self._max_reconnect_delay)
