#!/bin/bash
# Helper script to start WAHA session and get QR code
# This script helps you start a WhatsApp session and scan the QR code

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
        API_KEY=$(grep "^WAHA_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "")
    fi
fi

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Could not find WAHA_API_KEY${NC}"
    echo -e "${YELLOW}   Check docker logs: docker logs waha${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 WAHA Session Setup${NC}"
echo "=========================================="
echo -e "${YELLOW}WAHA URL: $WAHA_URL${NC}"
echo -e "${YELLOW}Session: $SESSION_NAME${NC}"
echo ""

# Step 1: Check session status
echo -e "${YELLOW}📱 Step 1: Checking session status...${NC}"
STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
  -H "X-Api-Key: $API_KEY")

# Check if we got unauthorized
if echo "$STATUS_RESPONSE" | grep -q "Unauthorized"; then
    echo -e "${RED}❌ Unauthorized - API key may be incorrect${NC}"
    echo -e "${YELLOW}   Current API key: ${API_KEY:0:10}...${NC}"
    echo -e "${YELLOW}   Get new key: docker logs waha | grep WAHA_API_KEY${NC}"
    exit 1
fi

SESSION_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "unknown")

if [ -z "$SESSION_STATUS" ] || [ "$SESSION_STATUS" = "null" ] || [ "$SESSION_STATUS" = "unknown" ]; then
    echo -e "${YELLOW}   Session doesn't exist, creating it...${NC}"
    CREATE_RESPONSE=$(curl -s -X POST "$WAHA_URL/api/sessions" \
      -H "Content-Type: application/json" \
      -H "X-Api-Key: $API_KEY" \
      -d "{\"name\": \"$SESSION_NAME\"}")
    
    # Check if creation failed due to existing session
    if echo "$CREATE_RESPONSE" | grep -q "already exists"; then
        echo -e "${GREEN}✅ Session already exists${NC}"
    elif echo "$CREATE_RESPONSE" | grep -q "Unauthorized"; then
        echo -e "${RED}❌ Unauthorized during session creation${NC}"
        exit 1
    fi
    sleep 2
fi

# Step 2: Start session if stopped
echo -e "${YELLOW}📱 Step 2: Starting session '$SESSION_NAME'...${NC}"
START_RESPONSE=$(curl -s -X POST "$WAHA_URL/api/sessions/$SESSION_NAME/start" \
  -H "X-Api-Key: $API_KEY")

# Check for errors
if echo "$START_RESPONSE" | grep -q "Unauthorized"; then
    echo -e "${RED}❌ Unauthorized - API key may be incorrect${NC}"
    echo -e "${YELLOW}   Current API key: ${API_KEY:0:10}...${NC}"
    echo -e "${YELLOW}   Get new key: docker logs waha | grep WAHA_API_KEY${NC}"
    exit 1
elif echo "$START_RESPONSE" | grep -q "already started"; then
    echo -e "${GREEN}✅ Session is already started${NC}"
else
    echo "$START_RESPONSE" | jq '.' 2>/dev/null || echo "$START_RESPONSE"
fi
echo ""

# Wait a moment for session to initialize
echo -e "${YELLOW}   Waiting for session to initialize...${NC}"
sleep 3

# Step 3: Wait for session to be ready for QR code
echo -e "${YELLOW}📱 Step 3: Waiting for session to be ready...${NC}"
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
      -H "X-Api-Key: $API_KEY")
    CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "unknown")
    
    if [ "$CURRENT_STATUS" = "SCAN_QR_CODE" ] || [ "$CURRENT_STATUS" = "WORKING" ]; then
        echo -e "${GREEN}✅ Session status: $CURRENT_STATUS${NC}"
        break
    elif [ "$CURRENT_STATUS" = "STARTING" ]; then
        echo -e "${YELLOW}   Status: STARTING (waiting... ${WAITED}s)${NC}"
        sleep 2
        WAITED=$((WAITED + 2))
    else
        echo -e "${YELLOW}   Status: $CURRENT_STATUS${NC}"
        sleep 2
        WAITED=$((WAITED + 2))
    fi
done

