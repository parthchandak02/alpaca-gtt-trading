#!/bin/bash
# Combined deployment script: Git push + Cloudflare Pages deployment
# Checks for secrets, commits, pushes, and deploys

set -e
set -x

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${GREEN}🚀 Deployment Script${NC}"
echo "=========================================="

# Step 1: Check for secrets in staged files
echo -e "${YELLOW}Step 1: Checking for secrets...${NC}"
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || echo "")

    if [ -n "$STAGED_FILES" ]; then
    echo "Checking staged files for secrets..."
    SECRETS_FOUND=$(git diff --cached | grep -iE "(api_key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]" | grep -v "deploy.sh" | grep -v "grep" | grep -v "\$(" || true)
    
    if [ -n "$SECRETS_FOUND" ]; then
        echo -e "${RED}❌ ERROR: Potential secrets found in staged files!${NC}"
        echo "$SECRETS_FOUND"
        exit 1
    fi
    echo -e "${GREEN}✅ No secrets found in staged files${NC}"
else
    echo "No files staged yet"
fi

# Step 2: Check for secrets in modified files
echo -e "${YELLOW}Step 2: Checking modified files for secrets...${NC}"
MODIFIED_FILES=$(git diff HEAD --name-only 2>/dev/null || echo "")

if [ -n "$MODIFIED_FILES" ]; then
    SECRETS_FOUND=$(git diff HEAD | grep -iE "(api_key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]" | grep -v "deploy.sh" | grep -v "grep" | grep -v "\$(" || true)
    
    if [ -n "$SECRETS_FOUND" ]; then
        echo -e "${RED}❌ ERROR: Potential secrets found in modified files!${NC}"
        echo "$SECRETS_FOUND"
        exit 1
    fi
    echo -e "${GREEN}✅ No secrets found in modified files${NC}"
fi

# Step 3: Stage all changes
echo -e "${YELLOW}Step 3: Staging changes...${NC}"
git add -A

# Check staged files again after staging
# Exclude .env files, deploy.sh itself, and shell assignment lines from the check
STAGED_SECRETS=$(git diff --cached | grep -iE "(api_key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]" | grep -v "deploy.sh" | grep -v "grep" | grep -v "\$(" || true)
if [ -n "$STAGED_SECRETS" ]; then
    echo -e "${RED}❌ ERROR: Potential secrets found after staging!${NC}"
    echo "$STAGED_SECRETS"
    git reset
    exit 1
fi

# Step 4: Generate commit message
echo -e "${YELLOW}Step 4: Generating commit message...${NC}"
CHANGED_FILES=$(git diff --cached --name-only | head -10)
COMMIT_TYPE="feat"
if echo "$CHANGED_FILES" | grep -qE "(fix|bug|error)"; then
    COMMIT_TYPE="fix"
elif echo "$CHANGED_FILES" | grep -qE "(refactor|cleanup|style)"; then
    COMMIT_TYPE="refactor"
fi

COMMIT_MSG="${COMMIT_TYPE}: Update project files"
if [ -n "$CHANGED_FILES" ]; then
    FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
    COMMIT_MSG="${COMMIT_TYPE}: Update ${FILE_COUNT} files"
fi

# Step 5: Commit
echo -e "${YELLOW}Step 5: Committing changes...${NC}"
echo "Commit message: $COMMIT_MSG"
read -p "Continue with commit? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 1
fi

git commit -m "$COMMIT_MSG"

# Step 6: Push to git
echo -e "${YELLOW}Step 6: Pushing to git...${NC}"
git push origin main || {
    echo -e "${YELLOW}⚠️  Git push failed or no remote configured${NC}"
    echo "Continuing with Cloudflare deployment..."
}

# Step 7: Deploy to Cloudflare
echo -e "${YELLOW}Step 7: Deploying to Cloudflare Pages...${NC}"
"$SCRIPT_DIR/deploy-cloudflare.sh"

echo -e "${GREEN}✅ Deployment complete!${NC}"


