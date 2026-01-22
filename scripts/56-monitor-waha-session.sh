#!/bin/bash
# Monitor WAHA session status and notify when it becomes WORKING
# This helps you know when QR code scan is successful

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

WAHA_URL="http://localhost:3001"
SESSION_NAME="default"

# Get API key
if [ -f "/Users/parthchandak/Documents/alpaca-trader/.env" ]; then
    API_KEY=$(grep "^WAHA_API_KEY=" /Users/parthchandak/Documents/alpaca-trader/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || echo "")
elif [ -f ".env" ]; then
    API_KEY=$(grep "^WAHA_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || echo "")
fi

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Could not find WAHA_API_KEY${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Monitoring WAHA Session Status${NC}"
echo "=========================================="
echo -e "${YELLOW}Session: $SESSION_NAME${NC}"
echo -e "${YELLOW}Checking every 3 seconds...${NC}"
echo ""

PREVIOUS_STATUS=""
CHECK_COUNT=0

while true; do
    CHECK_COUNT=$((CHECK_COUNT + 1))
    
    STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
      -H "X-Api-Key: $API_KEY" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Could not connect to WAHA API${NC}"
        sleep 3
        continue
    fi
    
    CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$CURRENT_STATUS" != "$PREVIOUS_STATUS" ]; then
        case "$CURRENT_STATUS" in
            "WORKING")
                echo -e "${GREEN}✅✅✅ SESSION IS NOW WORKING! ✅✅✅${NC}"
                echo -e "${GREEN}   WhatsApp is authenticated and ready to send messages!${NC}"
                echo ""
                echo -e "${BLUE}📋 Next Steps:${NC}"
                echo "1. Test sending a message:"
                echo "   cd /Users/parthchandak/Documents/alpaca-trader"
                echo "   backend/.venv/bin/python scripts/54-test-whatsapp.py"
                echo ""
                echo "2. Your WhatsApp notifications should now work!"
                echo ""
                exit 0
                ;;
            "SCAN_QR_CODE")
                echo -e "${YELLOW}📱 Status: SCAN_QR_CODE${NC}"
                echo -e "${YELLOW}   Waiting for QR code scan...${NC}"
                echo -e "${YELLOW}   Scan the QR code with your WhatsApp app${NC}"
                ;;
            "STARTING")
                echo -e "${YELLOW}⏳ Status: STARTING${NC}"
                echo -e "${YELLOW}   Session is initializing...${NC}"
                ;;
            "FAILED")
                echo -e "${RED}❌ Status: FAILED${NC}"
                echo -e "${RED}   Session failed. You may need to restart it.${NC}"
                ;;
            "STOPPED")
                echo -e "${YELLOW}⏸️  Status: STOPPED${NC}"
                echo -e "${YELLOW}   Session is stopped.${NC}"
                ;;
            *)
                echo -e "${YELLOW}⚠️  Status: $CURRENT_STATUS${NC}"
                ;;
        esac
        PREVIOUS_STATUS="$CURRENT_STATUS"
    else
        # Show progress every 10 checks (30 seconds)
        if [ $((CHECK_COUNT % 10)) -eq 0 ]; then
            echo -e "${BLUE}   Still waiting... (${CHECK_COUNT} checks, ~$((CHECK_COUNT * 3))s)${NC}"
        fi
    fi
    
    sleep 3
done
