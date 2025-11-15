# Architecture: Universal Webhook + Any API Call Add-on (Python)

**Production-grade Clockify add-on for universal webhook ingestion and no-code API operations**

---

## Overview

The Universal Webhook add-on is a FastAPI service that:
- Subscribes to ALL 50+ Clockify webhook event types
- Accepts custom webhooks from external systems
- Performs automatic GET bootstrap to cache workspace context
- Exposes a no-code API Explorer for executing any Clockify operation
- Enables no-code flows connecting webhooks → API calls

Built on the same foundation as `api_studio` but with enhanced capabilities for universal webhook processing and generic API execution.

---

## Technology Stack

- **Python 3.11+** with type hints
- **FastAPI** - async REST API framework
- **Pydantic v2** - data validation and settings
- **SQLAlchemy 2.x** - async ORM
- **Alembic** - database migrations
- **httpx** - async HTTP client with retry/backoff
- **jsonpath-ng** - JSONPath evaluation for flow conditions
- **aiosqlite** (dev) / **asyncpg** (prod) - async database drivers

---

## Project Structure

```
universal_webhook/
├── __init__.py           # Package metadata
├── config.py             # Settings with environment variables
├── db.py                 # Database session management
├── models.py             # SQLAlchemy ORM models
├── lifecycle.py          # Lifecycle endpoints (install, uninstall, settings)
├── webhooks.py           # Webhook receivers (Clockify + custom)
├── bootstrap.py          # GET bootstrap engine
├── api_explorer.py       # API Explorer endpoints
├── flows.py              # Flow engine (evaluation + execution)
├── ui.py                 # UI endpoints (dashboard, webhooks, flows)
└── main.py               # FastAPI app factory

clockify_core/            # Shared modules
├── clockify_client.py    # HTTP client with rate limiting
├── openapi_loader.py     # OpenAPI spec parsing
├── rate_limiter.py       # Token bucket rate limiter
└── config.py             # Base settings class
```

---

## Database Schema

All tables use `universal_webhook_*` prefix for isolation from `api_studio`.

### Tables

#### 1. `universal_webhook_installation`
Stores workspace installations and addon tokens.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| addon_token | String(512) | Encrypted token for API calls |
| settings_json | Text | Workspace-specific settings |
| installed_at | DateTime(TZ) | Installation timestamp |
| is_active | Boolean | Soft-delete flag |

**Indexes**: `workspace_id` (unique), `is_active`

#### 2. `universal_webhook_bootstrap_state`
Tracks GET bootstrap progress per workspace.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| status | String(50) | pending, in_progress, completed, error |
| progress | Integer | 0-100 |
| total_endpoints | Integer | Total GET endpoints to fetch |
| completed_endpoints | Integer | Completed endpoints |
| error_message | Text | Error details if failed |
| started_at | DateTime(TZ) | Bootstrap start time |
| completed_at | DateTime(TZ) | Bootstrap completion time |

**Indexes**: `workspace_id` (unique), `status`

#### 3. `universal_webhook_entity_cache`
Caches entities fetched from Clockify API.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| entity_type | String(100) | user, project, client, tag, task, etc. |
| entity_id | String(255) | Clockify entity ID |
| data_json | Text | Full JSON payload |
| fetched_at | DateTime(TZ) | Fetch timestamp |

**Indexes**: `workspace_id`, `entity_type`, `entity_id`, `(workspace_id, entity_type)`

#### 4. `universal_webhook_log`
Logs all incoming webhooks (Clockify + custom).

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| event_type | String(255) | Webhook event type |
| source | String(50) | CLOCKIFY or CUSTOM |
| custom_source | String(255) | Custom webhook source name |
| payload_json | Text | Full webhook payload |
| headers_json | Text | Request headers |
| status | String(50) | received, processed, error |
| error_message | Text | Error details if failed |
| received_at | DateTime(TZ) | Receipt timestamp |

**Indexes**: `workspace_id`, `event_type`, `source`, `received_at`, `status`

