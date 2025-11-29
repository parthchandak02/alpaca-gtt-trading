"""Database migration script to separate paper and live trading databases.

This script helps migrate existing data from the old single database
(alpaca_orders.db) to the new separate databases (alpaca_orders_paper.db
and alpaca_orders_live.db).

Usage:
    python migrate_database.py [--mode paper|live|both]

If no mode is specified, it will migrate to paper trading database by default.
"""

import argparse
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database(mode: str = "paper"):
    """Migrate existing database to separate paper/live databases.

    Args:
        mode: 'paper', 'live', or 'both'
    """
    backend_dir = Path(__file__).parent
    database_dir = backend_dir / "database"
    database_dir.mkdir(exist_ok=True)  # Ensure database directory exists

    old_db = backend_dir / "alpaca_orders.db"

    if not old_db.exists():
        logger.info(
            "No existing database found. New databases will be created on first run."
        )
        return

    logger.info(f"Found existing database: {old_db}")

    if mode in ["paper", "both"]:
        paper_db = database_dir / "alpaca_orders_paper.db"
        if paper_db.exists():
            logger.warning(f"Paper database already exists: {paper_db}")
            response = input("Overwrite existing paper database? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Skipping paper database migration.")
            else:
                shutil.copy2(old_db, paper_db)
                logger.info(f"✅ Migrated to paper database: {paper_db}")
        else:
            shutil.copy2(old_db, paper_db)
            logger.info(f"✅ Migrated to paper database: {paper_db}")

    if mode in ["live", "both"]:
        live_db = database_dir / "alpaca_orders_live.db"
        if live_db.exists():
            logger.warning(f"Live database already exists: {live_db}")
            response = input("Overwrite existing live database? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Skipping live database migration.")
            else:
                shutil.copy2(old_db, live_db)
                logger.info(f"✅ Migrated to live database: {live_db}")
        else:
            shutil.copy2(old_db, live_db)
            logger.info(f"✅ Migrated to live database: {live_db}")

    logger.info("\n⚠️  IMPORTANT:")
    logger.info(
        "1. The old database (alpaca_orders.db) has been copied to the new databases."
    )
    logger.info(
        "2. Review the migrated data to ensure it's correct for each trading mode."
    )
    logger.info(
        "3. Once verified, you can optionally backup and remove the old database."
    )
    logger.info("4. The old database will NOT be automatically deleted for safety.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate existing database to separate paper/live databases"
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "live", "both"],
        default="paper",
        help="Which database(s) to migrate to (default: paper)",
    )

    args = parser.parse_args()
    migrate_database(args.mode)
