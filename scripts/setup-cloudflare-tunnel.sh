#!/bin/bash
# Setup Cloudflare Tunnel for secure backend API access
# This script creates and configures a Cloudflare Tunnel to expose the backend API
# securely without exposing it directly to the internet

set -e  # Exit on error
set -x  # Verbose mode

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CONFIG_FILE="$PROJECT_ROOT/cloudflared-config.yml"

# Configuration
TUNNEL_NAME="alpaca-backend"
API_DOMAIN="api-trading.parthchandak.info"
BACKEND_PORT=8000

echo -e "${GREEN}🔒 Cloudflare Tunnel Setup Script${NC}"
echo "=========================================="

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found at $ENV_FILE${NC}"
    exit 1
fi

# Load Cloudflare credentials from .env
echo -e "${YELLOW}📋 Checking Cloudflare credentials...${NC}"
CLOUDFLARE_API_TOKEN=$(grep "^CLOUDFLARE_API_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
CLOUDFLARE_ACCOUNT_ID=$(grep "^CLOUDFLARE_ACCOUNT_ID=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_API_TOKEN not found in .env${NC}"
    exit 1
fi

if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_ACCOUNT_ID not found in .env${NC}"
    exit 1
fi

export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID
echo -e "${GREEN}✅ Cloudflare credentials found${NC}"

# Check if cloudflared is installed
echo -e "${YELLOW}🔍 Checking cloudflared installation...${NC}"
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}❌ Error: cloudflared not found${NC}"
    echo -e "${YELLOW}   Install it with:${NC}"
    echo -e "${YELLOW}   macOS: brew install cloudflare/cloudflare/cloudflared${NC}"
    echo -e "${YELLOW}   Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/${NC}"
    exit 1
fi

CLOUDFLARED_VERSION=$(cloudflared --version 2>&1)
echo -e "${GREEN}✅ cloudflared found: $CLOUDFLARED_VERSION${NC}"

# Check if tunnel already exists
echo -e "${YELLOW}📦 Checking for existing tunnel: $TUNNEL_NAME${NC}"
TUNNEL_LIST=$(cloudflared tunnel list 2>&1 || echo "")
TUNNEL_EXISTS=$(echo "$TUNNEL_LIST" | grep -q "$TUNNEL_NAME" && echo "yes" || echo "no")

if [ "$TUNNEL_EXISTS" = "yes" ]; then
    echo -e "${GREEN}✅ Tunnel '$TUNNEL_NAME' already exists${NC}"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    echo -e "${YELLOW}   Tunnel ID: $TUNNEL_ID${NC}"
else
    echo -e "${YELLOW}📦 Creating new tunnel: $TUNNEL_NAME${NC}"
    CREATE_OUTPUT=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1)
    CREATE_EXIT_CODE=$?
    
    if [ $CREATE_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Tunnel created successfully${NC}"
        # Extract tunnel ID from output
        TUNNEL_ID=$(echo "$CREATE_OUTPUT" | grep -oP 'Created tunnel \K[^\s]+' || cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
        echo -e "${YELLOW}   Tunnel ID: $TUNNEL_ID${NC}"
    else
        echo -e "${RED}❌ Failed to create tunnel${NC}"
        echo "$CREATE_OUTPUT"
        exit 1
    fi
fi

# Get tunnel ID if not set
if [ -z "$TUNNEL_ID" ]; then
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
fi

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${RED}❌ Error: Could not determine tunnel ID${NC}"
    exit 1
fi

# Configure DNS route
echo -e "${YELLOW}🌐 Configuring DNS route...${NC}"
echo -e "${YELLOW}   Domain: $API_DOMAIN${NC}"
echo -e "${YELLOW}   Tunnel: $TUNNEL_NAME ($TUNNEL_ID)${NC}"

DNS_OUTPUT=$(cloudflared tunnel route dns "$TUNNEL_NAME" "$API_DOMAIN" 2>&1)
DNS_EXIT_CODE=$?

if [ $DNS_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ DNS route configured${NC}"
else
    echo -e "${YELLOW}⚠️  DNS route may already exist or there was an issue${NC}"
    echo "$DNS_OUTPUT" | head -5
fi

# Update cloudflared-config.yml
echo -e "${YELLOW}📝 Updating cloudflared-config.yml...${NC}"
CREDENTIALS_FILE="$HOME/.cloudflared/${TUNNEL_ID}.json"

# Check if credentials file exists
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${YELLOW}⚠️  Credentials file not found at: $CREDENTIALS_FILE${NC}"
    echo -e "${YELLOW}   This is normal for new tunnels - cloudflared will create it${NC}"
fi

# Create/update config file
cat > "$CONFIG_FILE" << EOF
# Cloudflare Tunnel Configuration
# Run: cloudflared tunnel --config cloudflared-config.yml run
# Or: cloudflared tunnel run $TUNNEL_NAME

tunnel: $TUNNEL_ID
credentials-file: $CREDENTIALS_FILE

ingress:
  # Backend API - only accessible through Cloudflare Tunnel
  - hostname: $API_DOMAIN
    service: http://localhost:$BACKEND_PORT
  
  # Catch-all rule (must be last)
  - service: http_status:404
EOF

echo -e "${GREEN}✅ Configuration file updated: $CONFIG_FILE${NC}"
echo -e "${YELLOW}   Tunnel ID: $TUNNEL_ID${NC}"
echo -e "${YELLOW}   Credentials: $CREDENTIALS_FILE${NC}"
echo -e "${YELLOW}   Backend: http://localhost:$BACKEND_PORT${NC}"
echo -e "${YELLOW}   Public URL: https://$API_DOMAIN${NC}"

# Security recommendations
echo ""
echo -e "${GREEN}🔒 Security Setup Complete!${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo ""
echo "1. Update CORS settings in backend to allow your frontend domain:"
echo "   - Edit .env file and update CORS_ORIGINS:"
echo "     ${GREEN}CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://trading.parthchandak.info${NC}"
echo "   - Or add to .env:"
echo "     ${GREEN}CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://trading.parthchandak.info${NC}"
echo ""
echo "2. Set frontend API URL in Cloudflare Pages:"
echo "   - Go to: https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages/alpaca-trading-frontend"
echo "   - Settings → Environment variables"
echo "   - Add: NEXT_PUBLIC_API_URL = https://$API_DOMAIN"
echo ""
echo "3. Update ecosystem.config.js to enable tunnel:"
echo "   ${YELLOW}The tunnel PM2 config is commented out - uncomment it after setup${NC}"
echo ""
echo "4. Start everything with PM2:"
echo "   ${GREEN}pm2 start ecosystem.config.js${NC}"
echo "   Or start individually:"
echo "   ${GREEN}pm2 start ecosystem.config.js --only alpaca-backend${NC}"
echo "   ${GREEN}pm2 start ecosystem.config.js --only alpaca-tunnel${NC}"
echo ""
echo "5. Or start tunnel manually:"
echo "   ${GREEN}cloudflared tunnel --config $CONFIG_FILE run${NC}"
echo "   Or: ${GREEN}cloudflared tunnel run $TUNNEL_NAME${NC}"
echo ""
echo "6. View logs:"
echo "   ${GREEN}pm2 logs alpaca-tunnel${NC}"
echo "   ${GREEN}pm2 logs alpaca-backend${NC}"
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo -e "   Your backend will be accessible at: ${GREEN}https://$API_DOMAIN${NC}"
echo -e "   ${YELLOW}(Only through Cloudflare Tunnel - not directly exposed to internet)${NC}"

