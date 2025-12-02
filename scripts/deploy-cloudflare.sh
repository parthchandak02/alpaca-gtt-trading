#!/bin/bash
# Deploy frontend to Cloudflare Pages
# This script builds the Next.js app and deploys it to Cloudflare Pages
# Project name: alpaca-trading-frontend
# Custom domain: trading.parthchandak.info

set -e  # Exit on error
set -x  # Print commands as they execute (verbose mode)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BUILD_DIR="$FRONTEND_DIR/.next"

# Configuration
PROJECT_NAME="alpaca-trading-frontend"
CUSTOM_DOMAIN="trading.parthchandak.info"
ENV_FILE="$PROJECT_ROOT/.env"

echo -e "${GREEN}🚀 Cloudflare Pages Deployment Script${NC}"
echo "=========================================="

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found at $ENV_FILE${NC}"
    exit 1
fi

# Load Cloudflare credentials from .env
echo -e "${YELLOW}📋 Checking Cloudflare credentials...${NC}"
echo -e "${YELLOW}   Reading from: $ENV_FILE${NC}"

# Read credentials from .env file
CLOUDFLARE_API_TOKEN=$(grep "^CLOUDFLARE_API_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
CLOUDFLARE_ACCOUNT_ID=$(grep "^CLOUDFLARE_ACCOUNT_ID=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

echo -e "${YELLOW}   API Token: ${CLOUDFLARE_API_TOKEN:0:10}...${NC}"
echo -e "${YELLOW}   Account ID: $CLOUDFLARE_ACCOUNT_ID${NC}"

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_API_TOKEN not found in .env${NC}"
    echo -e "${RED}   Checked file: $ENV_FILE${NC}"
    exit 1
fi

if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_ACCOUNT_ID not found in .env${NC}"
    echo -e "${RED}   Checked file: $ENV_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Cloudflare credentials found${NC}"

# Export credentials for wrangler
export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID
echo -e "${YELLOW}   Exported CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID${NC}"

# Check if wrangler is installed
echo -e "${YELLOW}🔍 Checking wrangler installation...${NC}"
if ! command -v wrangler &> /dev/null; then
    echo -e "${RED}❌ Error: wrangler CLI not found${NC}"
    echo "Install it with: npm install -g wrangler"
    exit 1
fi
WRANGLER_VERSION=$(wrangler --version 2>&1)
echo -e "${GREEN}✅ wrangler found: $WRANGLER_VERSION${NC}"

# Check if project exists, create if not
echo -e "${YELLOW}📦 Checking project '$PROJECT_NAME'...${NC}"
echo -e "${YELLOW}   Running: wrangler pages project list${NC}"
PROJECT_LIST=$(wrangler pages project list 2>&1)
PROJECT_LIST_EXIT_CODE=$?
echo -e "${YELLOW}   Exit code: $PROJECT_LIST_EXIT_CODE${NC}"
echo -e "${YELLOW}   Project list output:${NC}"
echo "$PROJECT_LIST" | head -20
echo ""

PROJECT_EXISTS=$(echo "$PROJECT_LIST" | grep -q "$PROJECT_NAME" && echo "yes" || echo "no")
echo -e "${YELLOW}   Project '$PROJECT_NAME' exists: $PROJECT_EXISTS${NC}"

if [ "$PROJECT_EXISTS" = "yes" ]; then
    echo -e "${GREEN}✅ Project found in list${NC}"
else
    echo -e "${YELLOW}⚠️  Project not found in API list${NC}"
    echo -e "${YELLOW}   Attempting to create project with production branch 'main'...${NC}"
    CREATE_OUTPUT=$(wrangler pages project create "$PROJECT_NAME" --production-branch=main 2>&1)
    CREATE_EXIT_CODE=$?
    echo -e "${YELLOW}   Create exit code: $CREATE_EXIT_CODE${NC}"
    
    if [ $CREATE_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Project created successfully${NC}"
    else
        echo -e "${YELLOW}   Create output:${NC}"
        echo "$CREATE_OUTPUT" | head -10
        echo -e "${YELLOW}   Project may already exist or there was an issue${NC}"
        echo -e "${YELLOW}   Proceeding with deployment anyway...${NC}"
    fi
fi

# Navigate to frontend directory
echo -e "${YELLOW}📂 Changing to frontend directory: $FRONTEND_DIR${NC}"
cd "$FRONTEND_DIR"
echo -e "${YELLOW}   Current directory: $(pwd)${NC}"

# Check if node_modules exists
echo -e "${YELLOW}📦 Checking dependencies...${NC}"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}   node_modules not found, installing dependencies...${NC}"
    if command -v pnpm &> /dev/null; then
        echo -e "${YELLOW}   Using pnpm to install${NC}"
        pnpm install
    elif command -v npm &> /dev/null; then
        echo -e "${YELLOW}   Using npm to install${NC}"
        npm install
    else
        echo -e "${RED}❌ Error: Neither pnpm nor npm found${NC}"
        exit 1
    fi
    INSTALL_EXIT_CODE=$?
    echo -e "${YELLOW}   Install exit code: $INSTALL_EXIT_CODE${NC}"
    if [ $INSTALL_EXIT_CODE -ne 0 ]; then
        echo -e "${RED}❌ Dependency installation failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${GREEN}✅ node_modules exists, skipping install${NC}"
fi

# Build Next.js app
echo -e "${YELLOW}🔨 Building Next.js application...${NC}"
echo -e "${YELLOW}   Build directory will be: $BUILD_DIR${NC}"
if command -v pnpm &> /dev/null; then
    echo -e "${YELLOW}   Running: pnpm build${NC}"
    pnpm build
else
    echo -e "${YELLOW}   Running: npm run build${NC}"
    npm run build
fi
BUILD_EXIT_CODE=$?
echo -e "${YELLOW}   Build exit code: $BUILD_EXIT_CODE${NC}"

# Check if build was successful
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}❌ Error: Build failed - .next directory not found${NC}"
    echo -e "${RED}   Expected directory: $BUILD_DIR${NC}"
    echo -e "${RED}   Current directory contents:${NC}"
    ls -la
    exit 1
fi

echo -e "${GREEN}✅ Build completed successfully${NC}"
echo -e "${YELLOW}   Build directory exists: $BUILD_DIR${NC}"
echo -e "${YELLOW}   Build directory size: $(du -sh "$BUILD_DIR" | cut -f1)${NC}"

# Deploy to Cloudflare Pages
echo -e "${YELLOW}🚀 Deploying to Cloudflare Pages...${NC}"
echo "Project: $PROJECT_NAME"
echo "Domain: $CUSTOM_DOMAIN"

# Determine deployment directory
# Cloudflare Pages supports Next.js in multiple ways:
# 1. Static export (out directory) - for Pages Router
# 2. @cloudflare/next-on-pages (.vercel/output) - for App Router with SSR
# 3. Standard build (.next) - may work but has limitations

DEPLOY_DIR=""
echo -e "${YELLOW}📦 Determining deployment directory...${NC}"
echo -e "${YELLOW}   Checking for .vercel/output...${NC}"
if [ -d "$FRONTEND_DIR/.vercel/output" ]; then
    # Using @cloudflare/next-on-pages (recommended for App Router)
    DEPLOY_DIR="$FRONTEND_DIR/.vercel/output"
    echo -e "${GREEN}✅ Found .vercel/output (next-on-pages build)${NC}"
    echo -e "${YELLOW}   Directory contents:${NC}"
    ls -la "$DEPLOY_DIR" | head -10
elif [ -d "$FRONTEND_DIR/out" ]; then
    # Static export (works for Pages Router)
    DEPLOY_DIR="$FRONTEND_DIR/out"
    echo -e "${GREEN}✅ Using static export (out directory)${NC}"
    echo -e "${YELLOW}   Directory exists: $DEPLOY_DIR${NC}"
    echo -e "${YELLOW}   Directory size: $(du -sh "$DEPLOY_DIR" | cut -f1)${NC}"
elif [ -d "$BUILD_DIR" ]; then
    # Standard Next.js build - check if we should use next-on-pages
    echo -e "${YELLOW}📦 Standard Next.js build detected${NC}"
    echo -e "${YELLOW}   Build directory: $BUILD_DIR${NC}"
    echo -e "${YELLOW}   Directory exists: $(test -d "$BUILD_DIR" && echo 'yes' || echo 'no')${NC}"
    
    # Check if App Router is being used (has app directory)
    if [ -d "$FRONTEND_DIR/app" ]; then
        echo -e "${YELLOW}⚠️  App Router detected - recommend using @cloudflare/next-on-pages${NC}"
        echo -e "${YELLOW}   For now, deploying .next directory (may have limitations)${NC}"
        echo -e "${YELLOW}   To enable full SSR support, install: pnpm add -D @cloudflare/next-on-pages${NC}"
    fi
    
    echo -e "${YELLOW}   .next directory structure:${NC}"
    ls -la "$BUILD_DIR" | head -10
    DEPLOY_DIR="$BUILD_DIR"
else
    echo -e "${RED}❌ Error: No build directory found${NC}"
    echo -e "${RED}   Checked:${NC}"
    echo -e "${RED}     - $FRONTEND_DIR/.vercel/output${NC}"
    echo -e "${RED}     - $FRONTEND_DIR/out${NC}"
    echo -e "${RED}     - $BUILD_DIR${NC}"
    echo -e "${RED}   Current directory: $(pwd)${NC}"
    echo -e "${RED}   Directory contents:${NC}"
    ls -la
    exit 1
fi

echo -e "${GREEN}✅ Deployment directory determined: $DEPLOY_DIR${NC}"

# Deploy to Cloudflare Pages
echo -e "${YELLOW}🚀 Deploying to Cloudflare Pages...${NC}"
echo -e "${YELLOW}   Project: $PROJECT_NAME${NC}"
echo -e "${YELLOW}   Domain: $CUSTOM_DOMAIN${NC}"
echo -e "${YELLOW}   Deploy directory: $DEPLOY_DIR${NC}"
echo -e "${YELLOW}   Directory exists: $(test -d "$DEPLOY_DIR" && echo 'yes' || echo 'no')${NC}"

# Get git info for commit message
GIT_COMMIT_MESSAGE=$(git -C "$PROJECT_ROOT" log -1 --pretty=%B 2>/dev/null || echo 'Manual deployment')
GIT_COMMIT_HASH=$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo 'unknown')
echo -e "${YELLOW}   Git commit message: $GIT_COMMIT_MESSAGE${NC}"
echo -e "${YELLOW}   Git commit hash: $GIT_COMMIT_HASH${NC}"

