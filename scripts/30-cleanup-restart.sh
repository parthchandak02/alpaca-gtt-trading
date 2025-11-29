#!/bin/bash
# Cleanup and restart services
# Cleans up temporary files, Python caches, and restarts the backend service.
# Useful for clearing "zombie" connections or cached states.

echo "🧹 Starting system cleanup..."

# 1. Stop Backend Service
echo "🛑 Stopping backend..."
if command -v pm2 &> /dev/null; then
    pm2 stop alpaca-backend 2>/dev/null || echo "PM2 service not found, attempting kill..."
fi
pkill -f "uvicorn" || echo "No uvicorn processes found."

# 2. Clear Python Cache
echo "🗑️  Clearing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
echo "✅ Python cache cleared."

# 3. Clear Frontend Cache (Next.js)
if [ -d "frontend/.next" ]; then
    echo "🗑️  Clearing Next.js build cache..."
    rm -rf frontend/.next
    echo "✅ Frontend cache cleared."
fi

# 4. Restart Backend
echo "🚀 Restarting backend..."
if command -v pm2 &> /dev/null; then
    # Check if process exists in PM2
    if pm2 list | grep -q "alpaca-backend"; then
        pm2 restart alpaca-backend
    else
        echo "⚠️  'alpaca-backend' not found in PM2. Starting from script..."
        ./scripts/11-run-backend.sh
    fi
else
    echo "⚠️  PM2 not found. Starting backend manually in background..."
    ./scripts/11-run-backend.sh &
fi

echo "✅ System cleanup and restart complete!"
echo "👉 Please wait 30 seconds for the backend to fully initialize."

