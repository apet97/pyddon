# Clockify Add-ons (Python)

**✅ PRODUCTION-READY** | **Tests: 70/70 Passing** | **Security: Hardened** | **CI/CD: Automated**

Production-ready Clockify add-ons implemented in Python with comprehensive security, observability, and operational features. Fully containerized with Docker, CI/CD workflows, and production-grade deployment guides.

## 🚀 Quick Links

- **[Deployment Guide](DEPLOYMENT.md)** - Complete production deployment walkthrough
- **[Architecture Overview](ARCHITECTURE.md)** - System architecture and technology stack
- **[Environment Variables Reference](ENV_VARS_REFERENCE.md)** - Comprehensive configuration guide
- **[Production Hardening Summary](PRODUCTION_HARDENING_COMPLETE.md)** - Security & observability features
- **[Executive Summary](EXECUTIVE_SUMMARY.md)** - Business-level overview
- **[Security & Limits](docs/SECURITY_AND_LIMITS_API_STUDIO_PY.md)** - Detailed security posture

## 📦 What's Included

This repository contains **three production-ready Clockify add-ons** plus shared infrastructure:

1. **API Studio** (`/api_studio/`) - No-code API + webhook console (STANDARD plan) - Port 8000
2. **Universal Webhook** (`/universal_webhook/`) - Enterprise-grade universal webhook ingestion and automation (ENTERPRISE plan) - Port 8001
3. **Clockify Python Add-on** (`/clockify-python-addon/`) - Production reference implementation with full feature set - Port 8002
4. **Clockify Core** (`/clockify_core/`) - Shared modules (HTTP client, OpenAPI loader, rate limiter, security, metrics)

---

## 🎯 Add-ons

### 1. API Studio (`api_studio/`)
**For rapid prototyping and internal automation**

- **Plan**: STANDARD
- **Webhook Events**: 12 common events (TIME_ENTRY, PROJECT, CLIENT, TAG)
- **Scopes**: 7 resources (TIME_ENTRY, PROJECT, CLIENT, TAG, USER, CUSTOM_FIELDS, WORKSPACE)
- **Features**:
  - Lifecycle endpoints
  - Automatic GET bootstrap
  - Webhook receiver
  - No-code flow engine
  - API Explorer (safe GET operations)
  - JSON UI endpoints
  - Signature enforcement via `API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION` (default `true`). Keep enabled in production/staging; only disable in local testing environments because unsigned Clockify traffic is rejected otherwise.

### 2. Universal Webhook (`universal_webhook/`) ⭐
**Enterprise-grade automation platform**

- **Plan**: ENTERPRISE
- **Webhook Events**: ALL 50+ Clockify events + custom webhooks
- **Scopes**: ALL resources (READ + WRITE)
- **Features**:
  - Universal webhook ingestion (Clockify + custom sources)
  - Enhanced automatic GET bootstrap (configurable heavy endpoints, time entries)
  - API Explorer for ANY Clockify operation
  - Advanced no-code flows (with optional generic HTTP actions)
  - Comprehensive settings (14 fields across 4 sections)
  - Production-ready observability
  - Canonical manifest alignment via `clockify-python-addon/app/constants.py` ensuring every supported event/path and the full `CLOCKIFY_SCOPE_LIST` stay in sync between router, generated manifest, and `manifest.json`
  - Hardened security (workspace isolation, RS256 + JWKS verification, allowed domain enforcement, payload size limits, and per-workspace token-bucket rate limiting)
  - Signature enforcement via `UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION` (default `true`). This must remain enabled outside of tests; disabling it is a local-only escape hatch that bypasses Clockify's `Clockify-Signature` verification.

---

## 🏗️ Architecture

### Shared Core (`clockify_core/`)
Common functionality extracted for reuse:
- `ClockifyClient` - Async HTTP client with retry/backoff
- `OpenAPILoader` - Endpoint discovery from openapi.json
- `RateLimiter` - Token bucket rate limiting (50 RPS)
- `BaseClockifySettings` - Configuration base class

### Technology Stack
- **Python 3.11**
- **FastAPI** (async REST API)
- **httpx** (async HTTP client)
- **SQLAlchemy 2.x** + Alembic (async ORM + migrations)
- **SQLite** (dev) / **Postgres** (production)
- **Pydantic v2** (data validation)
- **jsonpath-ng** (flow condition evaluation)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip and virtualenv

### Installation

```bash
# Clone repository
cd /path/to/clockify-api-studio-py-kit

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head
```

### Run API Studio

```bash
# Start server (port 8000)
uvicorn api_studio.main:app --reload

# Verify
curl http://localhost:8000/healthz
# {"status":"ok"}
```

