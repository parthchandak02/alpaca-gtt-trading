"""Migration: Add AlpacaOrderCache table and remove duplicated Alpaca data from GTTOrderDetail."""
import sqlite3
import os
from pathlib import Path

def migrate():
    """Add AlpacaOrderCache table and remove status/timestamps from GTTOrderDetail."""
    # Get database path based on environment
    backend_dir = Path(__file__).parent.parent
    database_dir = backend_dir / "database"
    
    # Check which database exists (paper or live)
    use_paper = os.getenv("USE_PAPER_TRADING", "true").lower() == "true"
    if use_paper:
        db_path = database_dir / "alpaca_orders_paper.db"
    else:
        db_path = database_dir / "alpaca_orders_live.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print(f"Trying alternative location...")
        # Try the other database
        if use_paper:
            db_path = database_dir / "alpaca_orders_live.db"
        else:
            db_path = database_dir / "alpaca_orders_paper.db"
        
        if not db_path.exists():
            print(f"Database not found at {db_path}")
            return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 1. Create AlpacaOrderCache table
        print("Creating AlpacaOrderCache table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpaca_order_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alpaca_order_id VARCHAR NOT NULL UNIQUE,
                status VARCHAR,
                submitted_at DATETIME,
                filled_at DATETIME,
                expired_at DATETIME,
                filled_qty FLOAT,
                filled_avg_price FLOAT,
                cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_alpaca_order_cache_alpaca_order_id ON alpaca_order_cache(alpaca_order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_alpaca_order_cache_cached_at ON alpaca_order_cache(cached_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_alpaca_order_cache_last_fetched_at ON alpaca_order_cache(last_fetched_at)")
        
        # 2. Migrate existing data from GTTOrderDetail to AlpacaOrderCache
        print("Migrating existing Alpaca order data to cache...")
        cursor.execute("""
            INSERT OR IGNORE INTO alpaca_order_cache (
                alpaca_order_id, status, submitted_at, filled_at, expired_at
            )
            SELECT 
                alpaca_order_id,
                status,
                submitted_at,
                filled_at,
                expired_at
            FROM gtt_order_details
            WHERE alpaca_order_id IS NOT NULL
        """)
        
        # 3. Remove columns from GTTOrderDetail (SQLite doesn't support DROP COLUMN directly)
        # We'll need to recreate the table
        print("Removing duplicated columns from GTTOrderDetail...")
        
        # Get all data from gtt_order_details
        cursor.execute("SELECT * FROM gtt_order_details")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        # Create new table without status/timestamps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gtt_order_details_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gtt_order_id INTEGER NOT NULL,
                order_index INTEGER NOT NULL,
                trigger_price FLOAT NOT NULL,
                quantity INTEGER NOT NULL,
                fractional_quantity FLOAT,
                limit_price FLOAT NOT NULL,
                amount FLOAT NOT NULL,
                alpaca_order_id VARCHAR,
                is_manually_linked BOOLEAN DEFAULT 0,
                time_in_force VARCHAR DEFAULT 'DAY',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gtt_order_id) REFERENCES gtt_orders(id)
            )
        """)
        
        # Copy data (excluding status, submitted_at, filled_at, expired_at)
        if rows:
            for row in rows:
                row_dict = dict(zip(columns, row))
                cursor.execute("""
                    INSERT INTO gtt_order_details_new (
                        id, gtt_order_id, order_index, trigger_price, quantity,
                        fractional_quantity, limit_price, amount, alpaca_order_id,
                        is_manually_linked, time_in_force, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get('id'),
                    row_dict.get('gtt_order_id'),
                    row_dict.get('order_index'),
                    row_dict.get('trigger_price'),
                    row_dict.get('quantity'),
                    row_dict.get('fractional_quantity'),
                    row_dict.get('limit_price'),
                    row_dict.get('amount'),
                    row_dict.get('alpaca_order_id'),
                    row_dict.get('is_manually_linked', 0),
                    row_dict.get('time_in_force', 'DAY'),
                    row_dict.get('created_at'),
                    row_dict.get('updated_at')
                ))
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE gtt_order_details")
        cursor.execute("ALTER TABLE gtt_order_details_new RENAME TO gtt_order_details")
        
        # Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_gtt_order_details_gtt_order_id ON gtt_order_details(gtt_order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_gtt_order_details_alpaca_order_id ON gtt_order_details(alpaca_order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_gtt_order_details_is_manually_linked ON gtt_order_details(is_manually_linked)")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

