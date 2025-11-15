# Product Spec: “Clockify API Studio” Add-on
_Add-on that can consume any Clockify webhook and perform any API call, with no-code API execution UI and automatic GET bootstrap._

---

## 1. Overview

Clockify API Studio is a generic “API + webhook console” add-on for Clockify:

- Receives all Clockify webhook events the workspace subscribes to.
- On initial load, automatically calls all eligible GET endpoints in the Clockify API (using the add-on token) to build a local data snapshot/index.
- Exposes a no-code UI where admins can:
  - Browse the Clockify API (powered by the bundled OpenAPI spec).
  - Execute any allowed API call (GET/POST/PUT/PATCH/DELETE).
  - Bind webhooks to API calls (simple automations) without writing code.

The add-on is intended as a power-tool for admins, integrators, and support/ops who want to prototype or operate automations directly against Clockify.

---

## 2. Goals & Non-Goals

### Goals

1. Make Clockify’s API fully “clickable”: discover endpoints from OpenAPI, inspect schemas, and execute calls from the UI.
2. Ingest all Clockify webhook events configured in the manifest and expose them in a structured UI.
3. Bootstrap workspace context automatically by performing GET calls across the API as soon as the add-on is first loaded (within rate-limit and safety constraints).
4. Allow admins to create simple, no-code flows: “When webhook X arrives → call API endpoint Y with mapped fields”.
5. Provide observability: execution logs, request/response inspection, error handling, and rate-limit feedback.

### Non-Goals

- Not a full-blown iPaaS with arbitrary 3rd-party connectors (v1 is Clockify-only; optional external HTTP later).
- Not a long-running ETL or data warehouse; data snapshot is for automation context, not for full analytics.
- Not an SDK; this is a UI-based no-code environment on top of the existing API.

---

## 3. Personas

1. **Workspace Admin / Owner**
   - Wants to prototype and run automations without involving engineering.
   - Needs visibility into webhooks and API responses.
2. **Technical Integrator / Support Engineer**
   - Uses the tool as an internal console for debugging webhooks and calling API endpoints.
   - Builds and maintains flows for clients/customers.

---

## 4. Key Use Cases

1. **Inspect everything**
   - Install add-on → first load triggers “full GET bootstrap”.
   - Admin opens sidebar → sees all fetched entities (clients, projects, users, tags, custom fields, policies, etc.) in a navigable tree.
2. **Debug webhooks**
   - Admin subscribes to events in Clockify UI (e.g., NEW_TIME_ENTRY, EXPENSE_CREATED).
   - Webhook hits add-on → UI shows event stream, payloads, and mapped entities.
3. **No-code API actions**
   - Admin selects “Time entry → update” endpoint.
   - Chooses method (e.g., PUT) and path parameters (workspaceId, userId, timeEntryId).
   - Fills in body using a form or JSON, with the ability to inject values from:
     - workspace context (workspaceId, userId, etc.)
     - last webhook payload.
   - Executes call and sees response and status.
4. **webhook → action flow**
   - Define rule:  
     Trigger: `NEW_TIME_ENTRY`  
     Condition: `projectId = XYZ`  
     Action: PUT `/v1/workspaces/{workspaceId}/time-entries/{id}` to attach tags/custom field values.
5. **Ad-hoc API Console**
   - Admin uses API Studio as a Postman-style console to quickly test API calls with a valid X-Addon-Token, no extra tooling.

---

## 5. High-Level Architecture

### Components

1. **Backend (Add-on Server)**
   - Exposes:
     - Manifest endpoint (`/manifest`).
     - Lifecycle endpoints (`/lifecycle/installed`, `/lifecycle/uninstalled`, `/lifecycle/settings-updated`).
     - Webhook receiver endpoint(s) (e.g. `/webhooks/clockify`).
     - API Studio REST backend for the UI (e.g. `/ui/api-explorer/*`).
   - Handles:
     - JWT & X-Addon-Token validation.
     - Rate-limited GET bootstrap using Clockify API.
     - Execution of user-defined flows.
     - Persistence of:
       - Installed workspace records.
       - Cached GET results.
       - Saved flows and mappings.
       - Webhook logs.

2. **UI (Sidebar Component)**
   - Loaded as iframe with `auth_token` (JWT) query param.
   - Communicates with backend via REST/XHR using `X-Addon-Token` header.
   - Modules:
     - Dashboard (bootstrap status + quick links).
     - Webhook Stream Viewer.
     - API Explorer & Console.
     - Flow Builder (no-code automations).

