#!/bin/bash
# Auto-fix Python code quality issues
# Automatically fixes linting, formatting, and common code issues

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
VENV_BIN="${VENV_DIR}/bin"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Python Code Quality Auto-Fix${NC}"
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

# Parse arguments
AUTO_FIX_LINT=true
AUTO_FORMAT=true
UNSAFE_FIXES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-fix-lint)
            AUTO_FIX_LINT=false
            shift
            ;;
        --no-format)
            AUTO_FORMAT=false
            shift
            ;;
        --unsafe-fixes)
            UNSAFE_FIXES=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--no-fix-lint] [--no-format] [--unsafe-fixes]"
            exit 1
            ;;
    esac
done

FIXES_APPLIED=0

# 1. Auto-fix linting issues
if [ "$AUTO_FIX_LINT" = true ]; then
    echo -e "${BLUE}[1/2] Auto-fixing linting issues...${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    FIX_CMD="$VENV_BIN/ruff check --fix"
    if [ "$UNSAFE_FIXES" = true ]; then
        FIX_CMD="$FIX_CMD --unsafe-fixes"
    fi
    
    cd "$BACKEND_DIR"
    
    if $FIX_CMD . > /tmp/ruff-fix.log 2>&1; then
        echo -e "${GREEN}✓ No linting issues to fix${NC}"
    else
        # Check exit code and count fixes
        EXIT_CODE=$?
        FIXED_COUNT=$(grep -c "Fixed" /tmp/ruff-fix.log 2>/dev/null || echo "0")
        FIXED_COUNT=$(echo "$FIXED_COUNT" | tr -d ' ')
        
        if [ -n "$FIXED_COUNT" ] && [ "$FIXED_COUNT" -gt 0 ] 2>/dev/null; then
            echo -e "${GREEN}✓ Fixed $FIXED_COUNT linting issue(s)${NC}"
            FIXES_APPLIED=$((FIXES_APPLIED + FIXED_COUNT))
        else
            # Show summary of remaining issues
            REMAINING=$(grep -c "Found.*error" /tmp/ruff-fix.log 2>/dev/null || echo "0")
            if [ "$REMAINING" -gt 0 ]; then
                echo -e "${YELLOW}⚠ Some issues require manual fixes${NC}"
            else
                echo -e "${GREEN}✓ Linting fixes applied${NC}"
            fi
        fi
    fi
    cd "$PROJECT_ROOT"
    echo ""
fi

# 2. Auto-format code
if [ "$AUTO_FORMAT" = true ]; then
    echo -e "${BLUE}[2/2] Auto-formatting code...${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$BACKEND_DIR"
    FORMAT_OUTPUT=$("$VENV_BIN/ruff" format . 2>&1)
    FORMATTED_COUNT=$(echo "$FORMAT_OUTPUT" | grep -c "reformatted" || echo "0")
    FORMATTED_COUNT=$(echo "$FORMATTED_COUNT" | tr -d ' ')
    
    if [ -n "$FORMATTED_COUNT" ] && [ "$FORMATTED_COUNT" -gt 0 ] 2>/dev/null; then
        echo -e "${GREEN}✓ Reformatted $FORMATTED_COUNT file(s)${NC}"
        FIXES_APPLIED=$((FIXES_APPLIED + FORMATTED_COUNT))
    else
        echo -e "${GREEN}✓ Code is already properly formatted${NC}"
    fi
    cd "$PROJECT_ROOT"
    echo ""
fi

# Summary
echo -e "${BLUE}========================================${NC}"
if [ $FIXES_APPLIED -gt 0 ]; then
    echo -e "${GREEN}✓ Applied $FIXES_APPLIED fix(es)${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Review changes: git diff"
    echo "  2. Test your code: python -m pytest (if tests exist)"
    echo "  3. Run checks again: bash scripts/33-check-code-quality.sh"
else
    echo -e "${GREEN}✓ No fixes needed - code is clean!${NC}"
fi

exit 0

