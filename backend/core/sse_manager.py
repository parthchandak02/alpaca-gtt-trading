"""Server-Sent Events (SSE) Manager for real-time updates.

This module manages SSE connections and broadcasts events to all connected clients.
Used for real-time synchronization of GTT orders across multiple users.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE connections and broadcasts events to all connected clients."""

    def __init__(self):
        self.active_connections: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        logger.info("SSE Manager initialized")

    async def connect(self) -> AsyncGenerator[str, None]:
        """
        Create a new SSE connection.

        Yields SSE-formatted messages from the queue.
        Automatically removes connection when client disconnects.
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            self.active_connections.append(queue)
            client_id = id(queue)
            logger.info(
                f"SSE client connected: {client_id} (total: {len(self.active_connections)})"
            )

        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Listen for events - heartbeats are sent via queue by _send_heartbeats
            heartbeat_task = asyncio.create_task(self._send_heartbeats(queue))

            while True:
                try:
                    # Wait for events from queue with timeout to allow cancellation
                    # Heartbeat task sends events every 15s to prevent Cloudflare edge timeouts
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    # No events in 30s (should never happen with 15s heartbeats)
                    # Send SSE comment as backup keepalive
                    yield ": ping\n\n"
                except asyncio.CancelledError:
                    logger.info(f"SSE client disconnected: {client_id}")
                    break
        finally:
            # Cleanup
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            async with self._lock:
                if queue in self.active_connections:
                    self.active_connections.remove(queue)
                    logger.info(
                        f"SSE client removed: {client_id} (remaining: {len(self.active_connections)})"
                    )

    async def _send_heartbeats(self, queue: asyncio.Queue):
        """Send periodic heartbeat messages to keep connection alive.

        Cloudflare edge closes idle SSE connections after ~100 seconds,
        so we send heartbeats every 15 seconds to prevent timeouts.
        """
        while True:
            try:
                await asyncio.sleep(15)  # 15 seconds for Cloudflare edge compatibility
                await queue.put(
                    {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                break

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        """
        Broadcast an event to all connected clients.

        Args:
            event_type: Type of event (e.g., 'order_created', 'order_updated', 'order_deleted')
            data: Event data to send to clients
        """
        if not self.active_connections:
            logger.debug(
                f"No active SSE connections - skipping broadcast: {event_type}"
            )
            return

        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Broadcasting SSE event: {event_type} to {len(self.active_connections)} client(s)"
        )

        # Send to all active connections
        async with self._lock:
            failed_queues = []
            for queue in self.active_connections:
                try:
                    # Use put_nowait to avoid blocking if queue is full
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(
                        f"Queue full for client {id(queue)} - skipping event"
                    )
                except Exception as e:
                    logger.error(f"Error broadcasting to client {id(queue)}: {e}")
                    failed_queues.append(queue)

            # Remove failed connections
            for queue in failed_queues:
                if queue in self.active_connections:
                    self.active_connections.remove(queue)
                    logger.info(f"Removed failed SSE connection: {id(queue)}")

    def get_connection_count(self) -> int:
        """Get the number of active SSE connections."""
        return len(self.active_connections)


# Global SSE manager instance
sse_manager = SSEManager()
