"""WebSocket router for real-time price updates."""

import asyncio
import json
import logging
import uuid

from config import settings
from core.websocket_manager import ws_manager
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ws", tags=["websocket"])


def _is_origin_allowed(origin: str | None) -> bool:
    """Check if WebSocket origin is allowed."""
    # Allow connections without origin (e.g., from same origin, localhost, Postman, etc.)
    if not origin:
        return True

    # Get allowed origins from settings (can be string or list)
    cors_origins = (
        settings.cors_origins
        if hasattr(settings, "cors_origins")
        else "http://localhost:3000"
    )

    # Convert to list if it's a string
    if isinstance(cors_origins, str):
        allowed_origins = [o.strip() for o in cors_origins.split(",")]
    else:
        allowed_origins = cors_origins

    # Allow all origins if "*" is in the list
    if "*" in allowed_origins:
        return True

    # Check if origin matches any allowed origin
    return origin in allowed_origins


@router.websocket("/prices")
async def websocket_prices(websocket: WebSocket):
    """
    WebSocket endpoint for real-time price updates.

    Clients can subscribe to symbols and receive price updates in real-time.

    Message protocol:
    - Subscribe: {"type": "subscribe", "symbols": ["AAPL", "BTC/USD"]}
    - Unsubscribe: {"type": "unsubscribe", "symbols": ["AAPL"]}
    """
    # Accept WebSocket connection first (required before checking headers)
    # Note: FastAPI/Starlette handles CORS for WebSocket differently
    # We'll accept and then check origin if needed
    client_id = str(uuid.uuid4())
    heartbeat_task = None

    try:
        # Accept connection - this must happen before we can check headers properly
        await websocket.accept()

        # Check origin after accepting (for logging/monitoring)
        origin = websocket.headers.get("origin") or websocket.headers.get("Origin")
        if origin and not _is_origin_allowed(origin):
            logger.warning(
                f"WebSocket connection from unallowed origin '{origin}' (client: {client_id})"
            )
            # Note: Connection already accepted, but we can log it

        await ws_manager.connect(websocket, client_id)

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(_send_heartbeats(client_id))

        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                message_type = message.get("type")

                if message_type == "subscribe":
                    symbols = message.get("symbols", [])
                    if symbols:
                        await ws_manager.subscribe(client_id, symbols)
                        await ws_manager.send_to_client(
                            client_id, {"type": "subscribed", "symbols": symbols}
                        )
                    else:
                        await ws_manager.send_to_client(
                            client_id,
                            {
                                "type": "error",
                                "message": "No symbols provided for subscription",
                            },
                        )

                elif message_type == "unsubscribe":
                    symbols = message.get("symbols", [])
                    if symbols:
                        await ws_manager.unsubscribe(client_id, symbols)
                        await ws_manager.send_to_client(
                            client_id, {"type": "unsubscribed", "symbols": symbols}
                        )
                    else:
                        await ws_manager.send_to_client(
                            client_id,
                            {
                                "type": "error",
                                "message": "No symbols provided for unsubscription",
                            },
                        )

                else:
                    await ws_manager.send_to_client(
                        client_id,
                        {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                        },
                    )

            except WebSocketDisconnect:
                # Client disconnected - break out of message loop immediately
                logger.info(f"WebSocket client disconnected: {client_id}")
                break

            except json.JSONDecodeError:
                await ws_manager.send_to_client(
                    client_id, {"type": "error", "message": "Invalid JSON"}
                )

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                # Only send error if connection is still open
                try:
                    await ws_manager.send_to_client(
                        client_id, {"type": "error", "message": str(e)}
                    )
                except Exception:
                    # Connection may have closed, break loop
                    logger.debug(
                        f"Could not send error message to client {client_id}, connection may be closed"
                    )
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cancel heartbeat task if it was created
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        await ws_manager.disconnect(client_id)


async def _send_heartbeats(client_id: str):
    """Send heartbeat every 30 seconds to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(30)
            await ws_manager.send_heartbeat(client_id)
    except asyncio.CancelledError:
        pass
