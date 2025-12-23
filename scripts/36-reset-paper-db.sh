#!/bin/bash
# Reset paper trading database - deletes and reinitializes from scratch

set -e

BACKEND_DIR="/Users/parthchandak/Documents/alpaca-trader/backend"
PAPER_DB="$BACKEND_DIR/database/alpaca_orders_paper.db"

echo "🗑️  Resetting paper trading database..."

if [ -f "$PAPER_DB" ]; then
    echo "📦 Backing up existing database to alpaca_orders_paper.db.backup"
    cp "$PAPER_DB" "${PAPER_DB}.backup"
    
    echo "🔥 Deleting paper database..."
    rm "$PAPER_DB"
    echo "✅ Paper database deleted"
else
    echo "ℹ️  No paper database found (already empty)"
fi

echo ""
echo "🔄 Database will be recreated automatically on next backend start"
echo ""
echo "💡 To restore from backup if needed:"
echo "   cp $BACKEND_DIR/database/alpaca_orders_paper.db.backup $PAPER_DB"
echo ""
echo "✨ Paper database reset complete!"

