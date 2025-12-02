#!/bin/bash
# Run backend server

cd "$(dirname "$0")/../backend"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "../.venv" ]; then
    source ../.venv/bin/activate
fi

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "⚠️  Warning: .env file not found. Make sure to configure your Alpaca API keys."
fi

echo "🚀 Starting backend server on http://localhost:8000"
python3 main.py

