#!/bin/bash
# Fix database file permissions for backend write access
# Run this on the server where the backend is running

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
DATABASE_DIR="$BACKEND_DIR/database"

echo -e "${GREEN}🔧 Database Permissions Fix Script${NC}"
echo "=========================================="

# Check if database directory exists
if [ ! -d "$DATABASE_DIR" ]; then
    echo -e "${YELLOW}Creating database directory...${NC}"
    mkdir -p "$DATABASE_DIR"
fi

# Check current permissions
echo -e "${YELLOW}Current database file permissions:${NC}"
ls -la "$DATABASE_DIR"/*.db 2>/dev/null || echo "No database files found"

# Fix permissions for database directory
echo -e "${YELLOW}Setting database directory permissions...${NC}"
chmod 755 "$DATABASE_DIR"
echo -e "${GREEN}✅ Database directory permissions set${NC}"

# Fix permissions for database files
echo -e "${YELLOW}Setting database file permissions...${NC}"
for db_file in "$DATABASE_DIR"/*.db; do
    if [ -f "$db_file" ]; then
        chmod 664 "$db_file"
        echo -e "${GREEN}✅ Fixed permissions for: $(basename "$db_file")${NC}"
    fi
done

# Check if running as a specific user (e.g., PM2)
if [ -n "$PM2_HOME" ] || command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}PM2 detected - checking process user...${NC}"
    PM2_USER=$(pm2 jlist 2>/dev/null | grep -o '"username":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")
    if [ -n "$PM2_USER" ] && [ "$PM2_USER" != "$USER" ]; then
        echo -e "${YELLOW}PM2 is running as user: $PM2_USER${NC}"
        echo -e "${YELLOW}Changing ownership to $PM2_USER...${NC}"
        sudo chown "$PM2_USER:$PM2_USER" "$DATABASE_DIR"/*.db 2>/dev/null || {
            echo -e "${RED}⚠️  Could not change ownership (may need sudo)${NC}"
            echo -e "${YELLOW}   Run manually: sudo chown $PM2_USER:$PM2_USER $DATABASE_DIR/*.db${NC}"
        }
    fi
fi

# Final check
echo -e "${YELLOW}Final database file permissions:${NC}"
ls -la "$DATABASE_DIR"/*.db 2>/dev/null || echo "No database files found"

echo -e "${GREEN}✅ Database permissions fix complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Restart the backend: pm2 restart alpaca-backend"
echo "2. Try uploading the CSV again"
echo "3. Check backend logs: pm2 logs alpaca-backend"

