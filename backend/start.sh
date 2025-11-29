#!/bin/bash
# Startup script for the backend server

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the server
python3 main.py

