# Prompt for Claude Code – Clockify API Studio (Python)

Use this text as your initial prompt inside Claude Code when this repo is mounted:

> You are Claude Code, a coding agent working on a Python FastAPI service that will serve as
> a Clockify add-on called **Clockify API Studio**.
>
> Your job is to:
> - Read the spec and docs under `docs/` (especially `clockify-api-studio-spec.md`).
> - Implement the FastAPI backend in `api_studio/` following the package layout and stubs.
> - Wire Alembic migrations for the models.
> - Implement the endpoints and behavior so that Clockify can:
>   - Call lifecycle endpoints.
>   - Send webhooks to `/webhooks/clockify`.
>   - Use the sidebar UI (served under `/ui` and related APIs) for:
>     - Dashboard (bootstrap status).
>     - Webhook stream.
>     - API Explorer.
>     - Flows.
>
> Read and follow:
> - docs/clockify-api-studio-spec.md
> - docs/openapi.json
> - docs/Clockify_Webhook_JSON_Samples.md
> - docs/Clockify_Addon_Guide.md
> - docs/ARCHITECTURE_API_STUDIO_PY.md
> - docs/IMPLEMENTATION_CHECKLIST_API_STUDIO_PY.md
> - docs/CONFIG_NOTES_API_STUDIO_PY.md
> - docs/SECURITY_AND_LIMITS_API_STUDIO_PY.md
> - docs/FLOW_EXAMPLES_API_STUDIO.md
>
> Then implement the backend with small, incremental changes, running tests frequently.