#### 5. `universal_webhook_flow`
No-code flow definitions.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| name | String(255) | Flow name |
| description | Text | Flow description |
| trigger_event_type | String(255) | Event type to trigger on |
| trigger_source | String(50) | CLOCKIFY or CUSTOM |
| conditions_json | Text | JSONPath conditions (ALL/ANY) |
| actions_json | Text | Array of actions to execute |
| enabled | Boolean | Enable/disable flag |
| created_at | DateTime(TZ) | Creation timestamp |
| updated_at | DateTime(TZ) | Last update timestamp |

**Indexes**: `workspace_id`, `trigger_event_type`, `enabled`, `(workspace_id, trigger_event_type, enabled)`

#### 6. `universal_webhook_flow_execution`
Flow execution logs.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| workspace_id | String(255) | Clockify workspace ID |
| flow_id | Integer | Foreign key to flow |
| webhook_log_id | Integer | Foreign key to webhook log |
| status | String(50) | success, error, partial |
| actions_executed | Integer | Number of actions executed |
| error_message | Text | Error details if failed |
| result_json | Text | Execution results |
| started_at | DateTime(TZ) | Execution start time |
| completed_at | DateTime(TZ) | Execution completion time |

**Indexes**: `workspace_id`, `flow_id`, `webhook_log_id`, `status`, `started_at`

---

## Core Components

### 1. Configuration (`config.py`)

Pydantic v2 settings with environment variable support:

```python
class UniversalWebhookSettings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./api_studio.db"
    
    # Bootstrap settings
    bootstrap_max_rps: int = 25
    bootstrap_include_heavy_endpoints: bool = False
    bootstrap_include_time_entries: bool = True
    bootstrap_time_entry_days_back: int = 30
    
    # Webhook settings
    webhook_enable_custom: bool = True
    webhook_log_retention_days: int = 90
    
    # Flow settings
    flow_enable_flows: bool = True
    flow_enable_generic_http_actions: bool = False
    flow_execution_retention_days: int = 30
    
    # Data settings
    cache_ttl_days: int = 7
```

Loaded from `.env` file or environment variables with `UNIVERSAL_WEBHOOK_` prefix.

### 2. Database Session (`db.py`)

Async SQLAlchemy session management:

