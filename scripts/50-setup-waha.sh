#!/bin/bash
# Setup script for WAHA (WhatsApp HTTP API) Docker container
# This script downloads and starts the WAHA Docker container

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${GREEN}🚀 WAHA (WhatsApp HTTP API) Setup${NC}"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✅ Docker found${NC}"

# Check if WAHA container is already running
if docker ps --format '{{.Names}}' | grep -q "^waha$"; then
    echo -e "${YELLOW}⚠️  WAHA container is already running${NC}"
    echo -e "${YELLOW}   Container name: waha${NC}"
    echo ""
    echo -e "${GREEN}✅ WAHA is ready!${NC}"
    echo -e "${YELLOW}   API URL: http://localhost:3000${NC}"
    echo -e "${YELLOW}   Swagger UI: http://localhost:3000/${NC}"
    echo ""
    echo -e "${YELLOW}To stop WAHA: docker stop waha${NC}"
    echo -e "${YELLOW}To restart WAHA: docker restart waha${NC}"
    exit 0
fi

# Check if WAHA container exists but is stopped
if docker ps -a --format '{{.Names}}' | grep -q "^waha$"; then
    echo -e "${YELLOW}📦 WAHA container exists but is stopped. Starting it...${NC}"
    docker start waha
    echo -e "${GREEN}✅ WAHA container started${NC}"
    echo ""
    echo -e "${GREEN}✅ WAHA is ready!${NC}"
    echo -e "${YELLOW}   API URL: http://localhost:3000${NC}"
    echo -e "${YELLOW}   Swagger UI: http://localhost:3000/${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next Steps:${NC}"
    echo "1. Open Swagger UI: http://localhost:3000/"
    echo "2. Start a session: POST /api/sessions with name 'default'"
    echo "3. Get QR code: GET /api/screenshot"
    echo "4. Scan QR code with your WhatsApp app"
    exit 0
fi

# Detect architecture (ARM vs x86)
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]] || [[ "$ARCH" == "aarch64" ]]; then
    echo -e "${YELLOW}📦 Detected ARM architecture (Apple Silicon/M1/M2)${NC}"
    WAHA_IMAGE="devlikeapro/waha:arm"
else
    echo -e "${YELLOW}📦 Detected x86_64 architecture${NC}"
    WAHA_IMAGE="devlikeapro/waha"
fi

# Pull WAHA Docker image
echo -e "${YELLOW}📥 Downloading WAHA Docker image...${NC}"
docker pull "$WAHA_IMAGE"

# If ARM, tag it for easier use
if [[ "$ARCH" == "arm64" ]] || [[ "$ARCH" == "aarch64" ]]; then
    docker tag "$WAHA_IMAGE" devlikeapro/waha
    echo -e "${GREEN}✅ Tagged ARM image as devlikeapro/waha${NC}"
fi

# Create data directory for WAHA sessions (persists across restarts)
WAHA_DATA_DIR="$PROJECT_ROOT/waha-data"
mkdir -p "$WAHA_DATA_DIR"

# Use port 3001 for WAHA (3000 is used by frontend)
WAHA_PORT=3001

# Check if port 3001 is available
if lsof -i :$WAHA_PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $WAHA_PORT is already in use${NC}"
    echo -e "${YELLOW}   Checking if WAHA container is already running...${NC}"
    
    # Check if WAHA container exists and is running
    if docker ps --format '{{.Names}}' | grep -q "^waha$"; then
        ACTUAL_PORT=$(docker port waha 2>/dev/null | grep -oP ':\K[0-9]+' | head -1 || echo "$WAHA_PORT")
        echo -e "${GREEN}✅ WAHA container is already running${NC}"
        echo -e "${YELLOW}   Update WAHA_API_URL in .env to: http://localhost:$ACTUAL_PORT${NC}"
        exit 0
    else
        echo -e "${RED}❌ Port $WAHA_PORT is in use by another service${NC}"
        echo -e "${YELLOW}   Please stop the service using port $WAHA_PORT or choose a different port${NC}"
        exit 1
    fi
fi

