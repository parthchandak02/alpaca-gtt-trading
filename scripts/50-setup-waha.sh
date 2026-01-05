#!/bin/bash
# Setup script for WAHA (WhatsApp HTTP API) - Now uses shared WAHA instance
# WAHA is managed independently at /Users/parthchandak/Documents/waha

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

WAHA_DIR="/Users/parthchandak/Documents/waha"
WAHA_PORT=3001

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
    echo -e "${GREEN}✅ WAHA container is already running${NC}"
    echo ""
    echo -e "${YELLOW}📋 WAHA Information:${NC}"
    echo "   Container name: waha"
    echo "   API URL: http://localhost:$WAHA_PORT"
    echo "   Swagger UI: http://localhost:$WAHA_PORT/"
    echo "   Location: $WAHA_DIR"
    echo ""
    
    # Extract API key from logs
    WAHA_CREDS=$(docker logs waha 2>&1 | grep -A 10 "Generated credentials" | grep "WAHA_API_KEY=" | head -1 | sed 's/WAHA_API_KEY=//' | tr -d ' ' || echo "")
    
    if [ -n "$WAHA_CREDS" ]; then
        echo -e "${YELLOW}🔑 WAHA API Key:${NC}"
        echo "   $WAHA_CREDS"
        echo ""
        echo -e "${BLUE}💡 Add to your .env file:${NC}"
        echo "   WAHA_API_URL=http://localhost:$WAHA_PORT"
        echo "   WAHA_API_KEY=$WAHA_CREDS"
        echo "   WAHA_SESSION_NAME=default"
    else
        echo -e "${YELLOW}⚠️  Could not extract API key from logs${NC}"
        echo -e "${YELLOW}   Check logs: docker logs waha${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}💡 Management Commands:${NC}"
    echo "   Start:   cd $WAHA_DIR && docker compose up -d"
    echo "   Stop:    cd $WAHA_DIR && docker compose down"
    echo "   Logs:    docker logs -f waha"
    echo "   Restart: cd $WAHA_DIR && docker compose restart"
    exit 0
fi

# Check if WAHA directory exists
if [ ! -d "$WAHA_DIR" ]; then
    echo -e "${RED}❌ WAHA directory not found at $WAHA_DIR${NC}"
    echo -e "${YELLOW}   Please create the shared WAHA setup first${NC}"
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "$WAHA_DIR/docker-compose.yml" ]; then
    echo -e "${RED}❌ docker-compose.yml not found in $WAHA_DIR${NC}"
    echo -e "${YELLOW}   Please set up WAHA in the shared location first${NC}"
    exit 1
fi

# WAHA container exists but is stopped
if docker ps -a --format '{{.Names}}' | grep -q "^waha$"; then
    echo -e "${YELLOW}📦 WAHA container exists but is stopped${NC}"
    echo -e "${YELLOW}   Starting WAHA from shared location...${NC}"
    cd "$WAHA_DIR"
    docker compose up -d
    sleep 5
    
    if docker ps --format '{{.Names}}' | grep -q "^waha$"; then
        echo -e "${GREEN}✅ WAHA started successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to start WAHA${NC}"
        echo -e "${YELLOW}   Check logs: docker logs waha${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}📦 Starting WAHA from shared location...${NC}"
    cd "$WAHA_DIR"
    docker compose up -d
    sleep 5
    
    if docker ps --format '{{.Names}}' | grep -q "^waha$"; then
        echo -e "${GREEN}✅ WAHA started successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to start WAHA${NC}"
        echo -e "${YELLOW}   Check logs: docker logs waha${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}🎉 WAHA is ready!${NC}"
echo ""
echo -e "${YELLOW}📋 Configuration:${NC}"
echo "   Container name: waha"
echo "   API URL: http://localhost:$WAHA_PORT"
echo "   Swagger UI: http://localhost:$WAHA_PORT/"
echo "   Location: $WAHA_DIR"
echo ""

# Extract credentials from logs
echo -e "${YELLOW}📋 Extracting WAHA credentials from logs...${NC}"
WAHA_CREDS=$(docker logs waha 2>&1 | grep -A 10 "Generated credentials" | grep "WAHA_API_KEY=" | head -1 | sed 's/WAHA_API_KEY=//' | tr -d ' ' || echo "")

if [ -n "$WAHA_CREDS" ]; then
    echo -e "${GREEN}✅ Credentials extracted${NC}"
    echo ""
    echo -e "${YELLOW}🔑 WAHA Credentials:${NC}"
    echo "   API Key: $WAHA_CREDS"
    echo ""
    echo -e "${BLUE}💡 Add to your .env file:${NC}"
    echo "   WAHA_API_URL=http://localhost:$WAHA_PORT"
    echo "   WAHA_API_KEY=$WAHA_CREDS"
    echo "   WAHA_SESSION_NAME=default"
else
    echo -e "${YELLOW}⚠️  Could not extract credentials from logs${NC}"
    echo -e "${YELLOW}   Check logs manually: docker logs waha${NC}"
fi

echo ""
echo -e "${YELLOW}💡 Management Commands:${NC}"
echo "   Start:   cd $WAHA_DIR && docker compose up -d"
echo "   Stop:    cd $WAHA_DIR && docker compose down"
echo "   Logs:    docker logs -f waha"
echo "   Restart: cd $WAHA_DIR && docker compose restart"
echo ""
