#!/bin/bash
# PostgreSQL initialization script
# Creates separate databases for each service on first startup

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create databases for each service
    CREATE DATABASE api_studio;
    CREATE DATABASE universal_webhook;
    CREATE DATABASE clockify_addon;

    -- Grant all privileges to the main user
    GRANT ALL PRIVILEGES ON DATABASE api_studio TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE universal_webhook TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE clockify_addon TO $POSTGRES_USER;

    -- Log successful creation
    SELECT 'Databases created successfully' AS status;
EOSQL

echo "✓ All 3 databases initialized: api_studio, universal_webhook, clockify_addon"