```python
async_engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

Used as FastAPI dependency for automatic session management.

### 3. Lifecycle Management (`lifecycle.py`)

#### `POST /lifecycle/installed`
1. Parse installation payload (workspaceId, userId, token, settings)
2. Upsert `Installation` record with addon token
3. Initialize `BootstrapState` record
4. Trigger background bootstrap if enabled
5. Return success response

#### `POST /lifecycle/uninstalled`
1. Validate workspace ID
2. Soft-delete installation (set `is_active = False`)
3. Optionally clean up cached data based on settings
4. Return success response

#### `POST /lifecycle/settings-updated`
1. Validate workspace ID
2. Load new settings from payload
3. Update `Installation.settings_json`
4. Optionally trigger re-bootstrap if relevant settings changed
5. Return success response

### 4. Webhook Ingestion (`webhooks.py`)

#### `POST /webhooks/clockify`
1. Extract workspace ID from payload
2. Extract event type from `X-Clockify-Webhook-EventType` header
3. Validate installation exists and is active
4. Create `WebhookLog` record with source=CLOCKIFY
5. Fire-and-forget: trigger flow evaluation
6. Return 200 OK immediately

#### `POST /webhooks/custom/{source}`
1. Validate `X-Webhook-Source` header matches path parameter
2. Extract workspace ID from payload or header
3. Create `WebhookLog` record with source=CUSTOM
4. Fire-and-forget: trigger flow evaluation
5. Return 200 OK immediately

### 5. Bootstrap Engine (`bootstrap.py`)

#### `async def bootstrap_workspace(workspace_id, addon_token)`
1. Load OpenAPI spec and discover safe GET operations
2. Apply filters based on settings:
   - Exclude heavy endpoints if `bootstrap_include_heavy_endpoints=False`
   - Include time entries only if `bootstrap_include_time_entries=True`
3. Prioritize core endpoints (user, workspaces)
4. For each endpoint:
   - Resolve path parameters (workspaceId)
   - Apply rate limiting (max RPS from settings)
   - Fetch with pagination (page-size: 50)
   - Store entities in `EntityCache`
   - Update progress in `BootstrapState`
5. Handle errors with resumption capability
6. Mark bootstrap as completed

### 6. API Explorer (`api_explorer.py`)

#### `GET /ui/api-explorer/endpoints`
1. Load OpenAPI spec
2. Extract all operations with metadata
3. Group by tag (User, Project, Client, etc.)
4. Filter by method if specified
5. Return list of operations with:
   - operationId, method, path, summary, description
   - parameters (path, query, body schema)

#### `POST /ui/api-explorer/execute`
1. Validate workspace ID and operation ID
2. Resolve parameters from request + context:
   - Path params: `{workspaceId}` → actual workspace ID
   - Query params: from request body
   - Body: from request body
3. Execute via `ClockifyClient` with addon token
4. Return response with status, data, latency
5. Optionally save as flow action

### 7. Flow Engine (`flows.py`)

#### Flow Evaluation
On webhook receipt:
1. Query flows matching `trigger_event_type` and `trigger_source`
2. Filter to enabled flows
3. For each flow:
   - Evaluate conditions using JSONPath
   - If ALL/ANY conditions pass, execute flow

#### Condition Evaluation
```python
conditions = {
    "mode": "ALL",  # or "ANY"
    "rules": [
        {"path": "$.project.name", "operator": "==", "value": "Internal"},
        {"path": "$.timeInterval.duration", "operator": ">", "value": 3600}
    ]
}
```

Supported operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `exists`

#### Action Execution
```python
actions = [
    {
        "type": "clockify_api",
        "operation_id": "update-project",
        "parameters": {
            "workspaceId": "{{workspace_id}}",
            "projectId": "{{webhook.project.id}}",
            "body": {
                "archived": True
            }
        }
    }
]
```

Actions executed sequentially with context chaining:
- `{{webhook.*}}` - webhook payload
- `{{cache.*}}` - cached entities
- `{{actions[N].result}}` - previous action results

### 8. UI Endpoints (`ui.py`)

#### Dashboard (`GET /ui/dashboard`)
Returns:
- Bootstrap status and progress
- Entity counts by type
- Flow statistics (total, enabled)
- Recent activity (webhooks/executions in 24h)
- Error counts

#### Webhook Management
- `GET /ui/webhooks` - List with filters (event_type, source, date range)
- `GET /ui/webhooks/{id}` - Get full webhook details

#### Flow Management
- `GET /ui/flows` - List all flows
- `POST /ui/flows` - Create new flow
- `GET /ui/flows/{id}` - Get flow details
- `PUT /ui/flows/{id}` - Update flow
- `DELETE /ui/flows/{id}` - Delete flow
- `GET /ui/flows/{id}/executions` - List executions

#### Bootstrap Control
- `POST /ui/bootstrap/trigger` - Manually trigger bootstrap

---

## Security & Isolation

### Workspace Isolation
**CRITICAL**: Every database query MUST filter by `workspace_id`:

```python
async def get_flows(workspace_id: str, db: AsyncSession):
    result = await db.execute(
        select(Flow).where(Flow.workspace_id == workspace_id)
    )
    return result.scalars().all()
```

### Token Storage
Addon tokens stored encrypted in database, never exposed in responses.

### Input Validation
All inputs validated with Pydantic models:
- Path parameters
- Query parameters
- Request bodies
- Webhook payloads

### Rate Limiting
Enforced via `RateLimiter` from `clockify_core`:
- Token bucket algorithm
- Configurable RPS (default 25, max 50)
- Automatic backoff on 429 responses

### Logging
Structured logging with context:
- workspace_id
- operation_id
- event_type
- flow_id
- request_id
- source (universal_webhook)

---

## Error Handling

### HTTP Errors
- 400: Invalid request (validation errors)
- 401: Unauthorized (invalid token)
- 403: Forbidden (scope/workspace mismatch)
- 404: Not found (entity doesn't exist)
- 429: Rate limit exceeded
- 500: Internal server error

### Retry Strategy
- 5xx errors: exponential backoff (max 3 retries)
- 429 errors: respect Retry-After header
- Network errors: retry with jitter

### Error Logging
All errors logged with full context:
```python
logger.error(
    "Flow execution failed",
    extra={
        "workspace_id": workspace_id,
        "flow_id": flow_id,
        "webhook_log_id": webhook_log_id,
        "error": str(e)
    }
)
```

---

## Performance Considerations

### Database Indexes
All query fields indexed:
- workspace_id (on all tables)
- event_type, status, source (on webhook_log)
- enabled, trigger_event_type (on flow)
- started_at, completed_at (on executions)

### Connection Pooling
SQLAlchemy connection pool:
- pool_size: 20
- max_overflow: 10
- pool_pre_ping: True

### Rate Limiting
- Bootstrap: configurable RPS (default 25)
- API Explorer: shared rate limiter
- Flows: per-action rate limiting

### Async I/O
All I/O operations async:
- Database queries (aiosqlite/asyncpg)
- HTTP requests (httpx)
- Flow execution (asyncio tasks)

---

## Deployment

### Environment Variables
```bash
# Database
UNIVERSAL_WEBHOOK_DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Bootstrap
UNIVERSAL_WEBHOOK_BOOTSTRAP_MAX_RPS=25
UNIVERSAL_WEBHOOK_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS=false
UNIVERSAL_WEBHOOK_BOOTSTRAP_INCLUDE_TIME_ENTRIES=true
UNIVERSAL_WEBHOOK_BOOTSTRAP_TIME_ENTRY_DAYS_BACK=30

