# Security & Limits – Clockify API Studio (Python)

## ✅ Implemented Security Measures

### Secret Protection
- X-Addon-Token headers and addon tokens are never logged; structured logging (`app/utils/logger.py`) redacts common sensitive keys.
- Middleware injects request IDs and sanitizes headers before they reach log sinks.

### Workspace Isolation
- Every persistence model includes `workspace_id` and queries filter by it (installations, webhooks, API calls, bootstrap data).
- Lifecycle and webhook routers enforce that JWT/workspace claims match the payload before touching the database.

### Outbound HTTP Call Restrictions
- `app/api_caller.py` restricts outbound requests to `settings.allowed_api_domains` (defaults include `api.clockify.me`, `developer.clockify.me`, `reports.api.clockify.me`, etc.).
- Only endpoints present in the bundled `openapi.json` may be invoked; unknown method/path combinations return validation errors.

### Rate Limiting
- A token-bucket limiter (`app/utils/rate_limit.py`) caps each workspace at 50 requests per second by default (configurable via `RATE_LIMIT_RPS`).
- `httpx` requests handle 429s with exponential backoff; bootstrap uses the same executor so it inherits the limiter.
- Webhook registration/deletion calls now retry automatically with exponential backoff governed by `WEBHOOK_REQUEST_MAX_RETRIES`, `WEBHOOK_REQUEST_BACKOFF_BASE`, and `WEBHOOK_REQUEST_BACKOFF_CAP`.

### JWT / Signature Verification
- `app/token_verification.py` performs RS256 + JWKS validation, checking `iss == "clockify"`, `sub == addon_key`, `type == "addon"`, and ensuring `workspaceId`/`addonId` match expectations.
- Both lifecycle and webhook routers require the canonical `Clockify-Signature` header (legacy headers accepted with warnings) and reject mismatched claims.
- When `WEBHOOK_HMAC_SECRET` is set the verifier automatically falls back to computing an HMAC-SHA256 digest when Clockify delivers shared-secret signatures, and the `/metrics` endpoint tracks both signature failures and HMAC fallback usage per scope so operators can alert on suspicious traffic.

## 📊 Observability & Limits

### Metrics
- `GET /metrics` exposes Prometheus text format counters implemented in `app/metrics.py`.
- Tracked metrics include API Studio calls (success/failure), lifecycle callbacks, webhook receipts by event type, signature verification failures, HMAC fallback usage, and bootstrap job outcomes.

### Health Monitoring
- `GET /health` returns a lightweight liveness payload with version + timestamp.
- `GET /ready` checks database connectivity (and Redis when enabled), returning HTTP 503 on failure.

### Data Retention
- SQLite/Postgres tables keep historical data; retention/cleanup is handled operationally (no automatic purge job is included).
- Admin endpoints (`/bootstrap/*`, `/webhooks` dev listing) can be used to inspect and manage stored entities as needed.

## 🔐 Deployment Best Practices

1. Run behind HTTPS and set `BASE_URL` to the public TLS endpoint.
2. Use PostgreSQL in production; SQLite is intended for local development only.
3. Keep `REQUIRE_SIGNATURE_VERIFICATION=true` outside of dev.
4. Configure log aggregation for JSON logs and scrape `/metrics` for alerting.
5. Backup databases regularly and store secrets in a managed vault.

## 🧪 Security Testing

- `tests/test_security.py` covers JWKS caching, missing headers, developer-mode bypass warnings, and header resolution.
- `tests/test_middleware.py` validates request ID injection and payload size enforcement.
- `tests/test_api_caller.py` verifies domain whitelist blocking for non-Clockify hosts.
- New suites (`tests/test_webhook_manager.py`, `tests/test_config.py`, `tests/test_integration_app.py`) exercise webhook retries, environment validation, and FastAPI endpoints end-to-end.
- Additional coverage for manifest parity, bootstrap pagination, API explorer, and metrics keeps regression risk low.
- `PYTHONPATH=. pytest tests/ -v` → **49** tests passing on the current branch.
