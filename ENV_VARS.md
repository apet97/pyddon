# Environment Variables

This file inventories the configuration knobs exposed by each service. All settings are read via `.env` (thanks to `pydantic-settings`) so you can override them with real environment variables in production.

## Signature Enforcement Flags

| Service | Environment Variable | Default | Notes |
|---------|----------------------|---------|-------|
| API Studio | `API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION` | `true` | Rejects lifecycle + webhook calls that do not include a valid `Clockify-Signature`. Disable only when running tests or local mock traffic. |
| Universal Webhook | `UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION` | `true` | Guards `/lifecycle/*` and `/webhooks/clockify`. |
| Clockify Python Add-on | `REQUIRE_SIGNATURE_VERIFICATION` | `true` | Enforced by `app/token_verification.py`. See `clockify-python-addon/ENV_VARS.md` for details. |

## API Studio (`api_studio/config.py`)

The service inherits `CLOCKIFY_API_BASE_URL` (reserved for future use) and `LOG_LEVEL` from `clockify_core.config.BaseClockifySettings`. `LOG_LEVEL` now powers `logging.basicConfig` in `api_studio/main.py`.

### Service Settings

| Env Var | Default | Purpose / Usage |
|---------|---------|-----------------|
| `API_STUDIO_DB_URL` | `sqlite+aiosqlite:///./api_studio.db` | SQLAlchemy DSN consumed by `api_studio.db`. Use PostgreSQL in production. |
| `API_STUDIO_ADDON_KEY` | `clockify-api-studio` | Add-on identifier used when verifying lifecycle/webhook signatures and generating the manifest. |
| `API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION` | `true` | Toggles `_verify_lifecycle_signature` / `_verify_webhook_signature`. Must remain `true` outside of tests. |
| `API_STUDIO_BOOTSTRAP_MAX_RPS` | `25` | Token-bucket ceiling passed to `clockify_core.RateLimiter` during bootstrap. |
| `API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS` | `false` | If `true`, `_filter_operations` keeps heavy endpoints (reports, exports). Otherwise they are skipped. |
| `API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS` | `90` | Used by `periodic_cleanup_task` to purge `WebhookLog` rows. |
| `API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS` | `30` | Also consumed by `periodic_cleanup_task` for `FlowExecution` pruning. |

## Universal Webhook (`universal_webhook/config.py`)

Universal Webhook inherits the same base knobs as API Studio (`CLOCKIFY_API_BASE_URL` for future multi-host support and `LOG_LEVEL` which now drives `logging.basicConfig` in `universal_webhook/main.py`).

### Service Settings

| Env Var | Default | Purpose / Usage |
|---------|---------|-----------------|
| `UNIVERSAL_WEBHOOK_DB_URL` | `sqlite+aiosqlite:///./universal_webhook.db` | SQLAlchemy DSN consumed by `universal_webhook.db`. |
| `UNIVERSAL_WEBHOOK_ADDON_KEY` | `universal-webhook-api` | Manifest/add-on identifier used when verifying signatures. |
| `UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION` | `true` | Guards lifecycle + Clockify webhook routes. |
| `UW_BOOTSTRAP_MAX_RPS` | `25` | Passed to `clockify_core.RateLimiter` during bootstrap. |
| `UW_BOOTSTRAP_INCLUDE_HEAVY` | `false` | Includes heavy GET endpoints during bootstrap when enabled. |
| `UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES` | `false` | Allows bootstrap to fetch time entries (potentially large). |
| `UW_BOOTSTRAP_TIME_ENTRY_DAYS` | `30` | How many days of time entries to fetch when the above flag is enabled. |
| `UW_BOOTSTRAP_MAX_PAGES` | `200` | Safety cap for pagination so bootstrap never runs indefinitely. |
| `UW_ENABLE_CUSTOM_WEBHOOKS` | `true` | Toggles `/webhooks/custom/{source}` routing. |
| `UW_WEBHOOK_LOG_RETENTION_DAYS` | `90` | Used by the retention job to trim `WebhookLog`. |
| `UW_ENABLE_FLOWS` | `true` | Gates all flow evaluation/dispatch logic. |
| `UW_ENABLE_GENERIC_HTTP_ACTIONS` | `false` | **Reserved:** placeholder for future outbound HTTP actions. Changing it currently has no effect beyond marking tests. |
| `UW_FLOW_EXECUTION_RETENTION_DAYS` | `90` | Controls how long completed flow executions remain in the DB. |
| `UW_CACHE_TTL_DAYS` | `7` | Determines when cached bootstrap payloads in `EntityCache` expire. |

## Clockify Python Add-on (`clockify-python-addon/app/config.py`)

The add-on exposes a much larger configuration surface (server, JWKS overrides, rate limiting, bootstrap behavior, etc.). Full descriptions live in [`clockify-python-addon/ENV_VARS.md`](clockify-python-addon/ENV_VARS.md), but for quick reference the config defines:

- **Server:** `BASE_URL`, `HOST`, `PORT`, `DEBUG`
- **Database:** `DATABASE_URL`
- **Security / Clockify:** `CLOCKIFY_JWKS_URL`, `CLOCKIFY_JWKS_PROD_URL`, `CLOCKIFY_JWKS_DEV_URL`, `CLOCKIFY_ENVIRONMENT`, `REQUIRE_SIGNATURE_VERIFICATION`, `CLOCKIFY_ALLOWED_API_DOMAINS`
- **Clockify API bases:** `CLOCKIFY_API_BASE`, `CLOCKIFY_DEVELOPER_API_BASE`, `CLOCKIFY_PTO_API_BASE`, `CLOCKIFY_REPORTS_API_BASE`
- **Rate limiting:** `RATE_LIMIT_RPS`, `RATE_LIMIT_ENABLED`
- **Redis:** `REDIS_URL`, `USE_REDIS`
- **Logging:** `LOG_LEVEL`, `LOG_FORMAT`
- **Bootstrap:** `AUTO_BOOTSTRAP_ON_INSTALL`, `BOOTSTRAP_BATCH_SIZE`, `BOOTSTRAP_MAX_RETRIES`, `BOOTSTRAP_MAX_PAGES`
- **Payload limits:** `API_CALL_MAX_PAYLOAD_BYTES`, `WEBHOOK_MAX_PAYLOAD_BYTES`
- **Webhook HTTP retries:** `WEBHOOK_REQUEST_MAX_RETRIES`, `WEBHOOK_REQUEST_BACKOFF_BASE`, `WEBHOOK_REQUEST_BACKOFF_CAP`
- **Add-on metadata:** `ADDON_KEY`, `ADDON_NAME`, `ADDON_DESCRIPTION`, `ADDON_VENDOR_NAME`, `ADDON_VENDOR_URL`

> **Host allowlist format:** `CLOCKIFY_ALLOWED_API_DOMAINS` accepts a comma-separated list of hostnames or `*.example.com` wildcards (e.g., `CLOCKIFY_ALLOWED_API_DOMAINS=*.clockify.me,api.clockify.com,developer.clockify.me`). The API caller rejects any outbound request whose hostname is not on that list.
