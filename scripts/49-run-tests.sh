#!/bin/bash
# GTT Order System - Automated Test Suite
# Run this script to verify all functionality before production deployment

set -e  # Exit on error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}GTT Order System - Test Suite${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Test counter
PASSED=0
FAILED=0

# Helper function to run test
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    echo -e "${YELLOW}Testing:${NC} $test_name"
    
    if eval "$test_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
    fi
    echo ""
}

echo -e "${BLUE}=== Phase 1: Backend Connectivity ===${NC}"
echo ""

run_test "Backend is running" "curl -s http://localhost:8000/api/account/info > /dev/null"
run_test "Frontend is running" "curl -s http://localhost:3000 > /dev/null"

echo -e "${BLUE}=== Phase 2: Database Tests ===${NC}"
echo ""

# Check if database exists
if [ -f "backend/database/alpaca_orders_paper.db" ]; then
    echo -e "${GREEN}✓${NC} Database file exists"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} Database file missing"
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}=== Phase 3: Manual Testing Instructions ===${NC}"
echo ""
echo -e "${YELLOW}Please perform the following manual tests in the browser:${NC}"
echo ""
echo "1. Frontend URL: http://localhost:3000/gtt"
echo "2. Click 'Add GTT Order'"
echo "3. Test IVDA (whole shares):"
echo "   - Symbol: IVDA"
echo "   - Qty: 1"
echo "   - Price: 25.95"
echo "   - Increment: 1.2"
echo "   - Decrement: 0.9"
echo "   - Iterations: 5"
echo "   ✓ Check: Preview shows rounding (1.2 → 1, 1.44 → 1, etc.)"
echo "   ✓ Check: TIF badges show GTC (green)"
echo ""
echo "4. Test TSLA (fractional):"
echo "   - Symbol: TSLA"
echo "   - Qty: 0.5"
echo "   - Price: 350"
echo "   - Increment: 1.5"
echo "   - Decrement: 0.95"
echo "   - Iterations: 3"
echo "   ✓ Check: No rounding warnings"
echo "   ✓ Check: TIF badges show DAY (yellow) for fractional"
echo ""
echo "5. Test CSV Upload:"
echo "   - Upload: templates/gtt_template.csv"
echo "   ✓ Check: Shows rounding warnings"
echo "   ✓ Check: TIF calculated correctly"
echo ""

echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo -e "Automated tests passed: ${GREEN}$PASSED${NC}"
echo -e "Automated tests failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All automated tests passed!${NC}"
    echo -e "${YELLOW}⚠ Please complete manual tests above before deploying.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix issues before deploying.${NC}"
    exit 1
fi

