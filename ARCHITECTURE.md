# System Architecture

## Overview

This repository contains **three production-ready Clockify add-ons** built in Python, sharing common infrastructure and deployed as microservices. All services are containerized, fully tested, and ready for production deployment.

---

## Services

### 1. API Studio (Port 8000)

**Target:** STANDARD tier Clockify workspaces
**Location:** `/api_studio/`

**Capabilities:**
- Lifecycle management (install/uninstall/settings updates)
- Webhook receiver (12 common events: TIME_ENTRY, PROJECT, CLIENT, TAG)
- Bootstrap engine (auto-fetch workspace data on install)
- No-code flow engine
- API Explorer (safe GET operations only)
- Metrics & health endpoints (`/healthz`, `/ready`, `/metrics`)

**Database:** `api_studio` (PostgreSQL in production)

**Key Files:**
- `api_studio/main.py:118` - FastAPI application entrypoint
- `api_studio/config.py` - Configuration with Pydantic settings
- `api_studio/models.py` - SQLAlchemy async models
- `api_studio/Dockerfile` - Multi-stage production build

**Deployment:**
```bash
docker-compose up api_studio
# OR
uvicorn api_studio.main:app --host 0.0.0.0 --port 8000
```

---

### 2. Universal Webhook (Port 8001)

**Target:** ENTERPRISE tier Clockify workspaces
**Location:** `/universal_webhook/`

**Capabilities:**
- All API Studio features
- Universal webhook ingestion (50+ Clockify events + custom webhooks)
- Enhanced bootstrap (configurable heavy endpoints, time entries)
- Advanced API Explorer (all operations, not just GET)
- Generic HTTP actions in flows
- Comprehensive observability (structured logging, metrics, health checks)

**Database:** `universal_webhook` (PostgreSQL in production)

**Key Files:**
- `universal_webhook/main.py:122` - FastAPI application entrypoint
- `universal_webhook/config.py` - Extended configuration
- `universal_webhook/models.py` - Enhanced models with caching
- `universal_webhook/Dockerfile` - Multi-stage production build

**Deployment:**
```bash
docker-compose up universal_webhook
# OR
uvicorn universal_webhook.main:app --host 0.0.0.0 --port 8001
```

---

### 3. Clockify Python Addon (Port 8002)

**Target:** Production reference implementation
**Location:** `/clockify-python-addon/`

**Capabilities:**
- Full lifecycle management
- 50 webhook events (complete Clockify coverage)
- 19 API scopes (full read/write access)
- Universal bootstrap with configurable pagination
- API Studio/Explorer for any operation
- Production hardening (RS256 JWT, JWKS, HMAC fallback)
- Redis support for distributed caching/rate limiting

**Database:** `clockify_addon` (PostgreSQL in production)

**Key Files:**
- `clockify-python-addon/app/main.py` - FastAPI application
- `clockify-python-addon/app/config.py` - Comprehensive settings
- `clockify-python-addon/Dockerfile` - Production-hardened build
- `clockify-python-addon/docker-compose.yml` - Development setup

**Deployment:**
```bash
docker-compose up clockify_addon
# OR
cd clockify-python-addon && docker-compose up
```

---

## Shared Infrastructure

### Clockify Core (`/clockify_core/`)

Common modules used by all services:

| Module | Purpose |
|--------|---------|
| `clockify_client.py` | Async HTTP client with retry logic and exponential backoff |
| `openapi_loader.py` | Endpoint discovery from OpenAPI spec |
| `rate_limiter.py` | Token bucket rate limiting (default: 50 RPS) |
| `metrics.py` | Prometheus metrics collector |
| `retention.py` | Data retention cleanup utilities |
| `security.py` | Signature verification (RS256 + HMAC) |
| `config.py` | Base configuration class (`BaseClockifySettings`) |

**Import pattern:**
```python
from clockify_core import get_metrics_collector, run_retention_cleanup
from clockify_core.rate_limiter import RateLimiter
from clockify_core.config import BaseClockifySettings
```

---

### Database

**Production:** Single PostgreSQL 14+ instance with 3 separate databases
- `api_studio` - API Studio service data
- `universal_webhook` - Universal Webhook service data
- `clockify_addon` - Clockify Add-on service data

**Development:** SQLite files (one per service)
- `api_studio.db`
- `universal_webhook.db`
- `clockify_addon.db`

**Migrations:** Alembic with environment-based targeting
- Single alembic config at `/alembic/`
- Target specific database via `DATABASE_URL` environment variable
- Each service runs migrations on startup

**Connection:**
```python
# api_studio/db.py
engine = create_async_engine(settings.db_url, poolclass=NullPool)
```

