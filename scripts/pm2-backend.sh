#!/bin/bash
# PM2 wrapper script for backend

cd "$(dirname "$0")/../backend"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "../.venv" ]; then
    source ../.venv/bin/activate
fi

# Run the server
exec python3 main.py

