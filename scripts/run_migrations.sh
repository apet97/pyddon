#!/bin/bash
# Run database migrations for all services
# This script runs migrations sequentially for each service's database

set -e

echo "========================================="
echo "Running Database Migrations"
echo "========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get database URLs from environment or use defaults
API_STUDIO_DB_URL=${API_STUDIO_DB_URL:-sqlite+aiosqlite:///./api_studio.db}
UNIVERSAL_WEBHOOK_DB_URL=${UNIVERSAL_WEBHOOK_DB_URL:-sqlite+aiosqlite:///./universal_webhook.db}
CLOCKIFY_ADDON_DB_URL=${CLOCKIFY_ADDON_DB_URL:-sqlite+aiosqlite:///./clockify_addon.db}

# API Studio migrations
echo ""
echo -e "${BLUE}1. Migrating api_studio database...${NC}"
export DATABASE_URL="$API_STUDIO_DB_URL"
alembic upgrade head
echo -e "${GREEN}✓ API Studio migrations completed${NC}"

# Universal Webhook migrations
echo ""
echo -e "${BLUE}2. Migrating universal_webhook database...${NC}"
export DATABASE_URL="$UNIVERSAL_WEBHOOK_DB_URL"
alembic upgrade head
echo -e "${GREEN}✓ Universal Webhook migrations completed${NC}"

# Clockify Addon migrations (uses its own alembic in subdirectory)
echo ""
echo -e "${BLUE}3. Migrating clockify_addon database...${NC}"
cd clockify-python-addon
export DATABASE_URL="$CLOCKIFY_ADDON_DB_URL"
alembic upgrade head
cd ..
echo -e "${GREEN}✓ Clockify Addon migrations completed${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}All migrations completed successfully!${NC}"
echo "========================================="
