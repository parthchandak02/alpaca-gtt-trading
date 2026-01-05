"""WhatsApp notification service using WAHA (WhatsApp HTTP API).

This service provides a simple interface to send WhatsApp messages via WAHA.
WAHA runs as a Docker container and exposes a REST API on localhost:3001.

Usage:
    from core.whatsapp_service import WhatsAppService
    
    whatsapp = WhatsAppService()
    whatsapp.send_message("12132132130", "Order filled!")
"""

import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending WhatsApp messages via WAHA API."""

    def __init__(self):
        """Initialize WhatsApp service with configuration from settings."""
        self.api_url = getattr(settings, "waha_api_url", "http://localhost:3001")
        self.session_name = getattr(settings, "waha_session_name", "default")
        self.api_key = getattr(settings, "waha_api_key", "")
        self.enabled = getattr(settings, "whatsapp_enabled", False)
        self.phone_number = getattr(settings, "whatsapp_phone_number", "")
        self.group_id = getattr(settings, "whatsapp_group_id", "")

        if not self.enabled:
            logger.debug("WhatsApp notifications are disabled")
        elif not self.phone_number and not self.group_id:
            logger.warning(
                "WhatsApp enabled but no recipient configured. "
                "Set WHATSAPP_PHONE_NUMBER or WHATSAPP_GROUP_ID in .env"
            )

    def _get_headers(self) -> dict:
        """Get HTTP headers for WAHA API requests.
        
        Returns:
            Headers dict with API key if configured
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number for WAHA API.
        
        WAHA expects format: {phone}@c.us
        Phone should be digits only (no +, spaces, or dashes).
        
        Args:
            phone: Phone number (with or without country code)
            
        Returns:
            Formatted phone number for WAHA (e.g., "12132132130@c.us")
        """
        # Remove all non-digit characters
        digits_only = "".join(filter(str.isdigit, phone))
        
        # If phone number is not provided, use configured default
        if not digits_only:
            digits_only = "".join(filter(str.isdigit, self.phone_number))
        
        if not digits_only:
            raise ValueError("Phone number is required")
        
        return f"{digits_only}@c.us"

    def send_message(
        self, phone_number: Optional[str] = None, message: str = "", use_group: bool = True
    ) -> bool:
        """Send WhatsApp message via WAHA API.
        
        Args:
            phone_number: Recipient phone number (optional, uses default if not provided)
            message: Message text to send
            use_group: If True and group_id is configured, send to group instead of phone
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("WhatsApp notifications disabled, skipping message")
            return False

        if not message:
            logger.warning("Empty message, skipping WhatsApp send")
            return False

        try:
            # Determine chat_id: prefer group if configured and use_group is True
            if use_group and self.group_id:
                # Group ID already includes @g.us suffix
                chat_id = self.group_id if "@" in self.group_id else f"{self.group_id}@g.us"
            else:
                # Use provided phone number or default from config
                recipient = phone_number or self.phone_number
                if not recipient:
                    logger.error("No phone number provided and no default configured")
                    return False
                # Format phone number for WAHA
                chat_id = self._format_phone_number(recipient)

            # Prepare API request
            url = f"{self.api_url}/api/sendText"
            payload = {
                "session": self.session_name,
                "chatId": chat_id,
                "text": message,
            }

            logger.debug(f"Sending WhatsApp message to {chat_id}: {message[:50]}...")

            # Send message via WAHA API (with authentication header)
            headers = self._get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            logger.info(f"✅ WhatsApp message sent successfully to {chat_id}")
            return True

        except requests.exceptions.ConnectionError:
            logger.warning(
                f"⚠️  Cannot connect to WAHA API at {self.api_url}. "
                "Is WAHA Docker container running? Run: ./scripts/50-setup-waha.sh"
            )
            return False
        except requests.exceptions.Timeout:
            logger.warning("⚠️  WAHA API request timed out")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ WAHA API error: {e.response.status_code} - {e.response.text}")
            return False
        except ValueError as e:
            logger.error(f"❌ Invalid phone number: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending WhatsApp message: {e}", exc_info=True)
            return False

    def check_session_status(self) -> Optional[dict]:
        """Check WAHA session status.
        
        Returns:
            Session status dict if available, None otherwise
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.api_url}/api/sessions"
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            sessions = response.json()
            # Find our session
            for session in sessions:
                if session.get("name") == self.session_name:
                    return session
            return None
        except Exception as e:
            logger.debug(f"Could not check WAHA session status: {e}")
            return None

    def is_available(self) -> bool:
        """Check if WAHA service is available and configured.
        
        Returns:
            True if WAHA is enabled, configured, and reachable
        """
        if not self.enabled:
            return False
        
        try:
            # Quick health check - try to get sessions (with auth)
            url = f"{self.api_url}/api/sessions"
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=2)
            return response.status_code == 200
        except Exception:
            return False


# Global instance (singleton pattern)
_whatsapp_service: Optional[WhatsAppService] = None


def get_whatsapp_service() -> WhatsAppService:
    """Get global WhatsApp service instance.
    
    Returns:
        WhatsAppService instance
    """
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppService()
    return _whatsapp_service

