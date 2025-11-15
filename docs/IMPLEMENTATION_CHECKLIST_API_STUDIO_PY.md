# Implementation Checklist – Clockify API Studio (Python)

1. Project setup
- [x] Confirmed `requirements.txt` installs dependencies; FastAPI app importable (`uvicorn app.main:app`).
- [x] Alembic migrations cover installation/webhook/API call/bootstrap tables.

2. Core infrastructure
- [x] `app/config.py` loads env vars (documented in `ENV_VARS.md`).
- [x] `app/db/session.py` + `app/db/models.py` implement async SQLAlchemy engine and ORM models (Installation, WebhookEvent, APICall, BootstrapJob, WorkspaceData).

3. Clockify client
- [x] `app/api_caller.py` uses `httpx`, supports all HTTP verbs, enforces rate limits, retries 429s, and validates requests against OpenAPI metadata.

4. Lifecycle endpoints (`app/lifecycle.py`)
- [x] `POST /lifecycle/installed` – upserts installation, registers webhooks, triggers bootstrap.
- [x] `POST /lifecycle/uninstalled` – cleans up webhooks + workspace data.
- [x] `POST /lifecycle/settings-updated` / `POST /lifecycle/status-changed` – sync settings and status.

5. Webhooks (`app/webhook_router.py`)
- [x] `POST /webhooks/*` routes validate signatures, dedupe events, persist payloads, and emit metrics.

6. Bootstrap (`app/bootstrap.py`)
- [x] Loads `openapi.json`, discovers safe GET endpoints, paginates until exhaustion (configurable via `BOOTSTRAP_MAX_PAGES`), rate limits, and stores entity cache entries with progress tracking.

7. API Explorer (`app/api_explorer.py`)
- [x] `GET /ui/api-explorer/endpoints` lists OpenAPI operations grouped by tag.
- [x] `POST /ui/api-explorer/execute` executes any `operationId` with validation + workspace scoping.

8. Flows
- [ ] (Optional / future) Flow builder and execution engine are not part of this Python add-on; tracked separately.

9. UI
- [x] Static UI served from `static/` plus JSON endpoints for bootstrap status; ready for Clockify sidebar embedding.

10. `main.py`
- [x] FastAPI app includes manifest, lifecycle, webhook, API explorer routers; exposes `/api-call`, `/bootstrap/*`, `/health`, `/ready`, and `/metrics`.
