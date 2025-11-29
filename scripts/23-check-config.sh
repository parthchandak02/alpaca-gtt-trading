#!/bin/bash
# Check Cloudflare Pages configuration
# This script verifies that environment variables are set correctly

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load .env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Load credentials from .env (only the ones we need)
CLOUDFLARE_API_TOKEN=$(grep "^CLOUDFLARE_API_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
CLOUDFLARE_ACCOUNT_ID=$(grep "^CLOUDFLARE_ACCOUNT_ID=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

echo -e "${GREEN}🔍 Checking Cloudflare Pages Configuration${NC}"
echo "=============================================="
echo ""

# Check project configuration
echo -e "${YELLOW}📋 Project: alpaca-trading-frontend${NC}"
CONFIG=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/alpaca-trading-frontend" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json")

# Extract key information
PROD_BRANCH=$(echo "$CONFIG" | jq -r '.result.production_branch')
DOMAINS=$(echo "$CONFIG" | jq -r '.result.domains[]' | tr '\n' ', ' | sed 's/,$//')
PROD_API_URL=$(echo "$CONFIG" | jq -r '.result.deployment_configs.production.env_vars.NEXT_PUBLIC_API_URL.value // "NOT SET"')
PREVIEW_API_URL=$(echo "$CONFIG" | jq -r '.result.deployment_configs.preview.env_vars.NEXT_PUBLIC_API_URL.value // "NOT SET"')

echo -e "${GREEN}✅ Production Branch: ${PROD_BRANCH}${NC}"
echo -e "${GREEN}✅ Domains: ${DOMAINS}${NC}"
echo ""

echo -e "${YELLOW}🔧 Environment Variables:${NC}"
echo "  Production API URL: ${PROD_API_URL}"
echo "  Preview API URL: ${PREVIEW_API_URL}"
echo ""

# Verify configuration
if [ "$PROD_API_URL" = "https://api-trading.parthchandak.info" ] && [ "$PREVIEW_API_URL" = "https://api-trading.parthchandak.info" ]; then
    echo -e "${GREEN}✅ Configuration is correct!${NC}"
    echo "  Both Production and Preview are using: https://api-trading.parthchandak.info"
else
    echo -e "${RED}❌ Configuration issue detected!${NC}"
    if [ "$PROD_API_URL" != "https://api-trading.parthchandak.info" ]; then
        echo -e "${RED}  Production API URL is incorrect: ${PROD_API_URL}${NC}"
    fi
    if [ "$PREVIEW_API_URL" != "https://api-trading.parthchandak.info" ]; then
        echo -e "${RED}  Preview API URL is incorrect: ${PREVIEW_API_URL}${NC}"
    fi
fi
echo ""

# Get recent deployments
echo -e "${YELLOW}📦 Recent Deployments:${NC}"
DEPLOYMENTS=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/alpaca-trading-frontend/deployments?per_page=5" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json")

echo "$DEPLOYMENTS" | jq -r '.result[] | "\(.environment) - \(.url) - \(.created_on)"' | head -5
echo ""

echo -e "${GREEN}🎉 Check complete!${NC}"

