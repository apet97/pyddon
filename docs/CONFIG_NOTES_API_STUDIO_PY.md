# Config Notes – Clockify API Studio (Python)

## Environment Variables

### Server
- **APP_PORT**: Port to run FastAPI on (default: 8000)

### Database
- **API_STUDIO_DB_URL**: Database URL for SQLAlchemy
  - Default: `sqlite+aiosqlite:///./api_studio.db`
  - Production: `postgresql+asyncpg://user:pass@host/db`

### Clockify API
- **CLOCKIFY_API_BASE_URL**: Base URL for Clockify API
  - Default: `https://api.clockify.me`
  - Development: `https://developer.clockify.me`

### Bootstrap Settings
- **API_STUDIO_BOOTSTRAP_MAX_RPS**: Max requests per second during bootstrap (default: 25)
- **API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS**: Include heavy report endpoints (default: false)

### Data Retention (New)
- **API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS**: Days to retain webhook logs (default: 90, 0=disable)
- **API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS**: Days to retain flow execution logs (default: 30, 0=disable)

## Runtime Configuration

Installation data (workspaceId, addonId, apiUrl, X-Addon-Token, settings) is stored in the database
and used to configure the Clockify client per workspace.

## Production Deployment

### Required Changes for Production
1. Use PostgreSQL instead of SQLite:
   ```bash
   API_STUDIO_DB_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```

2. Configure retention based on data volume:
   ```bash
   API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=90
   API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS=30
   ```

3. Adjust rate limiting for your load:
   ```bash
   API_STUDIO_BOOTSTRAP_MAX_RPS=25  # Lower for rate-sensitive workspaces
   ```

## Monitoring

- **Health endpoint**: `GET /healthz` - Returns database status
- **Metrics endpoint**: `GET /metrics` - Prometheus format metrics

## Security Notes

- Never log `X-Addon-Token` or `addon_token` values
- All logs automatically redact sensitive data
- HTTP client restricted to approved Clockify hosts only
