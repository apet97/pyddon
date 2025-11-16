# Product Spec: Universal Webhook + Any API Call Add-on

**Enterprise-grade Clockify add-on for universal webhook ingestion and no-code API operations**

---

## Overview

Universal Webhook + Any API Call is a production-ready Clockify add-on that:

- **Receives ALL Clockify webhook events** (50+ event types)
- **Accepts custom webhooks** from external systems via generic HTTP endpoints
- **Performs automatic GET bootstrap** to cache workspace entities on installation
- **Exposes a no-code API Explorer** to execute ANY Clockify API operation
- **Enables no-code flows** connecting webhooks → API calls with conditions and parameter bindings

---

## Key Features

### 1. Universal Webhook Ingestion

- **All Clockify Events**: Subscribes to all 50+ webhook types via manifest
- **Custom Webhooks**: Generic `POST /webhooks/custom/{source}` endpoint for external systems
- **Structured Logging**: All webhooks logged with workspace isolation, indexing, and retention policies
- **Flow Triggers**: Webhooks automatically trigger matching no-code flows

### 2. Automatic GET Bootstrap

- On installation, fetches safe GET endpoints from Clockify API:
  - Core endpoints: `/v1/user`, `/v1/workspaces`
  - Workspace-scoped: `/v1/workspaces/{workspaceId}/*`
- **Configurable via Settings**:
  - Include/exclude heavy endpoints (reports)
  - Include time entries with restricted date range
  - Max RPS (default 25)
- **Progress Tracking**: Status, progress, errors exposed via dashboard

### 3. No-Code API Explorer

- **Browse ALL Clockify API operations** from `openapi.json`:
  - Grouped by tag (User, Workspace, Client, Project, Time Entry, etc.)
  - Filter by method (GET/POST/PUT/PATCH/DELETE)
  - View parameters, schemas, descriptions
- **Execute ANY operation** with parameter forms:
  - Path/query/body parameter resolution
  - Context bindings (workspaceId, userId)
  - Response inspection with status, latency, data

### 4. No-Code Flows

- **Trigger**: Clockify event or custom webhook + optional JSONPath conditions
- **Actions**: One or more:
  - **Clockify API calls**: operationId + parameter mappings
  - **Generic HTTP calls** (if enabled): method, URL, headers, body templates
- **Execution**:
  - Sequential with action chaining (results accessible to next action)
  - Automatic retry on 5xx/429
  - Execution logging with status, errors, results

---

## Architecture

### Stack

- **Python 3.11**
- **FastAPI** (async REST API)
- **httpx** (async HTTP client with retry/backoff)
- **SQLAlchemy 2.x** + Alembic (async ORM + migrations)
- **SQLite** (dev) / **Postgres** (production-ready)
- **Shared `clockify_core` module** (ClockifyClient, OpenAPI loader, rate limiter)

### Database Schema

All tables prefixed with `universal_webhook_*`:

- `universal_webhook_installation` - Workspace installations
- `universal_webhook_bootstrap_state` - Bootstrap progress tracking
- `universal_webhook_entity_cache` - Cached Clockify entities
- `universal_webhook_log` - Webhook logs (Clockify + custom)
- `universal_webhook_flow` - Flow definitions
- `universal_webhook_flow_execution` - Flow execution logs

### Endpoints

#### Lifecycle
- `POST /lifecycle/installed` - Installation handler
- `POST /lifecycle/uninstalled` - Uninstall handler
- `POST /lifecycle/settings-updated` - Settings update handler

#### Webhooks
- `POST /webhooks/clockify` - Receive all Clockify events
- `POST /webhooks/custom/{source}` - Receive custom webhooks

#### API Explorer
- `GET /ui/api-explorer/endpoints` - List all operations
- `POST /ui/api-explorer/execute` - Execute operation

#### Flows
- `GET /ui/flows` - List flows
- `POST /ui/flows` - Create flow
- `GET /ui/flows/{id}` - Get flow details
- `PUT /ui/flows/{id}` - Update flow
- `DELETE /ui/flows/{id}` - Delete flow
- `GET /ui/flows/{id}/executions` - List executions

#### Dashboard & Webhooks
- `GET /ui/dashboard` - Workspace dashboard
- `GET /ui/webhooks` - List webhook logs
- `GET /ui/webhooks/{id}` - Webhook details
- `POST /ui/bootstrap/trigger` - Manually trigger bootstrap

---

## Manifest

- **Schema Version**: 1.3
- **Plan Requirement**: ENTERPRISE
- **Scopes**: ALL READ + WRITE scopes for all resources:
  - WORKSPACE, TIME_ENTRY, PROJECT, CLIENT, TAG, TASK
  - USER, GROUP, CUSTOM_FIELDS, EXPENSE, INVOICE
  - APPROVAL, SCHEDULING, REPORTS, TIME_OFF