### Run Universal Webhook

```bash
# Start server (port 8001)
uvicorn universal_webhook.main:app --reload --port 8001

# Verify
curl http://localhost:8001/healthz
# {"status":"ok","service":"universal-webhook"}
```

---

## 🐍 Python & Testing

- **Supported Python**: The repo targets Python **3.11**. Python 3.12 works but is not part of the regression matrix yet. Python 3.14 (and newer) is still experimental because several dependencies (e.g., `uvloop`, `orjson`) do not publish official wheels—stick to 3.11 in production builds.
- **Root venv + tests**:
  ```bash
  python3.11 -m venv venv
  source venv/bin/activate
  pip install -e .
  ./venv/bin/python -m pytest tests -v
  ```
- **Add-on venv + tests**:
  ```bash
  cd clockify-python-addon
  python3.11 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ./venv/bin/python -m pytest tests -v
  ```
- Remember to deactivate each venv (`deactivate`) before switching between the root services and the add-on to avoid path confusion.

---

## 🧪 Testing

```bash
# Run all tests (70 tests total)
./scripts/test_all.sh

# Or run individually:

# Root tests (21 tests: api_studio + universal_webhook)
PYTHONPATH=. pytest tests/ -v

# Clockify add-on tests (49 tests)
cd clockify-python-addon && PYTHONPATH=. pytest tests/ -v

# Run with coverage
pytest tests/ --cov=api_studio --cov=universal_webhook --cov=clockify_core

# Run tests in Docker
docker-compose -f docker-compose.test.yml run --rm test-runner
```

**Current Status**: ✅ 70/70 tests passing (100%)
- 21 tests for API Studio + Universal Webhook
- 49 tests for Clockify Python Add-on
- **CI/CD**: Automated testing on every PR/push via GitHub Actions

---

## 📚 Documentation

### API Studio
- **Product Spec**: [`docs/clockify-api-studio-spec.md`](docs/clockify-api-studio-spec.md)
- **Architecture**: [`docs/ARCHITECTURE_API_STUDIO_PY.md`](docs/ARCHITECTURE_API_STUDIO_PY.md)
- **Implementation**: [`docs/IMPLEMENTATION_CHECKLIST_API_STUDIO_PY.md`](docs/IMPLEMENTATION_CHECKLIST_API_STUDIO_PY.md)
- **Security**: [`docs/SECURITY_AND_LIMITS_API_STUDIO_PY.md`](docs/SECURITY_AND_LIMITS_API_STUDIO_PY.md)
- **Status**: [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)

### Universal Webhook ⭐
- **Product Spec**: [`docs/clockify-universal-webhook-spec.md`](docs/clockify-universal-webhook-spec.md) 📖
- **Architecture**: [`docs/ARCHITECTURE_UNIVERSAL_WEBHOOK_PY.md`](docs/ARCHITECTURE_UNIVERSAL_WEBHOOK_PY.md) 🏗️
- **Implementation**: [`docs/IMPLEMENTATION_CHECKLIST_UNIVERSAL_WEBHOOK_PY.md`](docs/IMPLEMENTATION_CHECKLIST_UNIVERSAL_WEBHOOK_PY.md) ✅
- **Quickstart**: [`docs/QUICKSTART_UNIVERSAL_WEBHOOK.md`](docs/QUICKSTART_UNIVERSAL_WEBHOOK.md) 🚀
- **Progress**: [`UNIVERSAL_WEBHOOK_PROGRESS.md`](UNIVERSAL_WEBHOOK_PROGRESS.md)
- **Summary**: [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) 📊

### General
- **Clockify Add-on Guide**: [`docs/Clockify_Addon_Guide.md`](docs/Clockify_Addon_Guide.md)
- **Webhook Samples**: [`docs/Clockify_Webhook_JSON_Samples.md`](docs/Clockify_Webhook_JSON_Samples.md)
- **OpenAPI Spec**: [`docs/openapi.json`](docs/openapi.json)

---

## 📦 Project Structure

