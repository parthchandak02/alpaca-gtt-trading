#!/usr/bin/env python3
"""Migration script to add expired_at and is_manually_linked fields to GTTOrderDetail."""

import sqlite3
from pathlib import Path


def migrate_database(db_path: Path):
    """Add new fields to GTTOrderDetail table."""
    if not db_path.exists():
        print(f"Database {db_path} does not exist. Skipping migration.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(gtt_order_details)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add expired_at column if it doesn't exist
        if "expired_at" not in columns:
            print(f"Adding expired_at column to {db_path}")
            cursor.execute(
                "ALTER TABLE gtt_order_details ADD COLUMN expired_at DATETIME"
            )
        else:
            print(f"expired_at column already exists in {db_path}")

        # Add is_manually_linked column if it doesn't exist
        if "is_manually_linked" not in columns:
            print(f"Adding is_manually_linked column to {db_path}")
            cursor.execute(
                "ALTER TABLE gtt_order_details ADD COLUMN is_manually_linked BOOLEAN DEFAULT 0"
            )
        else:
            print(f"is_manually_linked column already exists in {db_path}")

        conn.commit()
        print(f"Migration completed successfully for {db_path}")

    except Exception as e:
        print(f"Error migrating {db_path}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    backend_dir = Path(__file__).parent
    database_dir = backend_dir / "database"

    # Migrate both paper and live databases
    paper_db = database_dir / "alpaca_orders_paper.db"
    live_db = database_dir / "alpaca_orders_live.db"

    if paper_db.exists():
        migrate_database(paper_db)

    if live_db.exists():
        migrate_database(live_db)

    print("All migrations completed!")
