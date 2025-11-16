"""Tests for Universal Webhook add-on."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from universal_webhook.db import get_db
from universal_webhook.main import create_app
from universal_webhook.models import (
    Base,
    BootstrapState,
    Flow,
    FlowExecution,
    Installation,
    EntityCache,
    WebhookLog,
)


@pytest.fixture
def test_db_url():
    """Test database URL."""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def client():
    """Create test client with in-memory test database."""
    from sqlalchemy.pool import StaticPool
    
    # Create in-memory database for testing
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    test_session_maker = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create tables
    import asyncio
    async def init_db():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    asyncio.run(init_db())
    
    app = create_app()
    
    async def override_get_db():
        async with test_session_maker() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Cleanup
    asyncio.run(test_engine.dispose())


def test_healthz(client):
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "universal-webhook"


def test_manifest_endpoint(client):
    """Test manifest endpoint serves valid JSON."""
    response = client.get("/manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "universal-webhook-api"
    assert data["schemaVersion"] == "1.3"
    assert data["minimalSubscriptionPlan"] == "ENTERPRISE"
    assert len(data["webhooks"][0]["eventTypes"]) >= 50


def test_lifecycle_installed(client):
    """Test installation endpoint."""
    payload = {
        "addonId": "test-addon-id",
        "authToken": "test-token-123",
        "workspaceId": "ws-001",
        "apiUrl": "https://api.clockify.me",
        "settings": {
            "bootstrap": {
                "run_on_install": False
            }
        }
    }
    
    response = client.post("/lifecycle/installed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "installed"
    assert data["workspaceId"] == "ws-001"


def test_lifecycle_uninstalled(client):
    """Test uninstall endpoint."""
    # Create installation first
    install_payload = {
        "addonId": "addon-002",
        "authToken": "token-002",
        "workspaceId": "ws-002",
        "apiUrl": "https://api.clockify.me",
        "settings": {"bootstrap": {"run_on_install": False}}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Uninstall
    payload = {"workspaceId": "ws-002"}
    response = client.post("/lifecycle/uninstalled", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "uninstalled"


def test_lifecycle_settings_updated(client):
    """Test settings update endpoint."""
    # Create installation
    install_payload = {
        "addonId": "addon-003",
        "authToken": "token-003",
        "workspaceId": "ws-003",
        "apiUrl": "https://api.clockify.me",
        "settings": {}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Update settings
    payload = {
        "workspaceId": "ws-003",
        "settings": {
            "bootstrap": {
                "max_rps": 30
            }
        }
    }
    response = client.post("/lifecycle/settings-updated", json=payload)
    assert response.status_code == 200


def test_clockify_webhook_receiver(client):
    """Test Clockify webhook receiver endpoint."""
    # Create installation
    install_payload = {
        "addonId": "addon-004",
        "authToken": "token-004",
        "workspaceId": "ws-004",
        "apiUrl": "https://api.clockify.me",
        "settings": {"flows": {"enable_flows": False}}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Send webhook
    payload = {
        "id": "entry-123",
        "workspaceId": "ws-004",
        "projectId": "project-456",
        "userId": "user-789"
    }
    
    headers = {
        "clockify-webhook-event-type": "NEW_TIME_ENTRY",
        "clockify-webhook-workspace-id": "ws-004"
    }
    
    response = client.post("/webhooks/clockify", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["eventType"] == "NEW_TIME_ENTRY"
    assert data["workspaceId"] == "ws-004"


def test_custom_webhook_receiver(client):
    """Test custom webhook receiver endpoint."""
    # Create installation
    install_payload = {
        "addonId": "addon-005",
        "authToken": "token-005",
        "workspaceId": "ws-005",
        "apiUrl": "https://api.clockify.me",
        "settings": {"flows": {"enable_flows": False}}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Send custom webhook
    payload = {
        "event_type": "CUSTOM_EVENT",
        "data": {"key": "value"}
    }
    
    headers = {"X-Workspace-Id": "ws-005"}
    
    response = client.post("/webhooks/custom/zapier", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["source"] == "zapier"
    assert data["workspaceId"] == "ws-005"


def test_ui_dashboard(client):
    """Test dashboard endpoint."""
    # Create installation
    install_payload = {
        "addonId": "addon-006",
        "authToken": "token-006",
        "workspaceId": "ws-006",
        "apiUrl": "https://api.clockify.me",
        "settings": {"bootstrap": {"run_on_install": False}}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Get dashboard
    response = client.get("/ui/dashboard?workspace_id=ws-006")
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == "ws-006"


def test_flow_crud(client):
    """Test flow CRUD operations."""
    # Create installation
    install_payload = {
        "addonId": "addon-007",
        "authToken": "token-007",
        "workspaceId": "ws-007",
        "apiUrl": "https://api.clockify.me",
        "settings": {}
    }
    client.post("/lifecycle/installed", json=install_payload)
    
    # Create flow
    flow_data = {
        "name": "Test Flow",
        "enabled": True,
        "trigger_source": "CLOCKIFY",
        "trigger_event_types": ["NEW_TIME_ENTRY"],
        "conditions": {
            "type": "ALL",
            "rules": [
                {"field": "$.projectId", "operator": "==", "value": "project-123"}
            ]
        },
        "actions": [
            {
                "type": "CLOCKIFY_API",
                "operation_id": "updateTimeEntry",
                "params": {
                    "path": {"workspaceId": "ws-007"},
                    "body": {"description": "Updated"}
                }
            }
        ]
    }
    
    response = client.post("/ui/flows?workspace_id=ws-007", json=flow_data)
    assert response.status_code == 200
    data = response.json()
    flow_id = data["id"]
    assert data["name"] == "Test Flow"
    
    # Get flow
    response = client.get(f"/ui/flows/{flow_id}?workspace_id=ws-007")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Flow"
    assert len(data["trigger_event_types"]) == 1
    
    # Update flow
    flow_data["name"] = "Updated Flow"
    response = client.put(f"/ui/flows/{flow_id}?workspace_id=ws-007", json=flow_data)
    assert response.status_code == 200
    
    # Delete flow
    response = client.delete(f"/ui/flows/{flow_id}?workspace_id=ws-007")
    assert response.status_code == 200


def test_api_explorer_list_endpoints(client):
    """Test API Explorer list endpoints."""
    response = client.get("/ui/api-explorer/endpoints?workspace_id=ws-008")
    assert response.status_code == 200
    data = response.json()
    assert "groups" in data
    assert "total" in data
    assert data["total"] > 0


def test_webhook_receiver_missing_workspace(client):
    """Test webhook receiver rejects requests without workspace ID."""
    payload = {"data": "test"}
    response = client.post("/webhooks/clockify", json=payload)
    assert response.status_code == 400


def test_custom_webhook_missing_header(client):
    """Test custom webhook rejects requests without X-Workspace-Id."""
    payload = {"data": "test"}
    response = client.post("/webhooks/custom/test", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_bootstrap_fetches_all_pages():
    """Ensure bootstrap helper paginates and stores every page."""
    from universal_webhook.bootstrap import _fetch_and_store_operation

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    test_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class DummyResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            return None

    class DummyClient:
        def __init__(self, pages):
            self.pages = pages

        async def get(self, path, params=None):
            page = params.get("page", 1)
            data = self.pages.get(page, [])
            return DummyResponse(data)

    class NoopLimiter:
        async def acquire(self):
            return None

    first_page = [{"id": f"p{i}"} for i in range(50)]
    second_page = [{"id": "extra-1"}, {"id": "extra-2"}]
    pages = {1: first_page, 2: second_page}
    operation = {
        "path": "/v1/workspaces/{workspaceId}/projects",
        "operation_id": "listProjects",
        "tags": ["PROJECTS"],
    }

    async with test_session_maker() as session:
        await _fetch_and_store_operation(
            session=session,
            workspace_id="ws-bootstrap",
            client=DummyClient(pages),
            operation=operation,
            rate_limiter=NoopLimiter(),
            workspace_context={"workspaceId": "ws-bootstrap"},
        )
        result = await session.execute(
            select(EntityCache).where(EntityCache.workspace_id == "ws-bootstrap")
        )
        records = result.scalars().all()

    await engine.dispose()

    expected_ids = {item["id"] for item in (first_page + second_page)}
    assert len(records) == len(expected_ids)
    assert {record.payload["id"] for record in records} == expected_ids
