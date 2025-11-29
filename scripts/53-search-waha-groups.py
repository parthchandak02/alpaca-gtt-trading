#!/usr/bin/env python3
"""Search WAHA groups by name.

Usage:
    backend/.venv/bin/python scripts/53-search-waha-groups.py "USA"
    backend/.venv/bin/python scripts/53-search-waha-groups.py "USA" --limit 200
"""

import argparse
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_path)

# Change to backend directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
backend_dir = os.path.join(project_root, "backend")
os.chdir(backend_dir)

# Load .env file
from dotenv import load_dotenv
load_dotenv("../.env", override=True)

import requests
from config import settings


def get_group_subject(group):
    """Extract group subject from various response formats."""
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


def main():
    parser = argparse.ArgumentParser(description="Search WAHA groups by name")
    parser.add_argument(
        "search_term",
        type=str,
        help="Search term to find in group names (case-insensitive)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Limit number of groups to fetch (default: 100)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="default",
        help="WAHA session name (default: default)",
    )
    args = parser.parse_args()

    # Get API key and URL from settings
    api_key = getattr(settings, "waha_api_key", "")
    api_url = getattr(settings, "waha_api_url", "http://localhost:3001")

    if not api_key:
        print("❌ WAHA_API_KEY not found in .env")
        print("   Set WAHA_API_KEY in .env file")
        return 1

    print(f"🔍 Searching for groups containing: '{args.search_term}'")
    print(f"📡 Fetching up to {args.limit} groups from WAHA...")
    print()

    # Fetch groups
    url = f"{api_url}/api/{args.session}/groups"
    params = {
        "limit": args.limit,
        "sortBy": "subject",
        "sortOrder": "asc",
    }
    headers = {"X-Api-Key": api_key}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        groups = response.json()

        # Search for matching groups
        search_term_lower = args.search_term.lower()
        matching_groups = []
        for g in groups:
            subject = get_group_subject(g).lower()
            if search_term_lower in subject:
                matching_groups.append(g)

        # Display results
        if not matching_groups:
            print(f"❌ No groups found containing '{args.search_term}'")
            print(f"   Searched {len(groups)} groups")
            return 1

        print(f"✅ Found {len(matching_groups)} group(s) containing '{args.search_term}':")
        print("=" * 70)
        print()

        for i, g in enumerate(matching_groups, 1):
            subject = get_group_subject(g)
            group_id = get_group_id(g)
            print(f"{i}. 📱 {subject}")
            print(f"   ID: {group_id}")
            print()

        return 0

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to WAHA API at {api_url}")
        print("   Is WAHA Docker container running? Run: ./scripts/50-setup-waha.sh")
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