3. **Storage**
   - Workspace-scoped data:
     - `Installation` (addonId, authToken, workspaceId, apiUrl).
     - `BootstrapState` (status, last run, list of endpoints fetched).
     - `EntityCache` (per entity type, e.g., projects, clients, tags).
     - `Flows` (trigger conditions, actions, mapping configuration).
     - `ExecutionLog` (per flow execution).
     - `WebhookLog` (raw payload + parsed metadata).

---

## 6. Functional Requirements

### 6.1 Manifest & Installation

#### Manifest

- `schemaVersion`: latest supported (1.3 or higher).
- `key`: `clockify-api-studio`.
- `name`: `Clockify API Studio`.
- `baseUrl`: public URL of add-on backend.
- `minimalSubscriptionPlan`: at least `STANDARD` (or `FREE` if allowed).
- `scopes` (minimum):
  - `WORKSPACE_READ`
  - `WORKSPACE_SETTINGS_READ`
  - `TIME_ENTRY_READ`, `TIME_ENTRY_WRITE`
  - `PROJECT_READ`, `PROJECT_WRITE`
  - `CLIENT_READ`, `CLIENT_WRITE`
  - `USER_READ`
  - `TAG_READ`, `TAG_WRITE`
  - `CUSTOM_FIELDS_READ`, `CUSTOM_FIELDS_WRITE`
  - Any others required to cover desired write operations (PTO/Policy/etc.).
- `webhooks`: subscribe to all available webhook event types (or as many as supported by Clockify’s manifest spec).
- `components`:
  - Sidebar component: `/ui/dashboard`, label `API Studio`, access `ADMIN`.
  - Optional: Settings tab component or structured settings.

#### Lifecycle: Installed

- Path: `/lifecycle/installed`
- Input: Installation payload (`addonId`, `authToken`, `workspaceId`, `apiUrl`, etc.).
- Behavior:
  - Persist installation record.
  - Store long-lived add-on auth token securely (never exposed to UI).
  - Initialize `BootstrapState` with status `PENDING`.
  - Optionally enqueue “bootstrap job” immediately.

#### Lifecycle: Uninstalled

- Path: `/lifecycle/uninstalled`
- Behavior:
  - Soft-delete workspace data or wipe according to retention policy.
  - Stop processing webhooks and flows for that workspace.

#### Lifecycle: Settings updated

- Path: `/lifecycle/settings-updated` (if using structured settings).
- Behavior:
  - Reload configuration: bootstrap options, included entity groups, rate limit caps, etc.

---

### 6.2 GET Bootstrap (Initial Data Fetch)

**Objective:** “Perform all GET calls in the API as soon as it loads”, interpreted as:

- For each **eligible** GET endpoint in the Clockify API:
  - That can be called with `{workspaceId}` and safe defaults only (no arbitrary date ranges, ids that we don’t have, etc.).
  - That returns list-like entities (clients, projects, tags, users, custom fields, policies, etc.).
  - That is not clearly a heavy report (e.g., detailed reports for long ranges) unless explicitly enabled.

#### Behavior

1. **Trigger conditions:**
   - Automatic on:
     - First successful installation.
     - First admin visit to the UI after installation (if installation job failed/was skipped).
   - Manual:
     - “Rebuild workspace snapshot” button in UI (admin only).

2. **Endpoint discovery:**
   - Use bundled `openapi.json` (the one you provided) to:
     - Enumerate all `paths` with `GET` operations that:
       - Have path param `{workspaceId}`.
       - Do not require other non-optional path params (`{userId}`, `{id}`) unless we already have them from other bootstrap steps.
     - Tag each operation with:
       - Tag group (Client, Project, Tag, User, Custom fields, etc.).
       - Expected response schema (list/object).
   - Define a “core set” of entity groups to fetch first:
     - `/v1/user`
     - `/v1/workspaces`
     - `/v1/workspaces/{workspaceId}` (workspace details)
     - `/v1/workspaces/{workspaceId}/clients`
     - `/v1/workspaces/{workspaceId}/projects`
     - `/v1/workspaces/{workspaceId}/tags`
     - `/v1/workspaces/{workspaceId}/users` (if available)
     - `/v1/workspaces/{workspaceId}/custom-fields`
     - Balance/Policy/Time Off entities where safe.

3. **Rate limiting and batching:**
   - Respect Clockify X-Addon-Token rate limit: `≤ 50 requests/second` per workspace (see `Rate limiting` section in `openapi.json`).
   - Use internal throttler:
     - Configurable RPS cap (default 25 RPS to leave headroom).
     - Exponential backoff on HTTP 429 with jitter.
   - Paginate list endpoints using `page` / `page-size` query params.
     - Default `page-size`: 50 (or max safe value defined in spec).
     - Stop when empty response or last page reached.

