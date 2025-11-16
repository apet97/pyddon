import json
from pathlib import Path

from fastapi.routing import APIRoute

from app.constants import (
    CLOCKIFY_SCOPE_LIST,
    CLOCKIFY_WEBHOOK_EVENTS,
    CLOCKIFY_WEBHOOK_EVENTS_BY_PATH,
    CLOCKIFY_WEBHOOK_ROUTE_MAP,
)
from app.manifest import generate_manifest, settings
from app.webhook_router import router


def _normalize_webhook_map(webhooks, base_url: str) -> dict:
    normalized = {}
    for definition in webhooks:
        url = definition["url"]
        path = url[len(base_url):] if url.startswith(base_url) else url
        normalized[definition["event"]] = path
    return normalized


def test_manifest_generation_matches_canonical_lists(monkeypatch):
    """Manifest endpoint should emit every webhook + scope from constants."""
    custom_base = "https://example.addon"
    monkeypatch.setattr(settings, "base_url", custom_base)

    manifest = generate_manifest()
    webhook_map = _normalize_webhook_map(manifest.get("webhooks", []), custom_base)
    scopes = manifest.get("permissions", {}).get("scopes", [])

    assert webhook_map == CLOCKIFY_WEBHOOK_ROUTE_MAP
    assert sorted(webhook_map.keys()) == sorted(CLOCKIFY_WEBHOOK_EVENTS)
    assert sorted(scopes) == sorted(CLOCKIFY_SCOPE_LIST)
    assert all(wh["url"].startswith(custom_base) for wh in manifest["webhooks"])
    for lifecycle_url in manifest.get("lifecycle", {}).values():
        assert lifecycle_url.startswith(custom_base)


def test_manifest_file_is_in_sync_with_constants():
    """Raw manifest.json must mirror canonical events and scopes."""
    manifest_path = Path(__file__).resolve().parents[1] / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text())

    webhook_map = _normalize_webhook_map(
        manifest_data.get("webhooks", []),
        base_url="http://localhost:8000"
    )
    scopes = manifest_data.get("permissions", {}).get("scopes", [])

    assert webhook_map == CLOCKIFY_WEBHOOK_ROUTE_MAP
    assert sorted(webhook_map.keys()) == sorted(CLOCKIFY_WEBHOOK_EVENTS)
    assert sorted(scopes) == sorted(CLOCKIFY_SCOPE_LIST)


def test_router_exposes_every_manifest_path():
    """FastAPI router should have handlers for all canonical webhook paths."""
    route_paths = {
        route.path
        for route in router.routes
        if isinstance(route, APIRoute)
    }
    missing_paths = set(CLOCKIFY_WEBHOOK_EVENTS_BY_PATH.keys()) - route_paths
    assert not missing_paths, f"Missing webhook routes: {missing_paths}"


def test_doc_samples_match_canonical_event_list():
    """Clockify webhook sample doc must stay in sync with the runtime list."""
    doc_path = Path(__file__).resolve().parents[2] / "Clockify_Webhook_JSON_Samples.md"
    doc_events = [
        line.lstrip("# ").strip()
        for line in doc_path.read_text().splitlines()
        if line.startswith("## ")
    ]
    assert sorted(doc_events) == sorted(CLOCKIFY_WEBHOOK_EVENTS)


def test_repo_manifest_spec_covers_all_events():
    """manifest.universal-webhook.json must include every webhook our addon expects."""
    repo_root = Path(__file__).resolve().parents[3]
    spec_path = repo_root / "manifest.universal-webhook.json"
    spec_data = json.loads(spec_path.read_text())

    spec_events = set()
    for definition in spec_data.get("webhooks", []):
        event_types = definition.get("eventTypes")
        if event_types:
            spec_events.update(event_types)
        elif definition.get("event"):
            spec_events.add(definition["event"])

    assert spec_events, "Spec manifest should enumerate webhook events"
    assert spec_events == set(CLOCKIFY_WEBHOOK_EVENTS)


def test_scope_list_has_full_read_write_pairs():
    """Each requested scope must include both READ and WRITE variants."""
    resource_actions = {}
    for scope in CLOCKIFY_SCOPE_LIST:
        resource, action = scope.rsplit("_", 1)
        resource_actions.setdefault(resource, set()).add(action)

    assert all(actions == {"READ", "WRITE"} for actions in resource_actions.values())