```
clockify-api-studio-py-kit/
├── clockify_core/          # Shared core modules
│   ├── clockify_client.py  # HTTP client with retry/backoff
│   ├── openapi_loader.py   # OpenAPI spec parsing
│   ├── rate_limiter.py     # Rate limiting
│   └── config.py           # Base settings
├── api_studio/             # API Studio add-on
│   ├── lifecycle.py        # Lifecycle endpoints
│   ├── webhooks.py         # Webhook receiver
│   ├── bootstrap.py        # GET bootstrap
│   ├── flows.py            # Flow engine
│   ├── api_explorer.py     # API Explorer
│   ├── ui.py               # UI endpoints
│   ├── main.py             # FastAPI app
│   ├── models.py           # Database models
│   └── ...
├── universal_webhook/      # Universal Webhook add-on
│   ├── lifecycle.py        # Enhanced lifecycle
│   ├── webhooks.py         # Universal ingestion
│   ├── bootstrap.py        # Enhanced bootstrap
│   ├── flows.py            # Advanced flows
│   ├── api_explorer.py     # Full API Explorer
│   ├── ui.py               # Comprehensive UI
│   ├── main.py             # FastAPI app
│   ├── models.py           # Enhanced models
│   └── ...
├── tests/                  # Test suite (21 tests)
│   ├── test_integration.py # API Studio tests
│   ├── test_main.py        # API Studio tests
│   └── test_universal_webhook.py  # Universal Webhook tests
├── docs/                   # Documentation
├── alembic/                # Database migrations
├── manifest.api-studio.json
├── manifest.universal-webhook.json
└── pyproject.toml
```

---

## 🔧 Configuration

### Environment Variables

#### API Studio
```bash
API_STUDIO_DB_URL=sqlite+aiosqlite:///./api_studio.db
API_STUDIO_BOOTSTRAP_MAX_RPS=25
API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS=false
API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS=90
API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS=30
LOG_LEVEL=INFO
CLOCKIFY_API_BASE_URL=https://api.clockify.me
```

#### Universal Webhook
```bash
UNIVERSAL_WEBHOOK_DB_URL=sqlite+aiosqlite:///./universal_webhook.db
UW_BOOTSTRAP_MAX_RPS=25
UW_BOOTSTRAP_INCLUDE_HEAVY=false
UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES=false
UW_BOOTSTRAP_TIME_ENTRY_DAYS=30
UW_BOOTSTRAP_MAX_PAGES=200  # configurable page cap for bootstrap pagination
UW_ENABLE_CUSTOM_WEBHOOKS=true
UW_ENABLE_FLOWS=true
UW_ENABLE_GENERIC_HTTP_ACTIONS=false
UW_WEBHOOK_LOG_RETENTION_DAYS=90
UW_FLOW_EXECUTION_RETENTION_DAYS=90
UW_CACHE_TTL_DAYS=7
LOG_LEVEL=INFO
```

Bootstrap pagination respects `UW_BOOTSTRAP_MAX_PAGES` (default `200`). When the cap is reached, the service logs a warning with workspace + operation context and records the truncation in `BootstrapState.last_error` so the UI dashboard surfaces the partial result. Set the env var higher if you need deeper historical fetches; lower it to keep bootstrap windows bounded in large workspaces. Use `UW_BOOTSTRAP_INCLUDE_HEAVY` / `UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES` to opt into heavier endpoints, `UW_BOOTSTRAP_TIME_ENTRY_DAYS` to bound how far back time entries are fetched, and `UW_CACHE_TTL_DAYS` to control when cached entities are purged during retention cleanup.

### Observability & Telemetry

- Structured logging flows through Python's `logging` module (API Studio, Universal Webhook) and `structlog` (Clockify Marketplace add-on) so every request includes workspace IDs, job IDs, and sanitized payload context without leaking secrets.
- Prometheus-compatible metrics live under `/metrics` with bootstrap, webhook, lifecycle, and flow counters/gauges shared in `clockify_core.metrics`.
- Both add-ons share the same expectations: workspace-aware logging, redaction utilities, and consistent metric names/label cardinality to make log aggregation and alerting straightforward.

### Manifest Settings

Both add-ons support structured settings via Clockify UI that override environment variables.

---

## 🚢 Deployment

### Quick Start with Docker Compose (Recommended)

The fastest way to get all three services running:

```bash
# 1. Clone and setup
git clone <repository-url>
cd pyddon
cp .env.example .env

# 2. Start all services (PostgreSQL + 3 add-ons)
docker-compose up -d

# 3. Verify deployment
docker-compose ps
curl http://localhost:8000/ready  # API Studio
curl http://localhost:8001/ready  # Universal Webhook
curl http://localhost:8002/health # Clockify Add-on

# 4. View logs
docker-compose logs -f
```

This starts:
- **PostgreSQL** on port 5432 (with 3 databases: api_studio, universal_webhook, clockify_addon)
- **API Studio** on port 8000
- **Universal Webhook** on port 8001
- **Clockify Add-on** on port 8002

### Local Development (Without Docker)

