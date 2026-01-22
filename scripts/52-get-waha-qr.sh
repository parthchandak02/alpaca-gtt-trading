#!/bin/bash
# Simple script to get WAHA QR code for scanning
# This creates/restarts the session and displays QR code info

# Don't exit on error - handle gracefully
set +e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

WAHA_URL="http://localhost:3001"
SESSION_NAME="default"

# Get API key from docker logs first (source of truth for running instance)
# Then fall back to .env if docker logs don't have it
echo -e "${YELLOW}📋 Extracting API key from WAHA logs...${NC}"
API_KEY=$(docker logs waha 2>&1 | grep "WAHA_API_KEY=" | head -1 | sed 's/.*WAHA_API_KEY=//' | tr -d ' ' || echo "")

if [ -z "$API_KEY" ]; then
    if [ -f ".env" ]; then
        echo -e "${YELLOW}📋 API key not in logs, checking .env...${NC}"
        API_KEY=$(grep "^WAHA_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || echo "")
    fi
fi

if [ -z "$API_KEY" ]; then
    # Try from alpaca-trader .env
    if [ -f "/Users/parthchandak/Documents/alpaca-trader/.env" ]; then
        API_KEY=$(grep "^WAHA_API_KEY=" /Users/parthchandak/Documents/alpaca-trader/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || echo "")
    fi
fi

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Could not find WAHA_API_KEY${NC}"
    echo -e "${YELLOW}   Check docker logs: docker logs waha${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 WAHA QR Code Setup${NC}"
echo "=========================================="
echo ""

# Step 1: Check current session status
echo -e "${YELLOW}📱 Step 1: Checking session status...${NC}"
STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
  -H "X-Api-Key: $API_KEY")

# Check if we got unauthorized
if echo "$STATUS_RESPONSE" | grep -q "Unauthorized"; then
    echo -e "${RED}❌ Unauthorized - API key may be incorrect${NC}"
    exit 1
fi

# Get current session status (use jq if available, otherwise python)
if command -v jq &> /dev/null; then
    CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "NOT_FOUND")
else
    CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else [data]
    session = next((s for s in sessions if s.get('name') == '$SESSION_NAME'), {})
    print(session.get('status', 'NOT_FOUND'))
except:
    print('NOT_FOUND')
" 2>/dev/null || echo "NOT_FOUND")
fi

echo -e "${YELLOW}   Current session status: $CURRENT_STATUS${NC}"

# Step 2: Handle session based on status
echo ""
echo -e "${YELLOW}📱 Step 2: Managing session...${NC}"

if [ "$CURRENT_STATUS" = "WORKING" ]; then
    echo -e "${GREEN}✅ Session is already WORKING - no QR code needed!${NC}"
    echo -e "${YELLOW}   Session is authenticated and ready to use${NC}"
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "1. Session is ready - you can send messages now"
    echo "2. Test: backend/.venv/bin/python scripts/54-test-whatsapp.py"
    exit 0
elif [ "$CURRENT_STATUS" = "SCAN_QR_CODE" ]; then
    echo -e "${GREEN}✅ Session is ready for QR code scan${NC}"
elif [ "$CURRENT_STATUS" = "FAILED" ] || [ "$CURRENT_STATUS" = "STOPPED" ]; then
    echo -e "${YELLOW}   Session is $CURRENT_STATUS - restarting...${NC}"
    # Stop session first if needed
    curl -s -X POST "$WAHA_URL/api/sessions/$SESSION_NAME/stop" \
      -H "X-Api-Key: $API_KEY" > /dev/null 2>&1
    sleep 2
    
    # Start session
    START_RESPONSE=$(curl -s -X POST "$WAHA_URL/api/sessions/$SESSION_NAME/start" \
      -H "X-Api-Key: $API_KEY")
    echo -e "${GREEN}✅ Session restarted${NC}"
