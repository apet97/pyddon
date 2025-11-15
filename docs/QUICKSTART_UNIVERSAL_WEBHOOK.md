# Quickstart: Universal Webhook + Any API Call

**Get the Universal Webhook add-on running in 5 minutes**

---

## Prerequisites

- Python 3.11+
- Git
- Virtual environment (venv)

---

## 1. Setup

### Clone & Install

```bash
cd /path/to/clockify-api-studio-py-kit

# Activate virtual environment
source venv/bin/activate

# Packages already installed via pyproject.toml
# If needed: pip install -e .
```

### Run Database Migrations

```bash
# Create/upgrade database schema
alembic upgrade head

# Should create universal_webhook.db with 6 tables
```

---

## 2. Start the Server

### Development Mode

```bash
# Start with auto-reload
uvicorn universal_webhook.main:app --reload --port 8001

# Server runs at http://localhost:8001
```

### Production Mode

```bash
# Start with Gunicorn + Uvicorn workers
gunicorn universal_webhook.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

---

## 3. Verify Installation

### Health Check

```bash
curl http://localhost:8001/healthz
# {"status":"ok","service":"universal-webhook"}
```

### Manifest

```bash
curl http://localhost:8001/manifest | jq .
# Should show manifest with 50+ webhook event types
```

---

## 4. Test Lifecycle Endpoints

### Simulate Installation

```bash
curl -X POST http://localhost:8001/lifecycle/installed \
  -H "Content-Type: application/json" \
  -d '{
    "addonId": "test-addon-123",
    "authToken": "test-token-abc",
    "workspaceId": "workspace-001",
    "apiUrl": "https://api.clockify.me",
    "settings": {
      "bootstrap": {
        "run_on_install": false
      }
    }
  }'

# Response:
# {"status":"installed","workspaceId":"workspace-001","bootstrap":"disabled"}
```

### Check Dashboard

```bash
curl "http://localhost:8001/ui/dashboard?workspace_id=workspace-001" | jq .

# Response:
# {
#   "workspace_id": "workspace-001",
#   "bootstrap": {
#     "status": "DISABLED",
#     "progress": 0,
#     "total": 0,
#     ...
#   },
#   "entity_counts": {},
#   "flows": {"total": 0, "enabled": 0},
#   "recent_activity": {"webhooks_24h": 0, "flow_executions_24h": 0}
# }
```

---

## 5. Test Webhook Ingestion

### Send Clockify Webhook

```bash
curl -X POST http://localhost:8001/webhooks/clockify \
  -H "Content-Type: application/json" \
  -H "clockify-webhook-event-type: NEW_TIME_ENTRY" \
  -H "clockify-webhook-workspace-id: workspace-001" \
  -d '{
    "id": "entry-123",
    "workspaceId": "workspace-001",
    "projectId": "project-456",
    "userId": "user-789",
    "timeInterval": {
      "start": "2024-01-15T10:00:00Z",
      "end": "2024-01-15T11:00:00Z"
    }
  }'

# Response:
# {
#   "status": "received",
#   "webhookId": "1",
#   "eventType": "NEW_TIME_ENTRY",
#   "workspaceId": "workspace-001"
# }
```

### Send Custom Webhook

```bash
curl -X POST http://localhost:8001/webhooks/custom/zapier \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: workspace-001" \
  -d '{
    "event_type": "FORM_SUBMITTED",
    "data": {
      "form_id": "contact-form-1",
      "email": "user@example.com"
    }
  }'

# Response:
# {
#   "status": "received",
#   "webhookId": "2",
#   "source": "zapier",
#   "eventType": "FORM_SUBMITTED",
#   "workspaceId": "workspace-001"
# }
```

### List Webhooks

```bash
curl "http://localhost:8001/ui/webhooks?workspace_id=workspace-001" | jq .

# Response:
# {
#   "workspace_id": "workspace-001",
#   "total": 2,
#   "limit": 50,
#   "offset": 0,
#   "webhooks": [
#     {
#       "id": 2,
#       "source": "CUSTOM",
#       "custom_source": "zapier",
#       "event_type": "FORM_SUBMITTED",
#       "received_at": "2024-01-15T12:00:00Z"
#     },
#     {
#       "id": 1,
#       "source": "CLOCKIFY",
#       "custom_source": null,
#       "event_type": "NEW_TIME_ENTRY",
#       "received_at": "2024-01-15T11:55:00Z"
#     }
#   ]
# }
```

---

## 6. Test API Explorer

### List All Operations

```bash
curl "http://localhost:8001/ui/api-explorer/endpoints?workspace_id=workspace-001" | jq '.groups | keys'