```bash
# API Studio
uvicorn api_studio.main:app --reload --port 8000

# Universal Webhook
uvicorn universal_webhook.main:app --reload --port 8001

# Clockify Add-on
cd clockify-python-addon
uvicorn app.main:app --reload --port 8002
```

### Production Deployment

**See the comprehensive [DEPLOYMENT.md](DEPLOYMENT.md) guide for:**
- VPS/cloud server setup
- PostgreSQL production configuration
- Nginx reverse proxy with SSL
- Database migrations and backups
- Monitoring with Prometheus
- Security hardening checklist
- Performance tuning

**Quick production setup:**

```bash
# 1. Update .env with production values
POSTGRES_PASSWORD=$(openssl rand -base64 32)
API_STUDIO_DB_URL=postgresql+asyncpg://clockify:$POSTGRES_PASSWORD@postgres:5432/api_studio
UNIVERSAL_WEBHOOK_DB_URL=postgresql+asyncpg://clockify:$POSTGRES_PASSWORD@postgres:5432/universal_webhook
DATABASE_URL=postgresql+asyncpg://clockify:$POSTGRES_PASSWORD@postgres:5432/clockify_addon

# Enable signature verification (REQUIRED for production)
API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION=true
UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION=true
REQUIRE_SIGNATURE_VERIFICATION=true

# 2. Build and start
docker-compose build
docker-compose up -d

# 3. Verify health
docker-compose ps
docker-compose logs --tail=50
```

### Production Checklist

- [ ] ✅ Generate strong PostgreSQL password (`openssl rand -base64 32`)
- [ ] ✅ Update all `DATABASE_URL` variables to use PostgreSQL
- [ ] ✅ Enable signature verification for all services
- [ ] ✅ Set `DEBUG=false` for Clockify add-on
- [ ] ✅ Configure reverse proxy (Nginx) with SSL/TLS
- [ ] ✅ Update `CLOCKIFY_ADDON_BASE_URL` to public domain
- [ ] ✅ Set up log aggregation (see [DEPLOYMENT.md](DEPLOYMENT.md))
- [ ] ✅ Configure Prometheus monitoring (`/metrics` endpoints)
- [ ] ✅ Set up automated database backups (daily recommended)
- [ ] ✅ Configure firewall (allow only 443, 22)
- [ ] ✅ Review data retention settings
- [ ] ✅ Test disaster recovery procedure

### CI/CD

**GitHub Actions workflows automatically:**
- Run all 70 tests on every PR/push
- Build multi-platform Docker images (amd64, arm64)
- Push to GitHub Container Registry (ghcr.io)

**Images available at:**
- `ghcr.io/<owner>/clockify-api_studio:latest`
- `ghcr.io/<owner>/clockify-universal_webhook:latest`
- `ghcr.io/<owner>/clockify-clockify_addon:latest`

See `.github/workflows/` for workflow details.

---

## 🆚 Comparison: API Studio vs Universal Webhook

| Feature | API Studio | Universal Webhook |
|---------|-----------|------------------|
| **Plan Requirement** | STANDARD | ENTERPRISE |
| **Webhook Events** | 12 common | ALL 50+ |
| **Custom Webhooks** | ❌ | ✅ |
| **Scopes** | 7 resources | 15+ resources (ALL) |
| **API Explorer** | Safe GET only | ALL operations |
| **Bootstrap** | Basic | Enhanced (configurable) |
| **Flows** | Basic Clockify API | Advanced (+ generic HTTP) |
| **Settings** | 3 fields | 14 fields |
| **Use Case** | Prototyping | Production automation |
| **Tests** | 9 tests | 12 tests |
| **Port** | 8000 | 8001 |

---

## 🎉 Status

✅ **All three add-ons are fully implemented and production-ready**

- ✅ **API Studio**: Complete with comprehensive tests
- ✅ **Universal Webhook**: Complete with advanced features
- ✅ **Clockify Python Add-on**: Production reference implementation
- ✅ **Shared Core**: Working correctly across all services
- ✅ **Documentation**: Complete with DEPLOYMENT.md, ARCHITECTURE.md, ENV_VARS_REFERENCE.md
- ✅ **Database**: Multi-database migrations, PostgreSQL production-ready
- ✅ **Containerization**: Docker + Docker Compose for all services
- ✅ **CI/CD**: GitHub Actions for automated testing and image builds
- ✅ **Tests**: 70/70 passing (100%)
  - 21 tests for API Studio + Universal Webhook
  - 49 tests for Clockify Python Add-on
- ✅ **Observability**: Prometheus metrics, health checks, structured logging
- ✅ **Security**: Signature verification, rate limiting, workspace isolation

---

## 📝 License

Internal use / proprietary
