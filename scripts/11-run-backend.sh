#!/bin/bash
# Run backend server
# Works for both dev mode and PM2 production mode

cd "$(dirname "$0")/../backend"

# Detect if running under PM2 (for version file generation)
if [ -n "$PM2_HOME" ] || [ -n "$PM2_INSTANCE_ID" ]; then
    # Running under PM2 - generate version file
    echo "Generating version file..."
    ../scripts/34-generate-version.sh
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "../.venv" ]; then
    source ../.venv/bin/activate
fi

# Check if .env exists (only warn in dev mode)
if [ -z "$PM2_HOME" ] && [ -z "$PM2_INSTANCE_ID" ]; then
    if [ ! -f "../.env" ]; then
        echo "⚠️  Warning: .env file not found. Make sure to configure your Alpaca API keys."
    fi
fi

echo "🚀 Starting backend server on http://localhost:8000"

# Use exec if running under PM2 (better process management)
if [ -n "$PM2_HOME" ] || [ -n "$PM2_INSTANCE_ID" ]; then
    exec python3 main.py
else
    python3 main.py
fi

