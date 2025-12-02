#!/bin/bash
# Verify GTT system is ready for market open

echo "🔍 Verifying GTT System Readiness..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: Backend is running
echo "1. Checking if backend is running..."
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend is running"
else
    echo -e "${RED}✗${NC} Backend is NOT running (start with: ./scripts/run-backend.sh)"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: Alpaca connection
echo ""
echo "2. Checking Alpaca API connection..."
RESPONSE=$(curl -s http://localhost:8000/api/market-clock 2>&1)
if echo "$RESPONSE" | grep -q "is_open"; then
    echo -e "${GREEN}✓${NC} Alpaca API connection working"
    IS_OPEN=$(echo "$RESPONSE" | grep -o '"is_open":[^,]*' | cut -d: -f2)
    echo "   Market status: is_open=$IS_OPEN"
else
    echo -e "${RED}✗${NC} Cannot connect to Alpaca API"
    echo "   Response: $RESPONSE"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Database has GTT orders
echo ""
echo "3. Checking for active GTT orders..."
ORDERS=$(curl -s http://localhost:8000/api/gtt-orders 2>&1)
if echo "$ORDERS" | grep -q "\[\]"; then
    echo -e "${YELLOW}⚠${NC} No GTT orders found - create orders before market opens"
else
    ORDER_COUNT=$(echo "$ORDERS" | grep -o '"id":' | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} Found $ORDER_COUNT GTT order(s)"
fi

# Check 4: Price monitoring is active (check logs)
echo ""
echo "4. Checking price monitoring..."
if pgrep -f "python.*main.py" > /dev/null || pgrep -f "uvicorn.*main:app" > /dev/null; then
    echo -e "${GREEN}✓${NC} Backend process is running"
    echo "   Price monitoring should be active (checks every 60 seconds)"
else
    echo -e "${RED}✗${NC} Backend process not found"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Environment variables
echo ""
echo "5. Checking environment configuration..."
if [ -f "../.env" ]; then
    if grep -q "USE_PAPER_TRADING" ../.env; then
        PAPER_MODE=$(grep "USE_PAPER_TRADING" ../.env | cut -d= -f2)
        echo -e "${GREEN}✓${NC} Trading mode: $PAPER_MODE"
    else
        echo -e "${YELLOW}⚠${NC} USE_PAPER_TRADING not set in .env"
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file not found"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ System is ready for market open!${NC}"
    echo ""
    echo "The system will:"
    echo "  • Check prices every 60 seconds"
    echo "  • Automatically execute orders when trigger prices are met"
    echo "  • Update order statuses from Alpaca"
    echo ""
    echo "Monitor logs: tail -f logs/backend.log"
else
    echo -e "${RED}✗ System has $ERRORS issue(s) that need to be fixed${NC}"
    exit 1
fi

