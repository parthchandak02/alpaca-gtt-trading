#!/bin/bash
# Start Cloudflare Tunnel with PM2
# This script ensures the tunnel is properly configured and starts it with PM2

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/cloudflared-config.yml"

echo -e "${GREEN}🔒 Starting Cloudflare Tunnel${NC}"
echo "=========================================="

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}❌ Error: cloudflared not found${NC}"
    echo "Install it with: brew install cloudflare/cloudflare/cloudflared"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: cloudflared-config.yml not found${NC}"
    echo "Run setup script first: ./scripts/setup-cloudflare-tunnel.sh"
    exit 1
fi

# Check if tunnel ID is configured
if grep -q "<YOUR_TUNNEL_ID>" "$CONFIG_FILE"; then
    echo -e "${RED}❌ Error: Tunnel ID not configured in cloudflared-config.yml${NC}"
    echo "Run setup script first: ./scripts/setup-cloudflare-tunnel.sh"
    exit 1
fi

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}⚠️  PM2 not found, starting tunnel directly...${NC}"
    echo -e "${GREEN}Starting tunnel: cloudflared tunnel --config $CONFIG_FILE run${NC}"
    cloudflared tunnel --config "$CONFIG_FILE" run
else
    echo -e "${GREEN}✅ Starting tunnel with PM2...${NC}"
    
    # Check if tunnel is already running
    if pm2 list | grep -q "alpaca-tunnel"; then
        echo -e "${YELLOW}⚠️  Tunnel already running in PM2${NC}"
        echo "To restart: pm2 restart alpaca-tunnel"
        echo "To view logs: pm2 logs alpaca-tunnel"
    else
        # Start tunnel with PM2
        pm2 start ecosystem.config.js --only alpaca-tunnel
        echo -e "${GREEN}✅ Tunnel started with PM2${NC}"
        echo ""
        echo "Useful commands:"
        echo "  pm2 logs alpaca-tunnel    # View tunnel logs"
        echo "  pm2 restart alpaca-tunnel # Restart tunnel"
        echo "  pm2 stop alpaca-tunnel    # Stop tunnel"
        echo "  pm2 status                # View all PM2 processes"
    fi
fi

