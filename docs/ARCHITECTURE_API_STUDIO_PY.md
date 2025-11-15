# Architecture – Clockify API Studio (Python)

Target stack:
- Python 3.11
- FastAPI
- httpx (async) for outgoing Clockify API calls
- SQLAlchemy 2.x (async) + Alembic for migrations
- SQLite in dev, Postgres-ready via DATABASE URL

Package: `api_studio`

Core modules:
- config.py          – load env vars and settings
- db.py              – async engine and session management
- models.py          – ORM models: Installation, BootstrapState, EntityCache, Flow, FlowExecution, WebhookLog
- clockify_client.py – wrapper for Clockify API (handles base URL, X-Addon-Token, rate limiting)
- openapi_loader.py  – load and parse docs/openapi.json
- bootstrap.py       – GET bootstrap logic
- flows.py           – flow model + engine
- webhooks.py        – FastAPI router for /webhooks/clockify
- lifecycle.py       – router for lifecycle endpoints
- api_explorer.py    – router for API Explorer (list + execute endpoints)
- ui.py              – router for minimal UI endpoints
- main.py            – FastAPI app factory and router registration