---

### Testing

**Test Suites:**
- `/tests/` - Integration tests for api_studio + universal_webhook (21 tests)
- `/clockify-python-addon/tests/` - Comprehensive unit/integration tests (49 tests)

**Total:** 70 tests (100% pass rate required)

**Test Execution:**
```bash
# Run all tests locally
./scripts/test_all.sh

# Run with Docker
docker-compose -f docker-compose.test.yml run --rm test-runner

# Run in CI/CD
# Triggered automatically on PR/push via GitHub Actions
```

**CI:** GitHub Actions runs all tests on every PR/push to main

---

## Technology Stack

### Runtime
- **Python 3.11** (3.12 compatible, 3.14 experimental)
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **Gunicorn** - Production WSGI server (multi-worker support)

### Database
- **PostgreSQL 14+** (production)
- **SQLite** (development)
- **SQLAlchemy 2.x** - Async ORM
- **Alembic** - Database migrations
- **asyncpg** - PostgreSQL async driver
- **aiosqlite** - SQLite async driver

### HTTP
- **httpx** - Async HTTP client
- **tenacity** - Retry logic with exponential backoff

### Data
- **Pydantic v2** - Data validation and settings management
- **jsonpath-ng** - Flow condition evaluation

### Observability
- **Prometheus** - Metrics (via `/metrics` endpoint)
- **structlog** - Structured logging (clockify-python-addon)
- Standard **logging** module (api_studio, universal_webhook)

---

## Security

### Authentication & Authorization
- **RS256 JWT verification** (clockify-python-addon)
- **JWKS key rotation** support
- **Workspace isolation** - All DB queries scoped by workspace ID

### Signature Verification
- **Clockify webhook signatures** (`Clockify-Signature` header)
- **HMAC-SHA256 fallback** (optional, for legacy support)
- **Configurable enforcement** (`REQUIRE_SIGNATURE_VERIFICATION`)

### Rate Limiting
- **Token bucket algorithm**
- **50 RPS default** (configurable)
- **Per-workspace isolation** (prevents cross-tenant abuse)

### API Protection
- **Domain allowlisting** (only approved Clockify domains)
- **Payload size limits** (1MB API calls, 5MB webhooks)
- **Input validation** (Pydantic models enforce schema)

**Security Configuration:**
```bash
# REQUIRED in production
REQUIRE_SIGNATURE_VERIFICATION=true
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true
```

---

## Observability

### Metrics

**Prometheus format** at `/metrics` for all services:
- `addon_uptime_seconds` - Service uptime
- `webhooks_received_total` - Webhook counter
- `webhooks_received_{event_type}` - Per-event counters
- `flows_executed_total` - Flow execution counter
- `flows_executed_completed` - Successful flows
- `flows_executed_failed` - Failed flows
- `api_calls_total` - API call counter
- `bootstrap_completed` - Bootstrap success counter
- `bootstrap_errors` - Bootstrap failure counter

**Scraping:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'clockify-addons'
    static_configs:
      - targets: ['localhost:8000', 'localhost:8001', 'localhost:8002']
    metrics_path: '/metrics'
```

### Logging

**Structured logs** with:
- **JSON format** (production)
- **Correlation IDs** (`X-Request-ID` header)
- **PII redaction** (automatic scrubbing of tokens/secrets)
- **Log levels:** DEBUG, INFO, WARNING, ERROR

**Configuration:**
```bash
LOG_LEVEL=INFO  # Use DEBUG for troubleshooting
```

### Health Checks

| Endpoint | Type | Purpose | Status Codes |
|----------|------|---------|--------------|
| `/healthz` | Liveness | Is process alive? | 200, 503 |
| `/ready` | Readiness | Can serve traffic? | 200, 503 |
| `/health` | Legacy | Clockify addon health | 200, 503 |

**Kubernetes/Docker Compose:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s  # Allow time for migrations
```

---

## Data Flow

### 1. Installation

```
Clockify → POST /lifecycle/installed (JWT in body)
  ↓
Service verifies signature
  ↓
Stores installation (workspace_id, addon_token, settings)
  ↓
Registers webhooks with Clockify API
  ↓
Triggers bootstrap job (async)
  ↓
Returns 200 OK
```

### 2. Webhook Processing

```
Clockify → POST /webhooks/{category} (event payload + signature header)
  ↓
Service verifies Clockify-Signature header
  ↓
Checks for duplicate (event_id in webhook_events table)
  ↓
Logs event to database
  ↓
Evaluates flows (if any match the event)
  ↓
Executes flow actions (API calls, HTTP requests)
  ↓
Returns 200 OK
```

