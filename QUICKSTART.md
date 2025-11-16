# Clockify API Studio - Quick Start Guide

## Prerequisites

- Python 3.11+
- Virtual environment (venv included)
- SQLite (included with Python)

## Installation

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

## Running the Server

### Development mode (with auto-reload):
```bash
uvicorn api_studio.main:app --reload --host 127.0.0.1 --port 8000
```

### Production mode:
```bash
uvicorn api_studio.main:app --host 0.0.0.0 --port 8000
```

## Testing

Run all tests:
```bash
PYTHONPATH=. pytest tests/ -v
```

Run with coverage:
```bash
PYTHONPATH=. pytest tests/ -v --cov=api_studio
```

## Configuration

Create a `.env` file (optional, defaults are provided):

```env
# Clockify API
CLOCKIFY_API_BASE_URL=https://api.clockify.me

# Database
API_STUDIO_DB_URL=sqlite+aiosqlite:///./api_studio.db

# Bootstrap settings
API_STUDIO_BOOTSTRAP_MAX_RPS=25
API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS=false

# Logging
LOG_LEVEL=INFO
```

## Key Endpoints

### Health & Manifest
- `GET /healthz` - Health check
- `GET /manifest` - Clockify add-on manifest

### Lifecycle (called by Clockify)
- `POST /lifecycle/installed` - Installation callback
- `POST /lifecycle/uninstalled` - Uninstallation callback
- `POST /lifecycle/settings-updated` - Settings update callback

### Webhooks (called by Clockify)
- `POST /webhooks/clockify` - Receives webhook events

### UI/Dashboard
- `GET /ui/health` - UI health check
- `GET /ui/dashboard?workspace_id={id}` - Dashboard data

### Webhooks Management
- `GET /ui/webhooks?workspace_id={id}` - List webhooks
- `GET /ui/webhooks/{webhook_id}?workspace_id={id}` - Webhook details

### Flows Management
- `GET /ui/flows?workspace_id={id}` - List flows
- `POST /ui/flows?workspace_id={id}` - Create flow
- `GET /ui/flows/{flow_id}?workspace_id={id}` - Get flow
- `PUT /ui/flows/{flow_id}?workspace_id={id}` - Update flow
- `DELETE /ui/flows/{flow_id}?workspace_id={id}` - Delete flow
- `GET /ui/flows/{flow_id}/executions?workspace_id={id}` - List executions

### API Explorer
- `GET /ui/api-explorer/endpoints` - List all Clockify API endpoints
- `POST /ui/api-explorer/execute` - Execute API operation

### Bootstrap
- `POST /ui/bootstrap/trigger?workspace_id={id}` - Manually trigger bootstrap

## Testing the Installation Flow

1. Start the server
2. Simulate installation:
   ```bash
   curl -X POST http://localhost:8000/lifecycle/installed \
     -H "Content-Type: application/json" \
     -d '{
       "addonId": "clockify-api-studio",
       "authToken": "your-test-token",
       "workspaceId": "test-workspace-123",
       "apiUrl": "https://api.clockify.me",
       "settings": {}
     }'
   ```

3. Check dashboard:
   ```bash
   curl "http://localhost:8000/ui/dashboard?workspace_id=test-workspace-123" | jq .
   ```

## Creating a Flow

Example: Log time entries to console

```bash
curl -X POST "http://localhost:8000/ui/flows?workspace_id=test-workspace-123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tag new time entries",
    "enabled": true,
    "trigger_event_types": ["TIME_ENTRY_CREATED"],
    "conditions": null,
    "actions": [
      {
        "operation_id": "updateTimeEntry",
        "path_params": {
          "workspaceId": "$.workspace.id",
          "id": "$.id"
        },
        "query_params": {},
        "body": {
          "tagIds": ["tag-id-123"]
        }
      }
    ]
  }'
```

## Troubleshooting

### Database Issues
- Delete `api_studio.db` and run `alembic upgrade head` again
- Check file permissions

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -e ".[dev]"` again

### Port Already in Use
- Change port: `uvicorn api_studio.main:app --port 8001`
- Or kill existing process: `lsof -ti:8000 | xargs kill -9`

## Next Steps

1. Deploy to a public server (required for Clockify to call your endpoints)
2. Update `manifest.api-studio.json` with your public URL
3. Upload manifest to Clockify Developer Portal
4. Install add-on in your Clockify workspace
5. Configure webhooks in Clockify settings
6. Create flows via the API

## Documentation

See `docs/` folder for:
- Full product specification
- Architecture details
- Security guidelines
- Flow examples
- Webhook payload samples

## Support

For issues or questions:
1. Check `IMPLEMENTATION_STATUS.md` for current status
2. Review documentation in `docs/`
3. Check logs in `logs/` directory (if configured)
