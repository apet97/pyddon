#!/bin/bash
# Migration script for Clockify Add-ons
# Runs database migrations for all services

set -e

echo "🚀 Running database migrations for all Clockify services..."

echo ""
echo "🔧 Running API Studio migrations..."
docker-compose exec api_studio sh -c "DATABASE_URL=\$API_STUDIO_DB_URL alembic upgrade head" || echo "⚠️  API Studio migration skipped or failed"

echo ""
echo "🔧 Running Universal Webhook migrations..."
docker-compose exec universal_webhook sh -c "DATABASE_URL=\$UNIVERSAL_WEBHOOK_DB_URL alembic upgrade head" || echo "⚠️  Universal Webhook migration skipped or failed"

echo ""
echo "🔧 Running Clockify Addon migrations..."
docker-compose exec clockify_addon sh -c "DATABASE_URL=\$DATABASE_URL alembic upgrade head" || echo "⚠️  Clockify Addon migration skipped or failed"

echo ""
echo "✅ All database migrations completed!"