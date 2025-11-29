"""Server-Sent Events (SSE) router for real-time updates."""

import logging

from core.sse_manager import sse_manager
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def stream_events():
    """
    SSE endpoint for real-time order updates.

    Clients can connect to this endpoint to receive real-time notifications when:
    - Orders are created
    - Orders are updated
    - Orders are deleted
    - Order details are modified

    Returns:
        StreamingResponse: SSE stream with real-time events
    """
    logger.info("New SSE connection request")

    return StreamingResponse(
        sse_manager.connect(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",  # Prevent Cloudflare buffering
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "X-Content-Type-Options": "nosniff",  # Prevent MIME sniffing
        },
    )


@router.get("/status")
async def get_sse_status():
    """Get SSE connection status (for monitoring/debugging)."""
    return {
        "active_connections": sse_manager.get_connection_count(),
        "status": "running",
    }
