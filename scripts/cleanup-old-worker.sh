#!/bin/bash
# Cleanup old Cloudflare Worker (we're using Pages now)
# This script deletes the old Worker deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

echo -e "${GREEN}🧹 Cleanup Old Cloudflare Worker${NC}"
echo "=========================================="

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Load Cloudflare credentials
CLOUDFLARE_API_TOKEN=$(grep "^CLOUDFLARE_API_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
CLOUDFLARE_ACCOUNT_ID=$(grep "^CLOUDFLARE_ACCOUNT_ID=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: Cloudflare credentials not found in .env${NC}"
    exit 1
fi

export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID

WORKER_NAME="alpaca-trading-frontend"

echo -e "${YELLOW}📋 Checking for Worker: $WORKER_NAME${NC}"

# Check if worker exists
if wrangler deployments list --name="$WORKER_NAME" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Found old Worker: $WORKER_NAME${NC}"
    echo -e "${YELLOW}   This Worker is no longer needed since we're using Cloudflare Pages${NC}"
    echo ""
    echo -e "${YELLOW}   To delete it, run:${NC}"
    echo -e "${GREEN}   wrangler delete $WORKER_NAME${NC}"
    echo ""
    read -p "Do you want to delete the old Worker? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🗑️  Deleting Worker: $WORKER_NAME${NC}"
        wrangler delete "$WORKER_NAME" || {
            echo -e "${RED}❌ Failed to delete Worker${NC}"
            echo -e "${YELLOW}   You may need to delete it manually from Cloudflare Dashboard${NC}"
            exit 1
        }
        echo -e "${GREEN}✅ Worker deleted successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Skipped deletion${NC}"
    fi
else
    echo -e "${GREEN}✅ No old Worker found (or already deleted)${NC}"
fi

echo ""
echo -e "${GREEN}📝 Next steps:${NC}"
echo "1. Your frontend is now deployed to Cloudflare Pages (not Workers)"
echo "2. You can remove or update wrangler.toml if you want"
echo "3. All future deployments should use: ./scripts/deploy-cloudflare.sh"
echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"

