#!/usr/bin/env python3
"""Daily summary script - CLI wrapper for daily_summary_service.

This script provides a command-line interface for the daily trading summary.
The core logic lives in backend/core/daily_summary_service.py.

Usage:
    # Dry run (preview only, no WhatsApp):
    backend/.venv/bin/python scripts/55-trigger-daily-summary.py --dry-run
    
    # Send to WhatsApp:
    backend/.venv/bin/python scripts/55-trigger-daily-summary.py
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

# Rich for nice terminal output (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False


def main():
    parser = argparse.ArgumentParser(description="Generate and send daily trading summary")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview message without sending to WhatsApp",
    )
    args = parser.parse_args()
    
    if HAS_RICH:
        console.print("[bold blue]Daily Trading Summary Generator[/bold blue]")
        console.print("=" * 50)
    else:
        print("Daily Trading Summary Generator")
        print("=" * 50)
    
    # Import after path setup
    from alpaca_client import AlpacaClient
    from database import get_db
    from core.daily_summary_service import generate_daily_summary
    
    # Get database session and Alpaca client
    print("\nFetching data...")
    db = next(get_db())
    alpaca_client = AlpacaClient()
    
    try:
        # Generate the summary using the shared service
        message = generate_daily_summary(db, alpaca_client)
        
        # Display the message
        print("\n" + "=" * 50)
        print("GENERATED MESSAGE:")
        print("=" * 50)
        
        if HAS_RICH:
            console.print(Panel(message, title="Daily Summary", border_style="green"))
        else:
            print(message)
        
        print("=" * 50)
        
        if args.dry_run:
            print("\nDRY RUN - Message NOT sent to WhatsApp")
            print("Remove --dry-run flag to send the message")
            return 0
        
        # Send to WhatsApp
        print("\nSending to WhatsApp...")
        
        from core.whatsapp_service import get_whatsapp_service
        whatsapp = get_whatsapp_service()
        
        if not whatsapp.enabled:
            print("WhatsApp notifications are disabled")
            print("Set WHATSAPP_ENABLED=true in .env")
            return 1
        
        if not whatsapp.is_available():
            print("WAHA API is not available")
            print("Is WAHA Docker container running?")
            return 1
        
        success = whatsapp.send_message(message=message)
        
        if success:
            print("Daily summary sent to WhatsApp!")
            if whatsapp.group_id:
                print(f"Sent to group: {whatsapp.group_id}")
            else:
                print(f"Sent to: {whatsapp.phone_number}")
            return 0
        else:
            print("Failed to send message")
            return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
