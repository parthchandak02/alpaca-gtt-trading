#!/usr/bin/env python3
"""Migration script to add fractional_quantity column to gtt_order_details table."""
import sqlite3
import sys
from pathlib import Path

# Get database path
backend_dir = Path(__file__).parent.parent
db_path = backend_dir / "database" / "alpaca_orders_paper.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    sys.exit(1)

def migrate():
    """Add fractional_quantity column if it doesn't exist."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(gtt_order_details)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'fractional_quantity' not in columns:
            print("Adding fractional_quantity column to gtt_order_details...")
            cursor.execute("""
                ALTER TABLE gtt_order_details 
                ADD COLUMN fractional_quantity REAL
            """)
            conn.commit()
            print("✅ Migration complete: fractional_quantity column added")
        else:
            print("✅ Column fractional_quantity already exists, skipping migration")
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