elif [ "$CURRENT_STATUS" = "NOT_FOUND" ]; then
    echo -e "${YELLOW}   Session doesn't exist - creating...${NC}"
    CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WAHA_URL/api/sessions" \
      -H "Content-Type: application/json" \
      -H "X-Api-Key: $API_KEY" \
      -d "{\"name\": \"$SESSION_NAME\"}")
    
    HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -1)
    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Session created${NC}"
    else
        # Session might already exist, try to start it
        echo -e "${YELLOW}   Session may already exist, starting...${NC}"
        curl -s -X POST "$WAHA_URL/api/sessions/$SESSION_NAME/start" \
          -H "X-Api-Key: $API_KEY" > /dev/null 2>&1
    fi
else
    echo -e "${YELLOW}   Session status: $CURRENT_STATUS - ensuring it's started...${NC}"
    curl -s -X POST "$WAHA_URL/api/sessions/$SESSION_NAME/start" \
      -H "X-Api-Key: $API_KEY" > /dev/null 2>&1
fi

# Step 3: Wait for session to be in SCAN_QR_CODE state
echo ""
echo -e "${YELLOW}📱 Step 3: Waiting for session to be ready for QR code...${NC}"
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
      -H "X-Api-Key: $API_KEY")
    
    if command -v jq &> /dev/null; then
        CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "UNKNOWN")
    else
        CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else [data]
    session = next((s for s in sessions if s.get('name') == '$SESSION_NAME'), {})
    print(session.get('status', 'UNKNOWN'))
except:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
    fi
    
    if [ "$CURRENT_STATUS" = "SCAN_QR_CODE" ]; then
        echo -e "${GREEN}✅ Session is ready for QR code scan!${NC}"
        break
    elif [ "$CURRENT_STATUS" = "WORKING" ]; then
        echo -e "${GREEN}✅ Session is already WORKING - authenticated!${NC}"
        echo ""
        echo -e "${BLUE}📋 Next Steps:${NC}"
        echo "1. Session is ready - you can send messages now"
        echo "2. Test: backend/.venv/bin/python scripts/54-test-whatsapp.py"
        exit 0
    elif [ "$CURRENT_STATUS" = "STARTING" ]; then
        echo -ne "\r   Status: STARTING (waiting... ${WAITED}s) "
        sleep 2
        WAITED=$((WAITED + 2))
    else
        echo -ne "\r   Status: $CURRENT_STATUS (waiting... ${WAITED}s) "
        sleep 2
        WAITED=$((WAITED + 2))
    fi
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Timeout waiting for session to be ready${NC}"
    echo -e "${YELLOW}   Current status: $CURRENT_STATUS${NC}"
    echo -e "${YELLOW}   Check logs: docker logs waha${NC}"
fi

# Step 4: Get QR code (only if session is in SCAN_QR_CODE state)
echo ""
echo -e "${YELLOW}📱 Step 4: Getting QR code...${NC}"

# Check status one more time
STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
  -H "X-Api-Key: $API_KEY")
if command -v jq &> /dev/null; then
    FINAL_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "UNKNOWN")
else
    FINAL_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else [data]
    session = next((s for s in sessions if s.get('name') == '$SESSION_NAME'), {})
    print(session.get('status', 'UNKNOWN'))
except:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")
fi

if [ "$FINAL_STATUS" != "SCAN_QR_CODE" ]; then
    echo -e "${YELLOW}⚠️  Session status is '$FINAL_STATUS' - QR code may not be available${NC}"
    echo -e "${YELLOW}   Expected: SCAN_QR_CODE${NC}"
    echo ""
    echo -e "${YELLOW}💡 Troubleshooting:${NC}"
    echo "  1. Check session status: curl -s '$WAHA_URL/api/sessions' -H 'X-Api-Key: $API_KEY'"
    echo "  2. Check WAHA logs: docker logs waha"
    echo "  3. Try restarting session: ./scripts/51-setup-waha-session.sh"
    exit 1
fi

QR_RESPONSE=$(curl -s -X GET "$WAHA_URL/api/$SESSION_NAME/auth/qr" \
  -H "Accept: application/json" \
  -H "X-Api-Key: $API_KEY")

