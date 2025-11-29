#!/bin/bash
# Python code quality checker (check only, no fixes)
# Use fix-code-quality.sh to auto-fix issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Python Code Quality Checker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    cd "$BACKEND_DIR" && uv venv && cd "$PROJECT_ROOT"
fi

# Install dev dependencies if needed
echo -e "${YELLOW}Ensuring dev dependencies are installed...${NC}"
cd "$BACKEND_DIR" && uv pip install -r requirements-dev.txt > /dev/null 2>&1 && cd "$PROJECT_ROOT"

echo -e "${GREEN}✓ Environment ready${NC}"
echo ""

# Track if any issues were found
ISSUES_FOUND=0

# Use venv's bin directory for tools
VENV_BIN="${VENV_DIR}/bin"

# 1. Ruff - Fast linter (unused imports, variables, errors, etc.)
echo -e "${BLUE}[1/3] Running Ruff linter...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if (cd "$BACKEND_DIR" && "$VENV_BIN/ruff" check . --output-format=concise); then
    echo -e "${GREEN}✓ Ruff: No linting errors found${NC}"
else
    echo -e "${RED}✗ Ruff: Found linting errors${NC}"
    ISSUES_FOUND=1
fi
echo ""

# Show auto-fixable issues
echo -e "${YELLOW}Checking for auto-fixable issues...${NC}"
FIXABLE=$(cd "$BACKEND_DIR" && "$VENV_BIN/ruff" check . --output-format=concise 2>&1 | grep -c "\[*\]" || true)
if [ "$FIXABLE" -gt 0 ]; then
    echo -e "${YELLOW}Found $FIXABLE potentially fixable issue(s). Run: cd backend && $VENV_BIN/ruff check --fix .${NC}"
fi
echo ""

# 2. Vulture - Find dead/unused code (run on key files only to avoid timeout)
echo -e "${BLUE}[2/3] Running Vulture (dead code detector)...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}Note: Running on key files only (full scan can be slow)${NC}"
VULTURE_FILES="alpaca_client.py gtt_service.py main.py models.py schemas.py"
VULTURE_ERROR=0
for file in $VULTURE_FILES; do
    if [ -f "$BACKEND_DIR/$file" ]; then
        if ! (cd "$BACKEND_DIR" && "$VENV_BIN/vulture" "$file" --min-confidence 80 2>&1 | grep -q "unused"); then
            # Check if vulture found issues (exit code 3 means dead code found)
            if (cd "$BACKEND_DIR" && "$VENV_BIN/vulture" "$file" --min-confidence 80 >/dev/null 2>&1); then
                : # No issues found
            else
                VULTURE_EXIT=$?
                if [ $VULTURE_EXIT -eq 3 ]; then
                    echo -e "${YELLOW}Found unused code in $file:${NC}"
                    (cd "$BACKEND_DIR" && "$VENV_BIN/vulture" "$file" --min-confidence 80 2>&1 | head -20)
                    VULTURE_ERROR=1
                fi
            fi
        fi
    fi
done
if [ $VULTURE_ERROR -eq 0 ]; then
    echo -e "${GREEN}✓ Vulture: No dead code found in key files${NC}"
else
    echo -e "${RED}✗ Vulture: Found dead/unused code${NC}"
    ISSUES_FOUND=1
fi
echo ""

# 3. Ruff format check
echo -e "${BLUE}[3/3] Checking code formatting...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if (cd "$BACKEND_DIR" && "$VENV_BIN/ruff" format --check .); then
    echo -e "${GREEN}✓ Code formatting is correct${NC}"
else
    echo -e "${RED}✗ Code formatting issues found${NC}"
    echo -e "${YELLOW}Run: cd backend && $VENV_BIN/ruff format .${NC}"
    ISSUES_FOUND=1
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Issues found. See details above.${NC}"
    echo ""
    echo -e "${YELLOW}Quick fixes:${NC}"
    echo "  • Auto-fix all issues:  bash scripts/32-fix-code-quality.sh"
    echo "  • Review dead code:     cd backend && .venv/bin/vulture <file.py> --min-confidence 100"
    exit 1
fi