4. **Data storage rules:**
   - Store raw JSON responses keyed by:
     - `workspaceId`
     - `entityType` (derived from tag + path)
     - `endpointId` (operationId)
   - For heavy collections (e.g. time entries), store:
     - Only headlines (id, description, projectId, userId, dates) or skip entirely unless admin enables “include time entries” in settings.
   - Track `lastBootstrapAt` and `status` per workspace.

5. **UI feedback:**
   - Dashboard shows:
     - Bootstrap status: `Not started`, `In progress`, `Complete`, `Failed`.
     - Number of endpoints fetched / total eligible endpoints.
     - Error summary (per endpoint) with retry option.

---

### 6.3 Webhook Ingestion

#### Scope

- Receive all Clockify webhook events configured in manifest (e.g. NEW_TIME_ENTRY, EXPENSE_CREATED, APPROVAL_REQUEST_STATUS_UPDATED, etc.; see `Clockify_Webhook_JSON_Samples.md`).

#### Endpoint

- Path: `/webhooks/clockify`
- HTTP method: POST
- Behavior:
  - Validate request signature/JWT (depending on final platform standard).
  - Parse event type and payload.
  - Persist event in `WebhookLog`:
    - `workspaceId`
    - `eventType`
    - `receivedAt`
    - `headers`
    - `rawPayload`
    - Derived metadata (e.g., userId, projectId, timeEntryId, etc. when available).
  - Dispatch to:
    - UI event stream (for live console, via polling or SSE).
    - Flow engine to evaluate triggers (see section 6.5).

#### UI: Webhook Stream

- Features:
  - Filter by event type, date, execution status.
  - View raw and formatted JSON.
  - Quick jump from event → related entity (using cached data from bootstrap).

---

### 6.4 No-Code API Explorer & Console

#### Objective

Allow an admin to perform any Clockify API call interactively, with UI generated from OpenAPI and contextual defaults.

#### Key Features

1. **Endpoint Catalog**
   - Driven by bundled `openapi.json`:
     - Group by tag (User, Workspace, Client, Project, Time entry, etc.).
     - Show method + path (e.g., `GET /v1/workspaces/{workspaceId}/clients`).
     - Show short description (`summary`).
   - Filters:
     - Method (GET/POST/PUT/PATCH/DELETE).
     - Requires workspace vs global.
     - Read-only vs write.

2. **Endpoint Detail Panel**
   - Shows:
     - Path template.
     - Required/optional path, query, and body parameters.
     - Sample request (cURL) and example responses (if present in OpenAPI).
   - Parameter inputs:
     - Path params: prefilled with known values (e.g., workspaceId from JWT claims; userId from current viewer).
     - Query params: text inputs, booleans, dropdowns where enums present.
     - Body:
       - Form mode (for common schemas) and JSON editor mode.

3. **Token & Environment Handling**
   - Use `auth_token` JWT claims from iframe:
     - `backendUrl` (Clockify base API URL).
     - `workspaceId`.
     - `userId`.
   - All calls issued from backend using:
     - `X-Addon-Token: <addonToken>` acquired at install (server-side).
   - UI never sees install-level token; for viewer-specific calls, it can also pass iframe token as `X-Addon-Token` when appropriate (user-level privileges).

4. **Execution & Results**
   - When admin clicks “Execute”:
     - UI posts to backend: `{workspaceId, operationId, params, body, contextBindings}`.
     - Backend:
       - Validates endpoint is part of Clockify API spec.
       - Builds HTTP request to Clockify (using `backendUrl` + path).
       - Executes with appropriate headers.
       - Logs `request`, `response` (status, headers, truncated body), `latency`.
     - UI shows:
       - HTTP status, duration.
       - Raw JSON.
       - Option to “Save as flow action” (see 6.5).

---

### 6.5 No-Code Flows (Webhook → API Calls)

#### Objective

Let admins connect webhooks to API actions via a simple rule builder.

#### Flow Model

- `Flow` (per workspace):
  - `id`
  - `name`
  - `enabled` (bool)
  - `trigger`:
    - `type`: `CLOCKIFY_WEBHOOK`
    - `eventTypes`: list (e.g. `["NEW_TIME_ENTRY"]`)
    - Optional filters:
      - JSONPath-like conditions on payload (e.g. `$.projectId == "..."`).
  - `actions`: ordered list; each action:
    - `operationId` (from OpenAPI)
    - Method & path template (derived from operation).
    - Parameter mapping:
      - Each path/query/body field can be:
        - Constant value.
        - Expression referencing webhook payload (`$.timeInterval.start`, `$.projectId`…) or previous action results.
      - Simple expression syntax only (no arbitrary code).
    - `retryPolicy` (optional).
  - `createdAt / updatedAt`.

