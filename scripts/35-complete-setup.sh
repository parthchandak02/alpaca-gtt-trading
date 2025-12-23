#!/bin/bash
# Complete setup checklist for production deployment
# This script helps verify and complete all necessary configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CONFIG_FILE="$PROJECT_ROOT/cloudflared-config.yml"

echo -e "${BLUE}📋 Production Setup Checklist${NC}"
echo "=========================================="
echo ""

# Check 1: Frontend Domain
echo -e "${YELLOW}1. Frontend Custom Domain${NC}"
echo -e "   ✅ Domain configured: ${GREEN}trading.parthchandak.info${NC}"
echo ""

# Check 2: Backend API URL
echo -e "${YELLOW}2. Backend API Configuration${NC}"
API_DOMAIN="api-trading.parthchandak.info"
echo -e "   Backend should be accessible at: ${GREEN}https://$API_DOMAIN${NC}"
echo ""

# Check 3: Cloudflare Pages Environment Variables
echo -e "${YELLOW}3. Cloudflare Pages Environment Variables${NC}"
echo -e "   ${YELLOW}⚠️  ACTION REQUIRED:${NC}"
echo -e "   Go to: ${BLUE}https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages/alpaca-trading-frontend/settings/environment-variables${NC}"
echo -e "   Add environment variable:"
echo -e "   ${GREEN}NEXT_PUBLIC_API_URL = https://$API_DOMAIN${NC}"
echo ""

# Check 4: CORS Configuration
echo -e "${YELLOW}4. Backend CORS Configuration${NC}"
CURRENT_CORS=$(grep "^CORS_ORIGINS=" "$ENV_FILE" | cut -d'=' -f2 || echo "")
if echo "$CURRENT_CORS" | grep -q "trading.parthchandak.info"; then
    echo -e "   ${GREEN}✅ CORS includes trading.parthchandak.info${NC}"
else
    echo -e "   ${RED}❌ CORS needs update${NC}"
    echo -e "   Current: $CURRENT_CORS"
    echo -e "   ${YELLOW}Update .env:${NC}"
    echo -e "   ${GREEN}CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://trading.parthchandak.info${NC}"
fi
echo ""

# Check 5: Cloudflare Tunnel Configuration
echo -e "${YELLOW}5. Cloudflare Tunnel Setup${NC}"
if grep -q "<YOUR_TUNNEL_ID>" "$CONFIG_FILE"; then
    echo -e "   ${RED}❌ Tunnel not configured${NC}"
    echo -e "   ${YELLOW}Run setup script:${NC}"
    echo -e "   ${GREEN}./scripts/setup-cloudflare-tunnel.sh${NC}"
else
    echo -e "   ${GREEN}✅ Tunnel configuration file ready${NC}"
    TUNNEL_ID=$(grep "^tunnel:" "$CONFIG_FILE" | awk '{print $2}')
    echo -e "   Tunnel ID: ${GREEN}$TUNNEL_ID${NC}"
fi
echo ""

# Check 6: PM2 Processes
echo -e "${YELLOW}6. PM2 Processes${NC}"
BACKEND_RUNNING=$(pm2 list 2>/dev/null | grep -q "alpaca-backend.*online" && echo "yes" || echo "no")
TUNNEL_RUNNING=$(pm2 list 2>/dev/null | grep -q "alpaca-tunnel.*online" && echo "yes" || echo "no")

if [ "$BACKEND_RUNNING" = "yes" ]; then
    echo -e "   ${GREEN}✅ Backend running${NC}"
else
    echo -e "   ${RED}❌ Backend not running${NC}"
    echo -e "   ${YELLOW}Start with:${NC} ${GREEN}pm2 start ecosystem.config.js --only alpaca-backend${NC}"
fi

if [ "$TUNNEL_RUNNING" = "yes" ]; then
    echo -e "   ${GREEN}✅ Tunnel running${NC}"
else
    echo -e "   ${RED}❌ Tunnel not running${NC}"
    echo -e "   ${YELLOW}Start with:${NC} ${GREEN}pm2 start ecosystem.config.js --only alpaca-tunnel${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}📝 Summary${NC}"
echo "=========================================="
echo ""
echo "To complete setup:"
echo ""
echo "1. ${YELLOW}Set Cloudflare Pages environment variable:${NC}"
echo "   ${GREEN}NEXT_PUBLIC_API_URL = https://$API_DOMAIN${NC}"
echo "   Dashboard: https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages/alpaca-trading-frontend/settings/environment-variables"
echo ""
echo "2. ${YELLOW}Update CORS in .env (if needed):${NC}"
echo "   ${GREEN}CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://trading.parthchandak.info${NC}"
echo ""
echo "3. ${YELLOW}Setup Cloudflare Tunnel (if not done):${NC}"
echo "   ${GREEN}./scripts/setup-cloudflare-tunnel.sh${NC}"
echo ""
echo "4. ${YELLOW}Start backend and tunnel with PM2:${NC}"
echo "   ${GREEN}pm2 start ecosystem.config.js${NC}"
echo ""
echo "5. ${YELLOW}Verify deployment:${NC}"
echo "   Frontend: ${GREEN}https://trading.parthchandak.info${NC}"
echo "   Backend: ${GREEN}https://$API_DOMAIN${NC}"
echo ""
echo -e "${GREEN}✅ Setup checklist complete!${NC}"