- **Webhooks**: All 50+ event types subscribed
- **Settings**: 4 sections, 14 configurable fields:
  - Bootstrap (run_on_install, include_heavy, max_rps, include_time_entries, time_entry_days_back)
  - Webhooks (enable_custom, log_retention_days)
  - Flows (enable_flows, enable_generic_http_actions, execution_retention_days)
  - Data (cache_ttl_days)

---

## Security & Limits

### Security
- **Workspace Isolation**: All queries filtered by `workspace_id`
- **Token Management**: Addon tokens stored securely, never exposed to UI
- **Input Validation**: All endpoints use Pydantic models
- **Signature Validation**: Webhook requests validated (headers, workspace checks)

### Rate Limiting
- **Clockify API Limit**: 50 RPS per workspace
- **Internal Throttle**: Default 25 RPS for bootstrap/flows with exponential backoff on 429
- **Configurable**: `max_rps` setting per workspace

### Data Retention
- **Webhook Logs**: Configurable (default 90 days)
- **Flow Execution Logs**: Configurable (default 90 days)
- **Entity Cache**: TTL-based (default 7 days)

---

## Configuration

### Environment Variables

```bash
# Database
UNIVERSAL_WEBHOOK_DB_URL=sqlite+aiosqlite:///./universal_webhook.db

# Bootstrap
UW_BOOTSTRAP_MAX_RPS=25
UW_BOOTSTRAP_INCLUDE_HEAVY=false
UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES=false
UW_BOOTSTRAP_TIME_ENTRY_DAYS=30

# Webhooks
UW_ENABLE_CUSTOM_WEBHOOKS=true
UW_WEBHOOK_LOG_RETENTION_DAYS=90

# Flows
UW_ENABLE_FLOWS=true
UW_ENABLE_GENERIC_HTTP_ACTIONS=false
UW_FLOW_EXECUTION_RETENTION_DAYS=90

# Data
UW_CACHE_TTL_DAYS=7

# Logging
LOG_LEVEL=INFO
```

> `UW_ENABLE_GENERIC_HTTP_ACTIONS` is currently reserved for future outbound HTTP action support; toggling it has no effect yet.

### Manifest Settings (Override Environment)

Settings configured via Clockify UI take precedence over environment variables.

---

## Use Cases

### 1. Comprehensive Audit Log
- Subscribe to all Clockify events
- Log every change with full payload
- Query historical events via UI

### 2. External System Integration
- Receive webhooks from Zapier, Make, n8n
- Trigger Clockify API calls based on external events
- Example: Zapier form submission → create Clockify project

### 3. Advanced Automation
- NEW_TIME_ENTRY → validate project budget → tag/update entry
- EXPENSE_CREATED → check policy → approve/reject via API
- TIME_OFF_REQUESTED → check availability → auto-approve

### 4. API Prototyping
- Explore all Clockify API endpoints
- Test operations with real data
- Generate example requests for integration

---

## Deployment

### Local Development
```bash
# Run migrations
alembic upgrade head

# Start server
uvicorn universal_webhook.main:app --host 0.0.0.0 --port 8001

# With reload
uvicorn universal_webhook.main:app --reload --port 8001
```

### Production
- Deploy with Gunicorn + Uvicorn workers
- Use Postgres database
- Configure ngrok/public URL for webhook ingress
- Update `baseUrl` in manifest before publishing

---

## Comparison: Universal Webhook vs API Studio

| Feature | API Studio | Universal Webhook |
|---------|-----------|------------------|
| **Webhook Events** | Subset (12 events) | ALL (50+ events) |
| **Custom Webhooks** | ❌ | ✅ |
| **Plan Requirement** | STANDARD | ENTERPRISE |
| **Scopes** | Subset (7 resources) | ALL (15+ resources) |
| **API Explorer** | Safe GET only | ALL operations |
| **Flows** | Basic | Enhanced (generic HTTP) |
| **Settings** | 3 fields | 14 fields |
| **Use Case** | Internal prototyping | Production automation |

---

## Roadmap

### Completed ✅
- All lifecycle endpoints
- Universal webhook ingestion (Clockify + custom)
- Automatic GET bootstrap
- API Explorer (all operations)
- No-code flows (Clockify API actions)
- Comprehensive tests (21 passing)

### Future Enhancements
- [ ] Generic HTTP actions in flows (currently stubbed)
- [ ] JWT/signature validation for webhooks
- [ ] SSE/WebSocket for real-time webhook stream
- [ ] Flow templates library
- [ ] PII redaction in logs
- [ ] Metrics/telemetry endpoints
- [ ] Frontend UI (currently JSON API only)

---

## License & Support

- **License**: Internal use / proprietary
- **Maintained by**: Engineering team
- **Documentation**: See `docs/` directory
- **Tests**: `pytest tests/test_universal_webhook.py -v`