# Step 4: Get QR code (only if session needs authentication)
echo -e "${YELLOW}📱 Step 4: Checking if QR code is needed...${NC}"
if [ "$SESSION_STATUS" = "SCAN_QR_CODE" ]; then
    QR_RESPONSE=$(curl -s "$WAHA_URL/api/$SESSION_NAME/auth/qr" \
      -H "Accept: application/json" \
      -H "X-Api-Key: $API_KEY")

    # Check if we got QR code data
    if echo "$QR_RESPONSE" | grep -q '"data"'; then
        QR_DATA=$(echo "$QR_RESPONSE" | jq -r '.data' 2>/dev/null)
        if [ -n "$QR_DATA" ] && [ "$QR_DATA" != "null" ]; then
        echo -e "${GREEN}✅ QR code received!${NC}"
        echo ""
        echo -e "${YELLOW}📋 To view and scan QR code:${NC}"
        echo ""
        echo "Option 1: Use Swagger UI (Recommended):"
        echo "  1. Open: http://localhost:3001/"
        echo "  2. Login with credentials from docker logs"
        echo "  3. Find 'GET /api/{session}/auth/qr' endpoint"
        echo "  4. Enter session: '$SESSION_NAME'"
        echo "  5. Set 'Accept' header to 'application/json'"
        echo "  6. Click 'Try it out' → 'Execute'"
        echo "  7. Copy the 'data' field value (base64 image)"
        echo "  8. Convert base64 to image or use online tool"
        echo ""
echo "Option 2: Direct API call (save to file):"
    echo "  curl -s '$WAHA_URL/api/$SESSION_NAME/auth/qr' \\"
    echo "    -H 'X-Api-Key: $API_KEY' \\"
    echo "    -o qr-code.png"
    echo ""
    echo "Option 3: View in browser (binary image):"
    echo "  Open: $WAHA_URL/api/$SESSION_NAME/auth/qr"
    echo ""
    echo "Option 4: Use Swagger UI (Easiest):"
    echo "  1. Open: http://localhost:3001/"
    echo "  2. Login with credentials"
    echo "  3. Find 'GET /api/{session}/auth/qr'"
    echo "  4. Enter session: '$SESSION_NAME'"
    echo "  5. Set Accept header to 'application/json'"
    echo "  6. Click 'Try it out' → 'Execute'"
    echo "  7. Copy the 'data' field (base64) and convert to image"
            echo ""
        else
            echo -e "${YELLOW}⚠️  QR code not ready yet. Session may still be starting...${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Could not get QR code. Response:${NC}"
        echo "$QR_RESPONSE" | head -5
        echo ""
    fi
else
    echo -e "${GREEN}✅ Session is already authenticated - no QR code needed!${NC}"
fi

# Step 5: Check session status
echo -e "${YELLOW}📱 Step 5: Checking session status...${NC}"
STATUS_RESPONSE=$(curl -s "$WAHA_URL/api/sessions" \
  -H "X-Api-Key: $API_KEY")

SESSION_STATUS=$(echo "$STATUS_RESPONSE" | jq -r ".[] | select(.name==\"$SESSION_NAME\") | .status" 2>/dev/null || echo "unknown")

echo -e "${YELLOW}   Session status: $SESSION_STATUS${NC}"

if [ "$SESSION_STATUS" = "SCAN_QR_CODE" ]; then
    echo -e "${GREEN}✅ Session is ready for QR scan!${NC}"
    echo -e "${YELLOW}   Scan the QR code with your WhatsApp app${NC}"
elif [ "$SESSION_STATUS" = "WORKING" ]; then
    echo -e "${GREEN}✅ Session is WORKING! You're all set!${NC}"
elif [ "$SESSION_STATUS" = "STARTING" ]; then
    echo -e "${YELLOW}⏳ Session is STARTING. Wait a few seconds and check QR code again.${NC}"
elif [ "$SESSION_STATUS" = "STOPPED" ]; then
    echo -e "${RED}❌ Session is STOPPED. Try running this script again.${NC}"
else
    echo -e "${YELLOW}⚠️  Session status: $SESSION_STATUS${NC}"
fi

echo ""
echo -e "${GREEN}📋 Next Steps:${NC}"
echo "1. Scan QR code with your WhatsApp app"
echo "2. Wait a few seconds for connection"
echo "3. Run test script: backend/.venv/bin/python scripts/54-test-whatsapp.py"
echo ""