# Response: List of API tags
# ["Client", "Custom fields", "Project", "Tag", "Task", "Time entry", "User", "Workspace", ...]
```

### List Operations by Tag

```bash
curl "http://localhost:8001/ui/api-explorer/endpoints?workspace_id=workspace-001&tag=Project" | jq .

# Response: All Project-related operations
```

---

## 7. Test No-Code Flows

### Create a Flow

```bash
curl -X POST "http://localhost:8001/ui/flows?workspace_id=workspace-001" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tag New Time Entries",
    "enabled": true,
    "trigger_source": "CLOCKIFY",
    "trigger_event_types": ["NEW_TIME_ENTRY"],
    "conditions": {
      "type": "ALL",
      "rules": [
        {
          "field": "$.projectId",
          "operator": "exists",
          "value": null
        }
      ]
    },
    "actions": [
      {
        "type": "CLOCKIFY_API",
        "operation_id": "updateTimeEntry",
        "params": {
          "path": {
            "workspaceId": "$.webhook.workspaceId",
            "timeEntryId": "$.webhook.id"
          },
          "body": {
            "tagIds": ["important-tag-id"]
          }
        }
      }
    ]
  }'

# Response:
# {
#   "id": 1,
#   "name": "Tag New Time Entries",
#   "enabled": true,
#   "created_at": "2024-01-15T12:00:00Z"
# }
```

### List Flows

```bash
curl "http://localhost:8001/ui/flows?workspace_id=workspace-001" | jq .

# Response: List of all flows
```

### Get Flow Details

```bash
curl "http://localhost:8001/ui/flows/1?workspace_id=workspace-001" | jq .

# Response: Full flow definition with trigger, conditions, actions
```

---

## 8. Run Tests

### Run All Tests

```bash
PYTHONPATH=. pytest tests/ -v

# Should show:
# 21 passed in X seconds
```

### Run Only Universal Webhook Tests

```bash
pytest tests/test_universal_webhook.py -v

# Should show:
# 12 passed in X seconds
```

---

## 9. Configuration

### Environment Variables

Create `.env` file:

```env
# Database
UNIVERSAL_WEBHOOK_DB_URL=sqlite+aiosqlite:///./universal_webhook.db

# Server
UNIVERSAL_WEBHOOK_PORT=8001

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
CLOCKIFY_API_BASE_URL=https://api.clockify.me
```

### Override via Manifest Settings

Settings configured via Clockify UI take precedence over environment variables.

---

## 10. Deployment Checklist

### For Production

- [ ] Set `UNIVERSAL_WEBHOOK_DB_URL` to Postgres connection string
- [ ] Configure `UW_ENABLE_GENERIC_HTTP_ACTIONS` based on security requirements
- [ ] Set appropriate retention periods for logs
- [ ] Update `baseUrl` in `manifest.universal-webhook.json`
- [ ] Configure public URL (ngrok/domain) for webhook ingress
- [ ] Set up SSL/TLS certificates
- [ ] Configure log aggregation (Sentry, DataDog, etc.)
- [ ] Set up monitoring/alerting
- [ ] Enable backup strategy for database
- [ ] Document workspace-specific settings

---

## Common Issues

### Port Already in Use

```bash
# Change port
uvicorn universal_webhook.main:app --port 8002
```

### Database Locked (SQLite)

```bash
# Use separate database for tests
pytest tests/test_universal_webhook.py --db-url="sqlite+aiosqlite:///:memory:"
```

### Module Not Found

```bash
# Ensure packages are installed
pip install -e .

# Or install individually
pip install fastapi uvicorn sqlalchemy alembic httpx pydantic pydantic-settings jsonpath-ng tenacity
```

---

## Next Steps

1. **Read Full Spec**: `docs/clockify-universal-webhook-spec.md`
2. **Review Architecture**: Understand `clockify_core` shared modules
3. **Explore API**: Test all endpoints with Postman/curl
4. **Create Flows**: Build automations for your use case
5. **Integrate**: Connect external systems via custom webhooks
6. **Monitor**: Check dashboard and logs regularly
7. **Scale**: Move to Postgres and add workers as needed

---

## Support

- **Documentation**: `docs/` directory
- **Tests**: `tests/test_universal_webhook.py`
- **Issues**: Check logs in `logs/` directory
- **Source**: `universal_webhook/` package
