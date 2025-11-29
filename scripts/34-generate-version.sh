#!/bin/bash
# Generate version.json file with build timestamp and git info
# This file is used to track deployment versions and prompt users to refresh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📋 Generating version.json...${NC}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Get git info (fallback to defaults if not in git repo)
GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
GIT_COMMIT_SHORT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Get current timestamp
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BUILD_TIME_READABLE=$(date +"%B %d, %Y at %I:%M %p %Z")

# Generate version string (YYYYMMDD-HHMM-gitshort)
VERSION=$(date -u +"%Y%m%d-%H%M")-${GIT_COMMIT_SHORT}

echo -e "${GREEN}Version: ${VERSION}${NC}"
echo -e "${GREEN}Build Time: ${BUILD_TIME_READABLE}${NC}"
echo -e "${GREEN}Commit: ${GIT_COMMIT_SHORT} (${GIT_BRANCH})${NC}"

# Create version.json for frontend
FRONTEND_VERSION_FILE="$PROJECT_ROOT/frontend/public/version.json"
mkdir -p "$PROJECT_ROOT/frontend/public"

cat > "$FRONTEND_VERSION_FILE" <<EOF
{
  "version": "$VERSION",
  "buildTime": "$BUILD_TIME",
  "buildTimeReadable": "$BUILD_TIME_READABLE",
  "gitCommit": "$GIT_COMMIT",
  "gitCommitShort": "$GIT_COMMIT_SHORT",
  "gitBranch": "$GIT_BRANCH"
}
EOF

echo -e "${GREEN}✅ Frontend version file created: $FRONTEND_VERSION_FILE${NC}"

# Create version.json for backend
BACKEND_VERSION_FILE="$PROJECT_ROOT/backend/version.json"

cat > "$BACKEND_VERSION_FILE" <<EOF
{
  "version": "$VERSION",
  "buildTime": "$BUILD_TIME",
  "buildTimeReadable": "$BUILD_TIME_READABLE",
  "gitCommit": "$GIT_COMMIT",
  "gitCommitShort": "$GIT_COMMIT_SHORT",
  "gitBranch": "$GIT_BRANCH"
}
EOF

echo -e "${GREEN}✅ Backend version file created: $BACKEND_VERSION_FILE${NC}"
echo -e "${GREEN}🎉 Version generation complete!${NC}"