### 3. Bootstrap

```
User installs addon
  ↓
Service creates BootstrapJob record
  ↓
Loads OpenAPI spec → identifies safe GET endpoints
  ↓
For each endpoint:
  ├─ Rate-limited HTTP GET (25 RPS default)
  ├─ Paginate until < 50 items or max_pages reached
  ├─ Store results in EntityCache table
  └─ Update BootstrapJob progress
  ↓
Marks BootstrapJob as completed
```

### 4. API Calls

```
User → POST /api-call OR /ui/api-explorer/execute
  ↓
Service validates operation against OpenAPI spec
  ↓
Injects workspace context (X-Api-Key, workspace_id in path)
  ↓
Rate limiting check (50 RPS token bucket)
  ↓
Calls Clockify API via httpx (with retries)
  ↓
Logs call to APICall table (endpoint, duration, status)
  ↓
Returns response + metrics
```

---

## Configuration

### Environment Variables

**Service-specific prefixes:**
- `API_STUDIO_*` - API Studio settings
- `UW_*` or `UNIVERSAL_WEBHOOK_*` - Universal Webhook settings
- No prefix or `CLOCKIFY_*` - Clockify Addon settings

**Shared variables:**
- `LOG_LEVEL` - Logging verbosity (INFO, DEBUG, ERROR)
- `CLOCKIFY_API_BASE_URL` - Clockify API base URL
- `POSTGRES_USER`, `POSTGRES_PASSWORD` - Database credentials

**Configuration files:**
- `.env` - Local overrides (gitignored)
- `.env.example` - Template with defaults and comments
- `ENV_VARS_REFERENCE.md` - Complete documentation

**Priority:**
1. Environment variables
2. .env file
3. Default values in code

---

## Deployment

### Local Development

```bash
# Clone and setup
git clone <repo-url>
cd pyddon
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:8000/ready
curl http://localhost:8001/ready
curl http://localhost:8002/health
```

### Production Deployment

```bash
# Update .env with production values
POSTGRES_PASSWORD=<strong-password>
API_STUDIO_DB_URL=postgresql+asyncpg://...
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://...
DATABASE_URL=postgresql+asyncpg://...

# Build and start
docker-compose build
docker-compose up -d

# Run migrations (if not auto-run)
./scripts/run_migrations.sh

# Verify deployment
docker-compose ps
docker-compose logs --tail=100
```

### Reverse Proxy (Production)

```nginx
# /etc/nginx/sites-available/clockify-addons
server {
    listen 443 ssl http2;
    server_name api-studio.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## CI/CD

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `test.yml` | PR, push to main/develop | Run all 70 tests |
| `build.yml` | PR, push to main, tags | Build Docker images, push to GHCR |

**Automated checks:**
- ✅ Python 3.11 compatibility
- ✅ All tests passing
- ✅ Docker builds succeed
- ✅ Multi-platform images (amd64, arm64)

**Image registry:** GitHub Container Registry (ghcr.io)

**Image naming:**
- `ghcr.io/<owner>/clockify-api_studio:latest`
- `ghcr.io/<owner>/clockify-universal_webhook:latest`
- `ghcr.io/<owner>/clockify-clockify_addon:latest`

---

## Performance Characteristics

### Request Latency
- Health checks: < 10ms
- Webhook processing: < 50ms (without flows)
- Bootstrap (full workspace): 30s - 5min (depends on data size)
- API calls: 100-500ms (depends on Clockify API)

### Throughput
- Max 50 RPS per workspace (rate limiter)
- Can handle 100+ concurrent workspaces

### Resource Usage
- Memory: 100-300 MB per service
- CPU: < 5% idle, 20-40% during bootstrap
- Disk: 10-50 GB (depends on retention settings)

---

## Future Enhancements

1. **Multi-tenancy:** Separate databases per workspace (enterprise scale)
2. **Redis:** Distributed caching and rate limiting
3. **Webhooks:** Retry with exponential backoff for failed deliveries
4. **Metrics:** Grafana dashboards and alerting
5. **Logging:** ELK/Datadog/Splunk integration
6. **Horizontal Scaling:** Multiple instances behind load balancer
7. **Database Sharding:** Split workspaces across database instances

---

## Support & Documentation

- **Deployment Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Environment Variables:** [ENV_VARS_REFERENCE.md](ENV_VARS_REFERENCE.md)
- **Quickstart:** [QUICKSTART.md](QUICKSTART.md)
- **API Documentation:** Auto-generated at `/docs` (FastAPI Swagger UI)

---

**Last Updated:** 2025-01-29
**Version:** 1.0.0
**Status:** ✅ Production Ready
