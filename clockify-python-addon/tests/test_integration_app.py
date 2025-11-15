from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_client(monkeypatch):
    async def fake_init_db():
        return None

    @asynccontextmanager
    async def fake_db_session():
        class DummySession:
            async def execute(self, *_args, **_kwargs):
                class DummyResult:
                    def scalar_one_or_none(self):
                        return 1

                    def scalar_one(self):
                        return 1

                return DummyResult()
        yield DummySession()

    monkeypatch.setattr("app.main.init_db", fake_init_db)
    monkeypatch.setattr("app.main.get_db_session", fake_db_session)

    from app.main import app

    with TestClient(app) as client:
        yield client


def test_health_ready_metrics_endpoints(app_client):
    health = app_client.get("/health")
    assert health.status_code == 200
    ready = app_client.get("/ready")
    assert ready.status_code == 200
    metrics = app_client.get("/metrics")
    assert metrics.status_code == 200
    assert "clockify_api_calls_total" in metrics.text


def test_manifest_reflects_base_url(monkeypatch, app_client):
    monkeypatch.setattr("app.manifest.settings.base_url", "https://integration.example")
    manifest = app_client.get("/manifest")
    assert manifest.status_code == 200
    data = manifest.json()
    assert data["baseUrl"] == "https://integration.example"


def test_api_explorer_execute_endpoint(monkeypatch, app_client):
    async def fake_execute(workspace_id, request):  # pragma: no cover - patched function
        return {
            "success": True,
            "status_code": 200,
            "response_body": {"workspace": workspace_id, "endpoint": request.endpoint},
            "duration_ms": 12,
        }

    monkeypatch.setattr("app.api_explorer.execute_api_call", fake_execute)

    payload = {
        "workspaceId": "ws-integration",
        "method": "GET",
        "path": "/v1/workspaces/{workspaceId}/projects",
        "params": {"workspaceId": "ws-integration"},
        "query": {},
        "body": None
    }

    resp = app_client.post("/ui/api-explorer/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["response_body"]["workspace"] == "ws-integration"