# Check response
if echo "$QR_RESPONSE" | grep -q '"data"'; then
    QR_DATA=$(echo "$QR_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data', ''))" 2>/dev/null || echo "")
    QR_MIME=$(echo "$QR_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('mimetype', ''))" 2>/dev/null || echo "")
    
    if [ -n "$QR_DATA" ] && [ "$QR_DATA" != "null" ] && [ ${#QR_DATA} -gt 100 ]; then
        echo -e "${GREEN}✅ QR Code received!${NC}"
        echo ""
        echo -e "${BLUE}📋 QR Code Information:${NC}"
        echo "   Format: $QR_MIME"
        echo "   Data length: ${#QR_DATA} characters (base64)"
        echo ""
        echo -e "${YELLOW}💡 How to view and scan the QR code:${NC}"
        echo ""
        echo -e "${GREEN}Option 1: Swagger UI (Easiest - Recommended)${NC}"
        echo "  1. Open: http://localhost:3001/"
        echo "  2. Click 'Authorize' button (top right)"
        echo "  3. Enter Swagger credentials (check docker logs if needed)"
        echo "  4. Find endpoint: GET /api/{session}/auth/qr"
        echo "  5. Click 'Try it out'"
        echo "  6. Enter session: $SESSION_NAME"
        echo "  7. Set 'Accept' header dropdown to 'application/json'"
        echo "  8. Click 'Execute'"
        echo "  9. Copy the 'data' field value"
        echo "  10. Use online tool to convert base64 to image:"
        echo "     https://base64.guru/converter/decode/image"
        echo "     OR use: echo '$QR_DATA' | base64 -d > qr.png"
        echo ""
        echo -e "${GREEN}Option 2: Save QR code directly${NC}"
        echo "  curl -s '$WAHA_URL/api/$SESSION_NAME/auth/qr' \\"
        echo "    -H 'X-Api-Key: $API_KEY' \\"
        echo "    -o qr-code.png"
        echo "  Then open qr-code.png and scan with WhatsApp"
        echo ""
        echo -e "${GREEN}Option 3: View in browser${NC}"
        echo "  Open: $WAHA_URL/api/$SESSION_NAME/auth/qr"
        echo "  (May require API key authentication)"
        echo ""
        
        # Save QR code to file
        echo -e "${YELLOW}💾 Saving QR code to qr-code.png...${NC}"
        curl -s "$WAHA_URL/api/$SESSION_NAME/auth/qr" \
          -H "X-Api-Key: $API_KEY" \
          -o qr-code.png 2>/dev/null && echo -e "${GREEN}✅ Saved to qr-code.png${NC}" || echo -e "${YELLOW}⚠️  Could not save (may need different endpoint)${NC}"
        echo ""
    else
        echo -e "${YELLOW}⚠️  QR code data is empty or invalid${NC}"
        echo "Response: $QR_RESPONSE" | head -5
    fi
else
    # Check if error is about session status
    if echo "$QR_RESPONSE" | grep -q "not as expected"; then
        echo -e "${YELLOW}⚠️  Session is not in SCAN_QR_CODE state${NC}"
        echo "Response: $QR_RESPONSE"
        echo ""
        echo -e "${YELLOW}💡 Current session status: $FINAL_STATUS${NC}"
        echo -e "${YELLOW}   If status is WORKING, session is already authenticated!${NC}"
        if [ "$FINAL_STATUS" = "WORKING" ]; then
            echo ""
            echo -e "${GREEN}✅ Session is already authenticated - no QR code needed!${NC}"
            echo -e "${BLUE}📋 Next Steps:${NC}"
            echo "1. Session is ready - you can send messages now"
            echo "2. Test: backend/.venv/bin/python scripts/54-test-whatsapp.py"
            exit 0
        fi
    else
        echo -e "${RED}❌ Could not get QR code${NC}"
        echo "Response: $QR_RESPONSE"
    fi
    echo ""
    echo -e "${YELLOW}💡 Troubleshooting:${NC}"
    echo "  1. Check session status: curl -s '$WAHA_URL/api/sessions' -H 'X-Api-Key: $API_KEY'"
    echo "  2. Check WAHA logs: docker logs waha"
    echo "  3. Try restarting session: ./scripts/51-setup-waha-session.sh"
    exit 1
fi

echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo "1. Scan QR code with your WhatsApp app"
echo "2. Wait for connection (session status will change to WORKING)"
echo "3. Test: backend/.venv/bin/python scripts/54-test-whatsapp.py"
echo ""