echo -e "${YELLOW}   Running deployment command...${NC}"
echo -e "${YELLOW}   Command: wrangler pages deploy \"$DEPLOY_DIR\" --project-name=\"$PROJECT_NAME\" --branch=\"main\" --commit-message=\"Deploy: $GIT_COMMIT_MESSAGE\" --commit-hash=\"$GIT_COMMIT_HASH\"${NC}"

wrangler pages deploy "$DEPLOY_DIR" \
    --project-name="$PROJECT_NAME" \
    --branch="main" \
    --commit-message="Deploy: $GIT_COMMIT_MESSAGE" \
    --commit-hash="$GIT_COMMIT_HASH" 2>&1 | tee /tmp/wrangler-deploy.log

DEPLOY_EXIT_CODE=${PIPESTATUS[0]}
echo -e "${YELLOW}   Deployment exit code: $DEPLOY_EXIT_CODE${NC}"

if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    echo -e "${YELLOW}   Full deployment log saved to: /tmp/wrangler-deploy.log${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo -e "${GREEN}📝 Next steps:${NC}"
echo ""
echo "1. If project doesn't exist, create it in Cloudflare Dashboard:"
echo "   - Go to: https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages"
echo "   - Click 'Create application' → 'Pages' → 'Upload assets'"
echo "   - Name it: $PROJECT_NAME"
echo "   - Then run this script again to deploy"
echo ""
echo "2. Configure custom domain '$CUSTOM_DOMAIN':"
echo "   - Go to: https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages/$PROJECT_NAME"
echo "   - Navigate to: Custom domains → Add custom domain"
echo "   - Enter: $CUSTOM_DOMAIN"
echo "   - Follow DNS setup instructions"
echo ""
echo "3. Set environment variables in Cloudflare Dashboard:"
echo "   - Go to: Settings → Environment variables"
echo "   - Add: NEXT_PUBLIC_API_URL = https://api-trading.parthchandak.info"
echo "   - (Or your backend API URL)"
echo ""
echo "4. Verify deployment:"
echo "   - Check deployment status in Cloudflare Dashboard"
echo "   - Visit: https://$PROJECT_NAME.pages.dev (temporary URL)"
echo ""
echo -e "${GREEN}🎉 Build complete!${NC}"
echo -e "   Build directory: ${GREEN}$DEPLOY_DIR${NC}"
echo -e "   Ready to deploy to: ${GREEN}https://$CUSTOM_DOMAIN${NC}"

