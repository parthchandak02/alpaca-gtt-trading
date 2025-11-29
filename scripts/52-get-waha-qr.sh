#!/bin/bash
# Simple script to get WAHA QR code for scanning
# This creates/restarts the session and displays QR code info

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

WAHA_URL="http://localhost:3001"
SESSION_NAME="default"

# Get API key from .env or docker logs
if [ -f ".env" ]; then
    API_KEY=$(grep "^WAHA_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr -d ' ' || echo "")
fi

if [ -z "$API_KEY" ]; then
    echo -e "${YELLOW}📋 Extracting API key from WAHA logs...${NC}"
    API_KEY=$(docker logs waha 2>&1 | grep "WAHA_API_KEY=" | head -1 | sed 's/.*WAHA_API_KEY=//' | tr -d ' ' || echo "")
fi

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Could not find WAHA_API_KEY${NC}"
    echo -e "${YELLOW}   Check docker logs: docker logs waha${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 WAHA QR Code Setup${NC}"
echo "=========================================="
echo ""

# Step 1: Create/restart session
echo -e "${YELLOW}📱 Step 1: Creating/restarting session '$SESSION_NAME'...${NC}"
CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WAHA_URL/api/sessions" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $API_KEY" \
  -d "{\"name\": \"$SESSION_NAME\"}")

HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -1)
BODY=$(echo "$CREATE_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Session created/updated (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}⚠️  Unexpected response: HTTP $HTTP_CODE${NC}"
    echo "$BODY"
fi

# Step 2: Wait for session to initialize
echo ""
echo -e "${YELLOW}📱 Step 2: Waiting for session to initialize (10 seconds)...${NC}"
for i in {10..1}; do
    echo -ne "\r   ${i}s remaining... "
    sleep 1
done
echo -e "\r   ✅ Ready!                    "

# Step 3: Get QR code
echo ""
echo -e "${YELLOW}📱 Step 3: Getting QR code...${NC}"
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
    echo -e "${RED}❌ Could not get QR code${NC}"
    echo "Response: $QR_RESPONSE"
    echo ""
    echo -e "${YELLOW}💡 Troubleshooting:${NC}"
    echo "  1. Check session status: curl -s '$WAHA_URL/api/sessions?all=true' -H 'X-Api-Key: $API_KEY'"
    echo "  2. Check WAHA logs: docker logs waha"
    echo "  3. Try restarting session: ./scripts/51-setup-waha-session.sh"
fi

echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo "1. Scan QR code with your WhatsApp app"
echo "2. Wait for connection (session status will change to WORKING)"
echo "3. Test: backend/.venv/bin/python scripts/54-test-whatsapp.py"
echo ""

