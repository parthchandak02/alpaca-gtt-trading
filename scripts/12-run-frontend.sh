#!/bin/bash
# Run frontend development server
# Works for both dev mode and PM2 production mode

cd "$(dirname "$0")/../frontend"

# Detect if running under PM2 (for version file generation)
if [ -n "$PM2_HOME" ] || [ -n "$PM2_INSTANCE_ID" ]; then
    # Running under PM2 - generate version file
    echo "Generating version file..."
    ../scripts/34-generate-version.sh
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    pnpm install
fi

echo "🚀 Starting frontend dev server on http://localhost:3000"

# Use exec if running under PM2 (better process management)
if [ -n "$PM2_HOME" ] || [ -n "$PM2_INSTANCE_ID" ]; then
    exec pnpm run dev
else
    pnpm run dev
fi