# Webhooks
UNIVERSAL_WEBHOOK_WEBHOOK_ENABLE_CUSTOM=true
UNIVERSAL_WEBHOOK_WEBHOOK_LOG_RETENTION_DAYS=90

# Flows
UNIVERSAL_WEBHOOK_FLOW_ENABLE_FLOWS=true
UNIVERSAL_WEBHOOK_FLOW_ENABLE_GENERIC_HTTP_ACTIONS=false
UNIVERSAL_WEBHOOK_FLOW_EXECUTION_RETENTION_DAYS=30

# Data
UNIVERSAL_WEBHOOK_CACHE_TTL_DAYS=7
```

### Database Migration
```bash
alembic upgrade head
```

### Running the Service
```bash
uvicorn universal_webhook.main:app --host 0.0.0.0 --port 8001
```

### Health Checks
- `GET /healthz` - Basic health check
- `GET /manifest` - Manifest validation

---

## Testing

### Unit Tests
- Models: ORM model creation and validation
- Config: Settings loading and validation
- Flows: Condition evaluation and action resolution

### Integration Tests
- Lifecycle: Install/uninstall/settings workflows
- Webhooks: Clockify + custom webhook ingestion
- API Explorer: Endpoint listing and execution
- Flows: End-to-end flow execution
- UI: Dashboard and CRUD endpoints

### Test Command
```bash
pytest tests/test_universal_webhook.py -v
```

---

## Observability

### Metrics (Planned)
- `webhooks_received_total{workspace_id, event_type, source}`
- `flows_executed_total{workspace_id, flow_id, status}`
- `api_calls_total{workspace_id, operation_id, status}`
- `bootstrap_duration_seconds{workspace_id}`

### Logs
- Structured JSON logs with context
- Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Rotation: daily, 7 days retention

### Tracing (Planned)
- OpenTelemetry integration
- Trace webhook → flow → API call chains
- Distributed tracing for flow actions

---

## Future Enhancements

- [ ] JWT/signature validation for webhooks
- [ ] Generic HTTP actions in flows (external APIs)
- [ ] SSE/WebSocket for real-time updates
- [ ] Frontend UI (React/Vue)
- [ ] PII redaction in logs
- [ ] Data retention cleanup jobs
- [ ] Flow templates library
- [ ] Flow testing/debugging mode
- [ ] Advanced flow features (loops, conditionals, variables)
- [ ] Webhook replay functionality
- [ ] Export/import flows
- [ ] Audit logs for all operations

---

## References

- Product Spec: `docs/clockify-universal-webhook-spec.md`
- Quickstart: `docs/QUICKSTART_UNIVERSAL_WEBHOOK.md`
- Implementation Checklist: `docs/IMPLEMENTATION_CHECKLIST_UNIVERSAL_WEBHOOK_PY.md`
- API Studio Architecture: `docs/ARCHITECTURE_API_STUDIO_PY.md`
- Clockify Add-on Guide: `docs/Clockify_Addon_Guide.md`
- OpenAPI Spec: `docs/openapi.json`
