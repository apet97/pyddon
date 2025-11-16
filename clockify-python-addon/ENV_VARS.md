# Environment Variables

This document lists all environment variables used by the Clockify Python Addon. All variables can be set in a `.env` file or as system environment variables.

## Server Configuration

### `BASE_URL`
- **Description**: Public URL where your addon is hosted
- **Required**: Yes
- **Example**: `https://your-addon-domain.com`
- **Note**: Must be accessible from Clockify servers for lifecycle and webhook callbacks

### `HOST`
- **Description**: Host address for the server to bind to
- **Required**: No
- **Default**: `0.0.0.0`
- **Example**: `0.0.0.0`

### `PORT`
- **Description**: Port number for the server
- **Required**: No
- **Default**: `8000`
- **Example**: `8000`

### `DEBUG`
- **Description**: Enable debug mode (verbose logging, auto-reload)
- **Required**: No
- **Default**: `false`
- **Example**: `true` or `false`
- **Note**: Set to `false` in production

## Database

### `DATABASE_URL`
- **Description**: Database connection string
- **Required**: Yes
- **Default**: `sqlite+aiosqlite:///./clockify_addon.db`
- **Example (SQLite)**: `sqlite+aiosqlite:///./clockify_addon.db`
- **Example (PostgreSQL)**: `postgresql+asyncpg://user:password@localhost:5432/clockify_addon`
- **Note**: Use PostgreSQL in production for better performance and reliability

## Security

### `CLOCKIFY_JWKS_URL`
- **Description**: Optional override for Clockify's JWKS endpoint (auto-selected when unset)
- **Required**: No
- **Default**: `None` (auto-selects prod/dev based on `CLOCKIFY_ENVIRONMENT`)
- **Example**: `https://developer.clockify.me/.well-known/jwks.json`
- **Note**: Only set when pointing at a custom Clockify environment

### `REQUIRE_SIGNATURE_VERIFICATION`
- **Description**: Enable JWT/signature verification for lifecycle and webhook events
- **Required**: No
- **Default**: `true`
- **Example**: `true` or `false`
- **Note**: MUST be `true` in production; set to `false` only for local development

### `CLOCKIFY_ENVIRONMENT`
- **Description**: Clockify environment hint used to auto-select JWKS (`prod` or `dev`)
- **Required**: No
- **Default**: `prod`
- **Example**: `dev`
- **Note**: Set to `dev` when targeting developer.clockify.me tenants

### `CLOCKIFY_ALLOWED_API_DOMAINS`
- **Description**: Comma-separated list of host or wildcard patterns allowed for API Studio outbound calls
- **Required**: No
- **Default**: `*.clockify.me,*.clockify.com,developer.clockify.me,api.clockify.me,reports.api.clockify.me,pto.api.clockify.me`
- **Example**: `*.clockify.me,internal.clockify.net`
- **Note**: Requests to hosts outside this list are rejected with a validation error. Comma-separated strings are automatically parsed into a list.

### `API_CALL_MAX_PAYLOAD_BYTES`
- **Description**: Maximum body size (in bytes) accepted by `/api-call`
- **Required**: No
- **Default**: `1048576`
- **Example**: `2097152`

### `WEBHOOK_MAX_PAYLOAD_BYTES`
- **Description**: Maximum webhook payload size enforced on `/webhooks/*`
- **Required**: No
- **Default**: `5242880`
- **Example**: `7340032`

### `WEBHOOK_REQUEST_MAX_RETRIES`
- **Description**: Number of attempts for Clockify webhook registration/deletion HTTP calls
- **Required**: No
- **Default**: `5`
- **Example**: `3`

### `WEBHOOK_REQUEST_BACKOFF_BASE`
- **Description**: Initial backoff delay (seconds) before retrying webhook HTTP calls
- **Required**: No
- **Default**: `0.5`
- **Example**: `1.0`

### `WEBHOOK_REQUEST_BACKOFF_CAP`
- **Description**: Maximum backoff delay (seconds) when retrying webhook HTTP calls
- **Required**: No
- **Default**: `5.0`
- **Example**: `10.0`

## Clockify API

### `CLOCKIFY_API_BASE`
- **Description**: Base URL for Clockify production API
- **Required**: No
- **Default**: `https://api.clockify.me/api/v1`
- **Example**: `https://api.clockify.me/api/v1`

### `CLOCKIFY_DEVELOPER_API_BASE`
- **Description**: Base URL for Clockify developer API
- **Required**: No
- **Default**: `https://developer.clockify.me/api/v1`
- **Example**: `https://developer.clockify.me/api/v1`

### `CLOCKIFY_PTO_API_BASE`
- **Description**: Base URL for Clockify PTO (time off) API
- **Required**: No
- **Default**: `https://pto.api.clockify.me/v1`
- **Example**: `https://pto.api.clockify.me/v1`

### `CLOCKIFY_REPORTS_API_BASE`
- **Description**: Base URL for Clockify Reports API
- **Required**: No
- **Default**: `https://reports.api.clockify.me/v1`
- **Example**: `https://reports.api.clockify.me/v1`

## Rate Limiting

### `RATE_LIMIT_RPS`
- **Description**: Maximum requests per second per workspace
- **Required**: No
- **Default**: `50`
- **Example**: `50`
- **Note**: Adjust based on your Clockify plan limits

### `RATE_LIMIT_ENABLED`
- **Description**: Enable rate limiting
- **Required**: No
- **Default**: `true`
- **Example**: `true` or `false`

## Redis (Optional)

### `REDIS_URL`
- **Description**: Redis connection URL for distributed rate limiting
- **Required**: No (required if `USE_REDIS=true`)
- **Default**: `redis://localhost:6379/0`
- **Example**: `redis://localhost:6379/0`

### `USE_REDIS`
- **Description**: Use Redis for distributed rate limiting and caching
- **Required**: No
- **Default**: `false`
- **Example**: `true` or `false`
- **Note**: Recommended for multi-instance deployments

## Logging

### `LOG_LEVEL`
- **Description**: Logging verbosity level
- **Required**: No
- **Default**: `INFO`
- **Example**: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- **Note**: Use `INFO` or `WARNING` in production

### `LOG_FORMAT`
- **Description**: Log output format
- **Required**: No
- **Default**: `json`
- **Example**: `json` or `text`
- **Note**: Use `json` in production for structured logging

## Bootstrap

### `AUTO_BOOTSTRAP_ON_INSTALL`
- **Description**: Automatically fetch workspace data on installation
- **Required**: No
- **Default**: `true`
- **Example**: `true` or `false`

### `BOOTSTRAP_BATCH_SIZE`
- **Description**: Number of endpoints to fetch concurrently during bootstrap
- **Required**: No
- **Default**: `10`
- **Example**: `10`
- **Note**: Lower values reduce load but increase bootstrap time

### `BOOTSTRAP_MAX_RETRIES`
- **Description**: Maximum retry attempts for failed bootstrap requests
- **Required**: No
- **Default**: `3`
- **Example**: `3`

### `BOOTSTRAP_MAX_PAGES`
- **Description**: Safety cap on pages fetched per endpoint during bootstrap (prevents runaway loops)
- **Required**: No
- **Default**: `1000`
- **Example**: `250`

## Addon Information

### `ADDON_KEY`
- **Description**: Unique addon identifier (must match manifest.json)
- **Required**: Yes
- **Default**: `clockify-python-addon`
- **Example**: `my-custom-addon-key`
- **Note**: Must match the `key` field in manifest.json

### `ADDON_NAME`
- **Description**: Human-readable addon name
- **Required**: No
- **Default**: `Clockify Python Addon Boilerplate`
- **Example**: `My Custom Clockify Integration`

### `ADDON_DESCRIPTION`
- **Description**: Short description of addon functionality
- **Required**: No
- **Default**: `Production-ready Clockify Add-on with full API integration`
- **Example**: `Time tracking automation and reporting`

### `ADDON_VENDOR_NAME`
- **Description**: Vendor/company name
- **Required**: No
- **Default**: `Your Company`
- **Example**: `Acme Corp`

### `ADDON_VENDOR_URL`
- **Description**: Vendor website URL
- **Required**: No
- **Default**: `https://your-company.com`
- **Example**: `https://acme-corp.com`

## Example .env File

```bash
# Production Example
BASE_URL=https://clockify-addon.acme-corp.com
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:password@db.acme-corp.com:5432/clockify
REQUIRE_SIGNATURE_VERIFICATION=true
CLOCKIFY_JWKS_URL=https://developer.clockify.me/.well-known/jwks.json
RATE_LIMIT_RPS=50
USE_REDIS=true
REDIS_URL=redis://redis.acme-corp.com:6379/0
LOG_LEVEL=INFO
LOG_FORMAT=json
ADDON_KEY=acme-clockify-integration
ADDON_NAME=Acme Clockify Integration
ADDON_VENDOR_NAME=Acme Corp
ADDON_VENDOR_URL=https://acme-corp.com
```

```bash
# Development Example
BASE_URL=http://localhost:8000
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./clockify_addon_dev.db
REQUIRE_SIGNATURE_VERIFICATION=false
RATE_LIMIT_ENABLED=false
LOG_LEVEL=DEBUG
LOG_FORMAT=text
AUTO_BOOTSTRAP_ON_INSTALL=false
```

## Security Best Practices

1. **Never commit `.env` files to version control**
2. **Ensure the Clockify JWKS host (`CLOCKIFY_JWKS_URL` or `CLOCKIFY_ENVIRONMENT`) is reachable and correct**
3. **Always enable signature verification** (`REQUIRE_SIGNATURE_VERIFICATION=true`) in production
4. **Use PostgreSQL** instead of SQLite for production deployments
5. **Enable Redis** for multi-instance deployments
6. **Use HTTPS** for all production `BASE_URL` values
7. **Rotate credentials (DB, Redis, addon token seeds) regularly**
8. **Monitor logs** for authentication failures and suspicious activity
