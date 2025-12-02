#!/bin/bash
# Run frontend development server

cd "$(dirname "$0")/../frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

echo "🚀 Starting frontend dev server on http://localhost:3000"
npm run dev

