# Environment Variables Reference

Complete reference for all environment variables used across the three Clockify add-on services.

---

## Table of Contents

- [PostgreSQL Configuration](#postgresql-configuration)
- [API Studio Configuration](#api-studio-configuration)
- [Universal Webhook Configuration](#universal-webhook-configuration)
- [Clockify Add-on Configuration](#clockify-addon-configuration)
- [Shared Configuration](#shared-configuration)
- [Quick Reference](#quick-reference)
- [Production Recommendations](#production-recommendations)

---

## PostgreSQL Configuration

Used by the PostgreSQL Docker container to initialize the database.

| Variable | Required | Default | Description | Production Value |
|----------|----------|---------|-------------|------------------|
| `POSTGRES_USER` | Yes | `clockify` | PostgreSQL username | `clockify` |
| `POSTGRES_PASSWORD` | Yes | `changeme_in_production` | PostgreSQL password | Generate strong password (`openssl rand -base64 32`) |
| `POSTGRES_DB` | No | `clockify` | Default database (init-db.sh creates service-specific DBs) | `clockify` |

**Example:**
```bash
POSTGRES_USER=clockify
POSTGRES_PASSWORD=a8f3k2j9d0s1l4m6n7p8q9r0t1u2v3w4x5y6z7
POSTGRES_DB=clockify
```

---

## API Studio Configuration

Service listening on port **8000**. Targets STANDARD tier Clockify workspaces.

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_STUDIO_DB_URL` | Yes | `sqlite+aiosqlite:///./api_studio.db` | Database connection string (SQLAlchemy format) |

**Development:**
```bash
API_STUDIO_DB_URL=sqlite+aiosqlite:///./api_studio.db
```

**Production:**
```bash
API_STUDIO_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/api_studio
```

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_STUDIO_ADDON_KEY` | No | `clockify-api-studio` | Unique identifier for the add-on |
| `API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION` | No | `true` | Enforce Clockify webhook signature verification (HMAC-SHA256) |

**Production:**
```bash
API_STUDIO_ADDON_KEY=clockify-api-studio
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true
```

### Bootstrap Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_STUDIO_BOOTSTRAP_MAX_RPS` | No | `25` | Maximum requests per second during bootstrap (rate limiting) |
| `API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS` | No | `false` | Include computationally expensive endpoints in bootstrap (tags, custom fields) |

**Example:**
```bash
API_STUDIO_BOOTSTRAP_MAX_RPS=25
API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS=false
```

### Data Retention

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS` | No | `90` | Days to retain webhook event logs (0 = unlimited) |
| `API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS` | No | `30` | Days to retain flow execution history (0 = unlimited) |

**Example:**
```bash
API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=90
API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS=30
```

---

## Universal Webhook Configuration

Service listening on port **8001**. Targets ENTERPRISE tier Clockify workspaces with advanced features.

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNIVERSAL_WEBHOOK_DB_URL` | Yes | `sqlite+aiosqlite:///./universal_webhook.db` | Database connection string (SQLAlchemy format) |

**Development:**
```bash
UNIVERSAL_WEBHOOK_DB_URL=sqlite+aiosqlite:///./universal_webhook.db
```

**Production:**
```bash
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/universal_webhook
```

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNIVERSAL_WEBHOOK_PORT` | No | `8001` | HTTP port for the service |
| `UNIVERSAL_WEBHOOK_ADDON_KEY` | No | `universal-webhook-api` | Unique identifier for the add-on |
| `UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION` | No | `true` | Enforce Clockify webhook signature verification |

**Production:**
```bash
UNIVERSAL_WEBHOOK_PORT=8001
UNIVERSAL_WEBHOOK_ADDON_KEY=universal-webhook-api
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true
```

### Bootstrap Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UW_BOOTSTRAP_MAX_RPS` | No | `25` | Maximum requests per second during bootstrap |
| `UW_BOOTSTRAP_INCLUDE_HEAVY` | No | `false` | Include heavy endpoints (tags, custom fields, expenses) |
| `UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES` | No | `false` | Include time entries in bootstrap (can be very large) |
| `UW_BOOTSTRAP_TIME_ENTRY_DAYS` | No | `30` | Number of days of time entries to fetch (if enabled) |
| `UW_BOOTSTRAP_MAX_PAGES` | No | `200` | Maximum pages to fetch per endpoint during bootstrap |

**Example:**
```bash
UW_BOOTSTRAP_MAX_RPS=25
UW_BOOTSTRAP_INCLUDE_HEAVY=false
UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES=false
UW_BOOTSTRAP_TIME_ENTRY_DAYS=30
UW_BOOTSTRAP_MAX_PAGES=200
```

### Webhook Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UW_ENABLE_CUSTOM_WEBHOOKS` | No | `true` | Allow registration of custom (non-Clockify) webhooks |
| `UW_WEBHOOK_LOG_RETENTION_DAYS` | No | `90` | Days to retain webhook event logs |

**Example:**
```bash
UW_ENABLE_CUSTOM_WEBHOOKS=true
UW_WEBHOOK_LOG_RETENTION_DAYS=90
```

### Flow Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UW_ENABLE_FLOWS` | No | `true` | Enable no-code flow engine |
| `UW_ENABLE_GENERIC_HTTP_ACTIONS` | No | `false` | Allow flows to make HTTP requests to arbitrary domains (security risk) |
| `UW_FLOW_EXECUTION_RETENTION_DAYS` | No | `90` | Days to retain flow execution history |

**Example:**
```bash
UW_ENABLE_FLOWS=true
UW_ENABLE_GENERIC_HTTP_ACTIONS=false
UW_FLOW_EXECUTION_RETENTION_DAYS=90
```

### Data Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UW_CACHE_TTL_DAYS` | No | `7` | Time-to-live for cached entity data (from bootstrap) |

**Example:**
```bash
UW_CACHE_TTL_DAYS=7
```

---

## Clockify Add-on Configuration

Service listening on port **8002**. Production reference implementation with full feature set.

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `sqlite+aiosqlite:///./clockify_addon.db` | Database connection string (SQLAlchemy format) |

**Development:**
```bash
DATABASE_URL=sqlite+aiosqlite:///./clockify_addon.db
```

**Production:**
```bash
DATABASE_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/clockify_addon
```

### Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLOCKIFY_ADDON_BASE_URL` | No | `http://localhost:8002` | Public URL where this service is accessible (used for webhook registration) |
| `DEBUG` | No | `false` | Enable debug mode (verbose logging, development features) |
| `REQUIRE_SIGNATURE_VERIFICATION` | No | `true` | Enforce Clockify webhook signature verification (RS256 JWT or HMAC) |

**Production:**
```bash
CLOCKIFY_ADDON_BASE_URL=https://clockify-addon.yourdomain.com
DEBUG=false
REQUIRE_SIGNATURE_VERIFICATION=true
```

### Clockify API Endpoints

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLOCKIFY_API_BASE` | No | `https://api.clockify.me/api/v1` | Main Clockify API base URL |
| `CLOCKIFY_DEVELOPER_API_BASE` | No | `https://developer.clockify.me/api/v1` | Developer/add-on lifecycle API |
| `CLOCKIFY_PTO_API_BASE` | No | `https://pto.api.clockify.me/v1` | Paid Time Off API base URL |
| `CLOCKIFY_REPORTS_API_BASE` | No | `https://reports.api.clockify.me/v1` | Reports API base URL |

**Example:**
```bash
CLOCKIFY_API_BASE=https://api.clockify.me/api/v1
CLOCKIFY_DEVELOPER_API_BASE=https://developer.clockify.me/api/v1
CLOCKIFY_PTO_API_BASE=https://pto.api.clockify.me/v1
CLOCKIFY_REPORTS_API_BASE=https://reports.api.clockify.me/v1
```

### Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RATE_LIMIT_RPS` | No | `50` | Maximum requests per second per workspace (token bucket algorithm) |
| `RATE_LIMIT_ENABLED` | No | `true` | Enable rate limiting for Clockify API calls |

**Example:**
```bash
RATE_LIMIT_RPS=50
RATE_LIMIT_ENABLED=true
```

### Redis (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string for distributed caching/rate limiting |
| `USE_REDIS` | No | `false` | Enable Redis for caching and distributed rate limiting |

**Example:**
```bash
REDIS_URL=redis://redis-host:6379/0
USE_REDIS=true
```

### Bootstrap

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTO_BOOTSTRAP_ON_INSTALL` | No | `true` | Automatically trigger bootstrap job when add-on is installed |
| `BOOTSTRAP_BATCH_SIZE` | No | `10` | Number of items to process per batch during bootstrap |
| `BOOTSTRAP_MAX_RETRIES` | No | `3` | Maximum retries for failed bootstrap API calls |
| `BOOTSTRAP_MAX_PAGES` | No | `1000` | Maximum pages to fetch per endpoint during bootstrap |

**Example:**
```bash
AUTO_BOOTSTRAP_ON_INSTALL=true
BOOTSTRAP_BATCH_SIZE=10
BOOTSTRAP_MAX_RETRIES=3
BOOTSTRAP_MAX_PAGES=1000
```

### Payload Limits

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_CALL_MAX_PAYLOAD_BYTES` | No | `1048576` | Maximum payload size for API calls (1MB default) |
| `WEBHOOK_MAX_PAYLOAD_BYTES` | No | `5242880` | Maximum payload size for incoming webhooks (5MB default) |

**Example:**
```bash
API_CALL_MAX_PAYLOAD_BYTES=1048576
WEBHOOK_MAX_PAYLOAD_BYTES=5242880
```

### Webhook Retries

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_REQUEST_MAX_RETRIES` | No | `5` | Maximum retry attempts for failed webhook deliveries |
| `WEBHOOK_REQUEST_BACKOFF_BASE` | No | `0.5` | Base backoff time in seconds (exponential backoff) |
| `WEBHOOK_REQUEST_BACKOFF_CAP` | No | `5.0` | Maximum backoff time in seconds |

**Example:**
```bash
WEBHOOK_REQUEST_MAX_RETRIES=5
WEBHOOK_REQUEST_BACKOFF_BASE=0.5
WEBHOOK_REQUEST_BACKOFF_CAP=5.0
```

### Security (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_HMAC_SECRET` | No | (none) | HMAC secret for legacy webhook signature verification (fallback if RS256 fails) |
| `CLOCKIFY_JWKS_URL` | No | `https://api.clockify.me/.well-known/jwks.json` | URL to fetch JWKS for RS256 JWT verification |
| `CLOCKIFY_ENVIRONMENT` | No | `prod` | Clockify environment (prod, staging, dev) |

**Example:**
```bash
WEBHOOK_HMAC_SECRET=your-hmac-secret-here
CLOCKIFY_JWKS_URL=https://api.clockify.me/.well-known/jwks.json
CLOCKIFY_ENVIRONMENT=prod
```

---

## Shared Configuration

Variables used by multiple services or shared infrastructure.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLOCKIFY_API_BASE_URL` | No | `https://api.clockify.me` | Clockify API base URL (without /api/v1) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

**Example:**
```bash
CLOCKIFY_API_BASE_URL=https://api.clockify.me
LOG_LEVEL=INFO
```

---

## Quick Reference

### Minimal Development Setup

```bash
# Copy template
cp .env.example .env

# Use defaults (SQLite databases, no changes needed)
docker-compose up -d
```

### Minimal Production Setup

```bash
# PostgreSQL
POSTGRES_PASSWORD=<generated-strong-password>

# API Studio
API_STUDIO_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/api_studio
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true

# Universal Webhook
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/universal_webhook
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true

# Clockify Add-on
DATABASE_URL=postgresql+asyncpg://clockify:<password>@postgres:5432/clockify_addon
CLOCKIFY_ADDON_BASE_URL=https://clockify-addon.yourdomain.com
DEBUG=false
REQUIRE_SIGNATURE_VERIFICATION=true

# Shared
LOG_LEVEL=INFO
```

---

## Production Recommendations

### Security

1. **Database Passwords**
   - Generate strong passwords: `openssl rand -base64 32`
   - Never commit `.env` to version control
   - Rotate credentials regularly

2. **Signature Verification**
   - ALWAYS set to `true` in production:
     - `API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true`
     - `UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true`
     - `REQUIRE_SIGNATURE_VERIFICATION=true`

3. **Debug Mode**
   - Disable in production: `DEBUG=false`
   - Use `LOG_LEVEL=INFO` (not DEBUG) in production

4. **Base URLs**
   - Update `CLOCKIFY_ADDON_BASE_URL` to your public domain
   - Use HTTPS with valid SSL certificates

### Performance

1. **Rate Limiting**
   - Default 50 RPS is conservative
   - Increase if Clockify allows: `RATE_LIMIT_RPS=100`
   - Monitor API quota usage in Clockify dashboard

2. **Bootstrap Settings**
   - Start conservative, increase if needed:
     - `BOOTSTRAP_MAX_PAGES=200` (not 1000)
     - `UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES=false` (time entries can be very large)
   - Adjust `BOOTSTRAP_MAX_RPS` based on Clockify rate limits

3. **Data Retention**
   - Reduce retention for large workspaces to save disk space:
     - `API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=30`
     - `UW_FLOW_EXECUTION_RETENTION_DAYS=30`

4. **Redis**
   - Enable for multi-instance deployments:
     - `USE_REDIS=true`
     - `REDIS_URL=redis://redis-host:6379/0`
   - Not needed for single-instance deployments

### Monitoring

1. **Logging**
   - `LOG_LEVEL=INFO` for production
   - `LOG_LEVEL=DEBUG` only for troubleshooting
   - Ship logs to external service (Datadog, Splunk, ELK)

2. **Metrics**
   - All services expose Prometheus metrics at `/metrics`
   - Set up Prometheus scraping (see [DEPLOYMENT.md](DEPLOYMENT.md))

3. **Health Checks**
   - Configure load balancer to use:
     - Liveness: `/healthz` (process alive?)
     - Readiness: `/ready` (can serve traffic?)

### Storage

1. **Database Sizing**
   - Start with 20 GB volume for PostgreSQL
   - Monitor disk usage (webhook logs, flow executions, entity cache)
   - Adjust retention settings if disk fills up

2. **Backup Strategy**
   - Daily automated backups: `pg_dumpall`
   - Store backups off-server (S3, cloud storage)
   - Test restore procedure regularly

---

## Environment Variable Priority

Configuration sources (highest to lowest priority):

1. **Environment variables** (set in shell or Docker)
2. **`.env` file** (loaded by docker-compose)
3. **Default values** (hardcoded in config.py files)

---

**Last Updated:** 2025-01-29
**Version:** 1.0.0

For deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).
For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
