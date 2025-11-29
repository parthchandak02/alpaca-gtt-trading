#!/bin/bash
# Run both backend and frontend in parallel

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Alpaca GTT Order Tracker${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend in background
echo -e "${GREEN}Starting backend...${NC}"
"$SCRIPT_DIR/11-run-backend.sh" &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo -e "${GREEN}Starting frontend...${NC}"
"$SCRIPT_DIR/12-run-frontend.sh" &
FRONTEND_PID=$!

echo ""
echo -e "${BLUE}✅ Servers started!${NC}"
echo -e "${GREEN}Backend:${NC} http://localhost:8000"
echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait

