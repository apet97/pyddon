# Clockify Python Addon Boilerplate

Production-ready Clockify Add-on implementation in Python 3.11+ with FastAPI, featuring full lifecycle management, webhook handling, and OpenAPI-driven API calls.

## Features

- ✅ **Full Lifecycle Support**: Install, settings-updated, status-changed, deleted
- ✅ **Comprehensive Webhook Handling**: Accepts all Clockify webhook events
- ✅ **No-Code API Caller**: Execute any Clockify API endpoint via OpenAPI validation
- ✅ **API Explorer Catalog**: `/ui/api-explorer` endpoints list every operation by tag with auto-generated forms in the sidebar UI
- ✅ **Universal Coverage**: Manifest + router auto-subscribe to every Clockify webhook and request full read/write scopes with drift tests
- ✅ **Automatic Bootstrap**: On install, fetches all workspace data via GET endpoints
- ✅ **Dual API Mode**: Supports both production (`api.clockify.me`) and developer (`developer.clockify.me`) APIs
- ✅ **Token Verification**: RS256 JWT validation with JWKS support + developer bypass mode
- ✅ **Rate Limiting**: 50 RPS limit with Redis support for distributed systems
- ✅ **Deduplication**: Webhook event deduplication to prevent double processing
- ✅ **Structured Logging & Metrics**: JSON-formatted logs with request IDs plus `/metrics` for Prometheus scrapes
- ✅ **Metrics Endpoint**: `/metrics` exposes Prometheus-compatible counters
- ✅ **Async Everything**: Fully async architecture with httpx and SQLAlchemy 2.0
- ✅ **Database Migrations**: Alembic setup for schema versioning
- ✅ **Comprehensive Tests**: Unit tests for all major components
- ✅ **Workspace Isolation**: All queries enforce workspace boundaries

> 📌 **Canonical coverage** – `app/constants.py` defines `CLOCKIFY_WEBHOOK_EVENTS`, `CLOCKIFY_WEBHOOK_ROUTE_MAP`, `CLOCKIFY_WEBHOOK_EVENTS_BY_PATH`, and `CLOCKIFY_SCOPE_LIST`. The manifest generator, router, and JSON manifest all load from those canonical lists and tests (`tests/test_manifest.py`) make sure every Clockify webhook path + read/write scope stays in lockstep.

### Security & Guardrails

- RS256 + JWKS validation (with strict `iss`, `sub`, and `workspaceId` claims). `REQUIRE_SIGNATURE_VERIFICATION` defaults to `true` and **must remain enabled** in production/staging; flip it to `false` only for local development or automated tests when you cannot generate real Clockify signatures.
- Allowed-domain enforcement for outbound API calls via `CLOCKIFY_ALLOWED_API_DOMAINS` (comma-separated hosts, e.g. `*.clockify.me,api.clockify.com`).
- Per-workspace token-bucket rate limiter (50 RPS) and configurable webhook/API payload size caps block runaway jobs.
- Pervasive workspace isolation (DB queries, cache keys, bootstrap jobs) so data never crosses tenants.

## Quick Start

### Prerequisites

- Python 3.11+
- pip or poetry
- SQLite (default) or PostgreSQL (production)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd clockify-python-addon

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=html
```

### Accessing the UI

Once installed in Clockify, the add-on sidebar will be available at:
- **Sidebar Component**: Clockify → Sidebar → "API Studio"

Or directly access the API caller UI:
- **Direct URL**: `http://localhost:8000/ui`

## Architecture

### Directory Structure

```
clockify-python-addon/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── manifest.py             # Manifest endpoint
│   ├── lifecycle.py            # Lifecycle event handlers
│   ├── webhook_router.py       # Webhook receivers
│   ├── token_verification.py   # JWT/signature validation
│   ├── bootstrap.py            # Workspace data bootstrap
│   ├── api_caller.py           # No-code API executor
│   ├── openapi_loader.py       # OpenAPI spec parser
│   ├── schemas/                # Pydantic models
│   ├── utils/                  # Utilities (rate limit, dedupe, logger, errors)
│   └── db/                     # Database models and session
├── static/                     # Frontend UI files
├── tests/                      # Test suite
├── manifest.json               # Clockify add-on manifest
├── openapi.json                # Clockify API spec (symlink)
└── requirements.txt            # Python dependencies
```

### Key Components

#### 1. Lifecycle Handlers (`app/lifecycle.py`)

Handles Clockify add-on lifecycle events:

- **`/lifecycle/installed`**: Stores installation, triggers bootstrap
- **`/lifecycle/settings-updated`**: Syncs settings changes
- **`/lifecycle/status-changed`**: Updates addon status
- **`/lifecycle/deleted`**: Cleans up workspace data

#### 2. Webhook Router (`app/webhook_router.py`)

Receives and processes all Clockify webhooks:

- Grouped by category (time, project, user, expense, custom)
- Automatic deduplication by event ID
- Signature verification (with developer bypass)
- Structured logging and persistence

#### 3. Bootstrap System (`app/bootstrap.py`)

Automatically fetches workspace context on installation:

- Parses OpenAPI spec to find safe GET endpoints
- Rate-limited parallel execution (50 RPS)
- Pagination handling
- Progress tracking and error recovery

#### 4. No-Code API Caller (`app/api_caller.py`)

Execute any Clockify API endpoint without code:

- OpenAPI-driven parameter validation
- Path parameter substitution
- Query string and body validation
- Supports both production and developer APIs
- Returns structured response with metadata

#### 5. API Explorer Router (`app/api_explorer.py`)

Provides the backing APIs for the sidebar explorer UI:

- `GET /ui/api-explorer/endpoints` groups every OpenAPI operation by tag/method.
- `POST /ui/api-explorer/execute` resolves an `operationId` (or method/path) and proxies via the validated API caller.
- Sidebar UI fetches the catalog and renders schema-driven forms for path/query/body parameters automatically, while still supporting advanced JSON overrides.
- Automatically injects `workspaceId` path parameters and rejects operations outside the bundled spec.

#### 6. Token Verification (`app/token_verification.py`)

Secure request validation:

- RS256 JWT verification using JWKS
- Clockify signature validation
- Developer mode bypass for testing
- Workspace and addon ID validation

## Data Model

All runtime state lives in SQLite (dev) or Postgres (prod) via `app/db/models.py`:

- **`installations`** – one row per workspace, storing addon token, API base, settings, and registered webhook IDs (for deregistration).
- **`webhook_events`** – immutable ledger of every Clockify webhook payload plus metadata (workspace ID, dedupe event ID).
- **`api_calls`** – audit trail of "Any API Call" requests (endpoint, parameters, response status, duration).
- **`bootstrap_jobs`** – progress tracker for long-running bootstrap runs (counts, errors, timing).
- **`workspace_data`** – cached GET responses pulled during bootstrap for the API Explorer UI.

All tables include a `workspace_id` column and the query layer always scopes by workspace.

## Permissions & Manifest Coverage

The add-on requests all read/write scopes and subscribes to every Clockify webhook event. Canonical lists live in `app/constants.py` and are used by:

- `app/webhook_router.py` (routing per event path)
- `app/manifest.py` + `manifest.json` (generated + static manifests)
- Tests (`tests/test_manifest.py`) that diff the router, generated manifest, and JSON manifest to prevent drift.

Any change to the constants automatically cascades through the manifest generator and router, and the tests fail if an event or scope drifts out of sync.

## Operations

- **Environment variables** – see [`clockify-python-addon/ENV_VARS.md`](ENV_VARS.md) for every knob (signature flags, JWKS hosts, rate limiting, etc.).
- **Local run** – follow the Quick Start above or use the repo-level instructions to create `./venv`, install dependencies with `pip install -r requirements.txt`, and start `uvicorn app.main:app --reload`.
- **Docker** – `docker build -t clockify-addon .` then `docker run -p 8000:8000 --env-file .env clockify-addon`. A `docker-compose.yml` is included for local Postgres/Redis stacks.
- **Health / readiness / metrics** – the service exposes `GET /health`, `GET /ready`, and `GET /metrics` (Prometheus exposition). All endpoints include workspace-aware logging so on-call responders can trace traffic quickly.

## Configuration

All configuration is managed via environment variables (`.env` file):

### Required Settings

- `BASE_URL`: Your add-on's public URL
- `DATABASE_URL`: Database connection string
- `ADDON_KEY`: Unique addon identifier

### Security

- `REQUIRE_SIGNATURE_VERIFICATION`: Enable/disable JWT validation
- `CLOCKIFY_ENVIRONMENT`: `prod` (default) or `dev` to auto-select the correct JWKS host
- `CLOCKIFY_JWKS_URL`: Optional override when targeting a custom Clockify environment
- `CLOCKIFY_ALLOWED_API_DOMAINS`: Comma-separated host whitelist for outbound API Studio calls (defaults to `*.clockify.me`, `*.clockify.com`, and official API subdomains)
- `API_CALL_MAX_PAYLOAD_BYTES`: Maximum request body size for `/api-call` (default `1_048_576` bytes)
- `WEBHOOK_MAX_PAYLOAD_BYTES`: Maximum webhook payload size (default `5_242_880` bytes)
- `WEBHOOK_REQUEST_MAX_RETRIES`, `WEBHOOK_REQUEST_BACKOFF_BASE`, `WEBHOOK_REQUEST_BACKOFF_CAP`: Control exponential backoff for Clockify webhook HTTP calls

> RS256 + JWKS verification is mandatory in production. There is no HMAC fallback; use `CLOCKIFY_JWKS_URL` or `CLOCKIFY_ENVIRONMENT` to point at the correct Clockify JWKS host.

