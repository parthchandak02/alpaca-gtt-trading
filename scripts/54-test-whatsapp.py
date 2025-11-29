#!/usr/bin/env python3
"""Test script for WhatsApp notifications via WAHA.

This script tests the WhatsApp service by sending a test message.

Usage:
    # Using backend venv directly:
    backend/.venv/bin/python scripts/54-test-whatsapp.py
    
    # Or with uv:
    uv run --directory backend python scripts/54-test-whatsapp.py
    
    # Or with phone number override:
    backend/.venv/bin/python scripts/54-test-whatsapp.py --phone 12132132130
"""

import argparse
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_path)

# Change to backend directory so database paths resolve correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
backend_dir = os.path.join(project_root, "backend")
os.chdir(backend_dir)

# Load .env file before importing config
from dotenv import load_dotenv

load_dotenv("../.env", override=True)

from core.whatsapp_service import get_whatsapp_service
import requests


def main():
    parser = argparse.ArgumentParser(description="Test WhatsApp notifications")
    parser.add_argument(
        "--phone",
        type=str,
        help="Phone number to send test message to (optional, uses config default)",
    )
    parser.add_argument(
        "--group",
        type=str,
        help="Group name to send test message to (searches by name)",
    )
    parser.add_argument(
        "--group-id",
        type=str,
        help="Group ID to send test message to (format: 123456789@g.us)",
    )
    parser.add_argument(
        "--message",
        type=str,
        default="🧪 Test message from Alpaca Trader!",
        help="Test message to send",
    )
    args = parser.parse_args()

    print("🧪 Testing WhatsApp Service")
    print("=" * 50)

    # Get WhatsApp service
    whatsapp = get_whatsapp_service()

    # Check if enabled
    if not whatsapp.enabled:
        print("❌ WhatsApp notifications are disabled")
        print("   Set WHATSAPP_ENABLED=true in .env")
        return 1

    # Check if phone number is configured
    if not args.phone and not whatsapp.phone_number:
        print("❌ No phone number configured")
        print("   Set WHATSAPP_PHONE_NUMBER in .env or use --phone argument")
        return 1

    # Check WAHA availability
    print(f"📡 Checking WAHA API at {whatsapp.api_url}...")
    if not whatsapp.is_available():
        print("❌ WAHA API is not available")
        print("   Is WAHA Docker container running?")
        print("   Run: ./scripts/50-setup-waha.sh")
        return 1

    print("✅ WAHA API is available")

    # Check session status
    session_status = whatsapp.check_session_status()
    if session_status:
        status = session_status.get("status", "unknown")
        print(f"📱 Session '{whatsapp.session_name}' status: {status}")
        if status != "WORKING":
            print("⚠️  Warning: Session is not WORKING")
            print("   Make sure you've scanned the QR code")
    else:
        print(f"⚠️  Could not check session '{whatsapp.session_name}' status")

    # Determine recipient
    if args.group_id:
        # Direct group ID provided
        chat_id = args.group_id
        print(f"\n📤 Sending test message to group ID: {chat_id}...")
        print(f"   Message: {args.message}")
        
        # Send directly to group
        url = f"{whatsapp.api_url}/api/sendText"
        headers = whatsapp._get_headers()
        payload = {
            "session": whatsapp.session_name,
            "chatId": chat_id,
            "text": args.message,
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            success = True
        except Exception as e:
            print(f"❌ Error: {e}")
            success = False
            
    elif args.group:
        # Search for group by name
        print(f"\n🔍 Searching for group: {args.group}...")
        # Use sortBy=subject to get groups sorted alphabetically (helps with search)
        url = f"{whatsapp.api_url}/api/{whatsapp.session_name}/groups?sortBy=subject&sortOrder=asc&limit=1000"
        headers = whatsapp._get_headers()
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            groups = response.json()
            
            # Extract subject from different possible structures
            def get_group_subject(group):
                """Extract group subject from various response formats."""
                # Try different possible locations
                if "subject" in group:
                    return group["subject"]
                if "groupMetadata" in group and "subject" in group["groupMetadata"]:
                    return group["groupMetadata"]["subject"]
                if "name" in group:
                    return group["name"]
                return ""
            
            def get_group_id(group):
                """Extract group ID from various response formats."""
                if "id" in group:
                    id_val = group["id"]
                    if isinstance(id_val, str):
                        return id_val
                    if isinstance(id_val, dict) and "_serialized" in id_val:
                        return id_val["_serialized"]
                if "groupMetadata" in group and "id" in group["groupMetadata"]:
                    id_val = group["groupMetadata"]["id"]
                    if isinstance(id_val, dict) and "_serialized" in id_val:
                        return id_val["_serialized"]
                    if isinstance(id_val, str):
                        return id_val
                return None
            
            # Search for group by name (case-insensitive, partial match)
            search_term = args.group.lower()
            matching_groups = []
            for g in groups:
                subject = get_group_subject(g).lower()
                if search_term in subject:
                    matching_groups.append({
                        "subject": get_group_subject(g),
                        "id": get_group_id(g),
                        "raw": g
                    })
            
            if not matching_groups:
                print(f"❌ Group '{args.group}' not found")
                print(f"   Found {len(groups)} total groups")
                print("   Try using --group-id with the group ID instead")
                return 1
            
            if len(matching_groups) > 1:
                print(f"⚠️  Found {len(matching_groups)} matching groups:")
                for g in matching_groups[:5]:
                    print(f"   - {g['subject']}: {g['id']}")
                print(f"   Using first match: {matching_groups[0]['subject']}")
            
            group_id = matching_groups[0]["id"]
            if not group_id:
                print(f"❌ Could not extract group ID from response")
                return 1
            print(f"✅ Found group: {matching_groups[0]['subject']}")
            print(f"\n📤 Sending test message to group...")
            print(f"   Message: {args.message}")
            
            # Send to group
            url = f"{whatsapp.api_url}/api/sendText"
            payload = {
                "session": whatsapp.session_name,
                "chatId": group_id,
                "text": args.message,
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            success = True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            success = False
    else:
        # Send to phone number
        phone = args.phone or whatsapp.phone_number
        print(f"\n📤 Sending test message to {phone}...")
        print(f"   Message: {args.message}")

        success = whatsapp.send_message(phone_number=phone, message=args.message)

    if success:
        print("\n✅ Test message sent successfully!")
        print("   Check your WhatsApp for the message")
        return 0
    else:
        print("\n❌ Failed to send test message")
        print("   Check logs for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())