# Run WAHA container on port 3001
echo -e "${YELLOW}🚀 Starting WAHA container on port $WAHA_PORT...${NC}"
docker run -d \
  --name waha \
  --restart unless-stopped \
  -p $WAHA_PORT:3000 \
  -v "$WAHA_DATA_DIR:/app/.sessions" \
  -e WHATSAPP_HOOK_URL=http://localhost:5000/bot \
  -e "WHATSAPP_HOOK_EVENTS=*" \
  devlikeapro/waha

echo -e "${GREEN}✅ WAHA container started on port $WAHA_PORT${NC}"
echo -e "${YELLOW}   Note: WAHA runs on port $WAHA_PORT (not 3000) to avoid conflict with frontend${NC}"
echo ""
echo -e "${YELLOW}⏳ Waiting for WAHA to start (5 seconds)...${NC}"
sleep 5

# Extract credentials from logs
echo -e "${YELLOW}📋 Extracting WAHA credentials from logs...${NC}"
WAHA_CREDS=$(docker logs waha 2>&1 | grep -A 10 "Generated credentials" | grep "WAHA_API_KEY=" | head -1 | sed 's/WAHA_API_KEY=//' | tr -d ' ')
SWAGGER_USER=$(docker logs waha 2>&1 | grep "WHATSAPP_SWAGGER_USERNAME=" | head -1 | sed 's/WHATSAPP_SWAGGER_USERNAME=//' | tr -d ' ')
SWAGGER_PASS=$(docker logs waha 2>&1 | grep "WHATSAPP_SWAGGER_PASSWORD=" | head -1 | sed 's/WHATSAPP_SWAGGER_PASSWORD=//' | tr -d ' ')

if [ -n "$WAHA_CREDS" ]; then
    echo -e "${GREEN}✅ Credentials extracted${NC}"
    echo ""
    echo -e "${YELLOW}🔑 WAHA Credentials:${NC}"
    echo "   API Key: $WAHA_CREDS"
    echo "   Swagger Username: ${SWAGGER_USER:-admin}"
    echo "   Swagger Password: ${SWAGGER_PASS:-check logs}"
else
    echo -e "${YELLOW}⚠️  Could not extract credentials from logs${NC}"
    echo -e "${YELLOW}   Check logs manually: docker logs waha${NC}"
fi

echo -e "${GREEN}✅ WAHA container started successfully!${NC}"
echo ""
echo -e "${GREEN}🎉 WAHA is ready!${NC}"
echo ""
echo -e "${YELLOW}📋 Configuration:${NC}"
echo "   Container name: waha"
echo "   API URL: http://localhost:$WAHA_PORT"
echo "   Swagger UI: http://localhost:$WAHA_PORT/"
echo "   Data directory: $WAHA_DATA_DIR"
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "1. Add to .env file:"
echo "   WHATSAPP_ENABLED=true"
echo "   WHATSAPP_PHONE_NUMBER=12132132130  # Your phone (digits only)"
echo "   WAHA_API_URL=http://localhost:$WAHA_PORT"
echo "   WAHA_SESSION_NAME=default"
echo ""
echo "2. Open Swagger UI in your browser: http://localhost:$WAHA_PORT/"
echo "2. Start a session:"
echo "   - Find 'POST /api/sessions' endpoint"
echo "   - Click 'Try it out'"
echo "   - Use session name: 'default'"
echo "   - Click 'Execute'"
echo "3. Get QR code:"
echo "   - Find 'GET /api/screenshot' endpoint"
echo "   - Click 'Try it out' and 'Execute'"
echo "   - Scan the QR code with your WhatsApp app"
echo "4. Verify connection:"
echo "   - Execute 'GET /api/screenshot' again"
echo "   - Should show WhatsApp Web interface (not QR code)"
echo ""
echo -e "${YELLOW}💡 Useful Commands:${NC}"
echo "   View logs: docker logs -f waha"
echo "   Stop WAHA: docker stop waha"
echo "   Start WAHA: docker start waha"
echo "   Restart WAHA: docker restart waha"
echo "   Remove WAHA: docker rm -f waha"
echo ""