**Signature headers**: All lifecycle and webhook routes expect the canonical `Clockify-Signature` header. Legacy headers (`X-Addon-Signature`, `X-Webhook-Signature`) are still accepted automatically for backwards compatibility.

> ⚙️ **Startup validation** – The `Settings` model validates required inputs (base URL, addon key, DB URL, allowed domains, webhook retry knobs) on import. If any value is missing or malformed, the process exits immediately with a descriptive error so misconfigured deployments never start serving traffic.

### API Configuration

- `CLOCKIFY_API_BASE`: Production API base URL
- `CLOCKIFY_DEVELOPER_API_BASE`: Developer API base URL
- Rate limiting, logging levels, and more

### Observability

Every request is tagged with an `X-Request-ID` correlation header that is echoed back to callers and injected into all structured log entries (`request_received`, `request_completed`, `webhook_received`, etc.), simplifying distributed tracing during incident response.

### Metrics

The `/metrics` endpoint exposes Prometheus-compatible counters for API Studio calls, lifecycle callbacks, webhook deliveries, and bootstrap jobs. Grafana/Prometheus scrapers can poll the endpoint at regular intervals to power alerting without any additional sidecars.

## Manifest

The add-on manifest (`manifest.json`) defines:

- **Schema Version**: 1.3
- **Permissions**: All required API scopes
- **Webhooks**: Subscriptions to all Clockify events
- **Components**: Sidebar UI component
- **Settings**: Structured settings (developer_mode, auto_bootstrap, etc.)

### Customizing the Manifest

Edit `app/manifest.py` to modify:

- Addon name and description
- Requested permissions
- Webhook subscriptions
- UI components
- Settings fields

## API Endpoints

### Core Endpoints

- `GET /manifest` - Addon manifest
- `POST /lifecycle/installed` - Installation handler
- `POST /lifecycle/settings-updated` - Settings update handler
- `POST /lifecycle/status-changed` - Status change handler
- `POST /lifecycle/deleted` - Deletion handler

### Webhook Endpoints

- `POST /webhooks/time` - Time entry events
- `POST /webhooks/project` - Project events
- `POST /webhooks/user` - User events
- `POST /webhooks/expense` - Expense events
- `POST /webhooks/custom` - Custom field events
- `POST /webhooks/generic` - All other events

### API Caller

- `POST /api-call` - Execute any Clockify API call
- `GET /ui` - No-code API caller interface
- `GET /ui/api-explorer/endpoints` - List every Clockify operation grouped by tag
- `POST /ui/api-explorer/execute` - Execute an operation by `operationId`

### Admin/Debug

- `GET /health` - Health check
- `GET /ready` - Readiness probe with DB/redis checks
- `GET /metrics` - Prometheus counters
- `GET /installations` - List installations (dev mode)
- `GET /webhooks` - List received webhooks (dev mode)

## Development

### Adding New Features

1. **New Webhook Handler**: Add route in `webhook_router.py`
2. **New API Endpoint**: Add to `api_caller.py` with OpenAPI validation
3. **New Settings**: Update manifest settings in `manifest.py`
4. **Database Changes**: Create Alembic migration

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_lifecycle.py -v

# Run with coverage
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Deployment

### Production Checklist

- [ ] Set `DEBUG=false` in `.env`
- [ ] Set `REQUIRE_SIGNATURE_VERIFICATION=true`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable Redis for distributed rate limiting
- [ ] Configure proper logging aggregation
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerts
- [ ] Backup database regularly

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t clockify-addon .
docker run -p 8000:8000 --env-file .env clockify-addon
```

### Environment-Specific Configuration

- **Development**: Use SQLite, disable verification, verbose logging
- **Staging**: Use PostgreSQL, enable verification, moderate logging
- **Production**: Use PostgreSQL + Redis, full verification, structured JSON logs

## Troubleshooting

### Common Issues

**Issue**: JWT verification fails
- **Solution**: Check `CLOCKIFY_JWKS_URL` is accessible and `REQUIRE_SIGNATURE_VERIFICATION` setting

**Issue**: Rate limit exceeded
- **Solution**: Adjust `RATE_LIMIT_RPS` or enable Redis for better distribution

**Issue**: Bootstrap fails
- **Solution**: Check addon token permissions in manifest and API availability

**Issue**: Webhooks not received
- **Solution**: Verify webhook URLs in manifest match your deployment URL

## Support

For issues, questions, or contributions:

- **Documentation**: [Clockify Developer Portal](https://developer.clockify.me)
- **API Reference**: [Clockify API Docs](https://docs.clockify.me)
- **Issues**: [GitHub Issues](link-to-repo)

## License

MIT License - See LICENSE file for details

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM
- [Pydantic](https://docs.pydantic.dev/) - Data validation using Python type hints
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [Structlog](https://www.structlog.org/) - Structured logging