#### Runtime Behavior

- On webhook:
  - Load set of flows for workspace where:
    - `enabled = true` and `trigger.eventTypes` contains webhook event type.
  - For each matching flow:
    - Evaluate filters.
    - Execute actions sequentially:
      - Render parameters with context values (payload + previous actions).
      - Call Clockify API (similar to API Explorer).
    - Persist `ExecutionLog`:
      - `flowId`, `webhookId`, per-action statuses, errors, and truncated responses.

#### UI: Flow Builder

- Steps:
  1. Select one or more webhook event types as trigger.
  2. Add optional conditions (basic UI for JSONPath + comparison).
  3. Add one or more actions by:
     - Picking endpoint from API Explorer.
     - Mapping parameters via:
       - Drop-downs with available payload fields.
       - Direct constants.
  4. Save & enable.

---

## 7. Non-Functional Requirements

1. **Security**
   - Validate all incoming webhook signatures/JWTs; reject invalid (403).
   - Never expose install-level auth token to UI or logs.
   - Strict multi-tenant isolation by `workspaceId`.
   - PII handling:
     - Do not log sensitive fields (emails, notes) in plain text; redact where feasible.
   - Use HTTPS for all external communication.

2. **Performance & Limits**
   - Respect 50 RPS per addon per workspace rate limit.
   - Bootstrap jobs must be resumable and chunked (no single huge run).
   - Flows must degrade gracefully when rate-limited (retry/backoff).

3. **Reliability**
   - At-least-once processing for webhooks:
     - Idempotency keys (e.g., based on Clockify webhook ID + flowId).
   - Retry policies for failed API calls:
     - On 5xx & 429 with backoff.
   - Background job worker for bootstrap and flow execution.

4. **Observability**
   - Structured logs with:
     - workspaceId, operationId, eventType, flowId, requestId.
   - Metrics:
     - Count of webhooks processed, flows executed.
     - Success/error rates per endpoint.
     - Rate-limit events, retry count.

5. **Data Retention**
   - Configurable retention (default 30–90 days) for:
     - Webhook logs.
     - Execution logs.
   - Entity cache can be recomputed via bootstrap.

---

## 8. Add-on Settings

Use structured settings (manifest-driven) or custom settings UI; minimum:

- **General**
  - Toggle: “Run automatic GET bootstrap on install” (on/off).
  - Toggle: “Include heavy report endpoints in bootstrap” (off by default).
  - Maximum RPS for bootstrap (default 25).
- **Data**
  - Include time entries in cache? (bool; if true, require restricted date range).
  - Cache TTL (e.g., 7 days).
- **Logging**
  - Keep webhook logs for N days.
  - Keep execution logs for N days.

---

## 9. UI Overview (Wireframe-Level)

1. **Sidebar → API Studio**
   - Shows:
     - Bootstrap status widget.
     - Quick counts for cached entities (projects, clients, tags, etc.).
     - Recent webhooks and recent flow executions.

2. **Tab: Webhooks**
   - Event stream list.
   - Filters (event type, status, date).
   - Detail pane with raw JSON + mapped entities.

3. **Tab: API Explorer**
   - Left: tree of tags/endpoints.
   - Right: endpoint details, parameter forms, execute button, result view.
   - “Save as flow action” button.

4. **Tab: Flows**
   - List of flows with status toggles.
   - Flow editor (trigger, filters, actions).

5. **Tab: Settings**
   - Mirrors structured settings for bootstrap & retention.

---

## 10. Implementation Notes (for engineers/AI agents)

- Use provided `openapi.json` as the canonical contract for:
  - Endpoint discovery (GET bootstrap & API Explorer).
  - Parameter forms and mapping metadata.
- Webhook payloads: refer to `Clockify_Webhook_JSON_Samples.md` for field names and event structure.
- Follow Clockify Add-on Guide for:
  - Manifest structure and hosting.
  - Lifecycle endpoints and iframe auth (`auth_token` JWT claims).
  - X-Addon-Token header usage and environment-agnostic `backendUrl` handling.

This spec should be enough for an implementation agent (Java, Node, Python, etc.) to design backend routes, data models, and UI flows for a first production-ready version of the add-on.
