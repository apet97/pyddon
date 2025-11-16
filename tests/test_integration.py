import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api_studio.config import settings as api_settings
from api_studio.main import app
from api_studio.db import async_session_maker
from api_studio.models import Base, Installation, BootstrapState, Flow, WebhookLog


api_settings.require_signature_verification = False
client = TestClient(app)


@pytest.fixture
async def db_session():
    """Create a clean database session for testing."""
    from api_studio.db import engine
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_manifest_endpoint():
    """Test that the manifest endpoint returns valid JSON."""
    resp = client.get("/manifest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "clockify-api-studio"
    assert data["name"] == "Clockify API Studio"
    assert "components" in data
    assert "webhooks" in data


def test_lifecycle_installed():
    """Test the installation lifecycle endpoint."""
    payload = {
        "addonId": "test-addon",
        "authToken": "test-token-123",
        "workspaceId": "ws-123",
        "apiUrl": "https://api.clockify.me",
        "settings": {}
    }
    
    resp = client.post("/lifecycle/installed", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_lifecycle_uninstalled():
    """Test the uninstallation lifecycle endpoint."""
    payload = {
        "addonId": "test-addon",
        "workspaceId": "ws-123"
    }
    
    resp = client.post("/lifecycle/uninstalled", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_api_explorer_endpoints():
    """Test that API Explorer can list endpoints from OpenAPI spec."""
    resp = client.get("/ui/api-explorer/endpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert isinstance(data["groups"], dict)
    # Should have some endpoint groups from the OpenAPI spec
    assert len(data["groups"]) > 0


def test_ui_health():
    """Test UI health endpoint."""
    resp = client.get("/ui/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_receiver_missing_workspace():
    """Test webhook receiver with missing workspace ID."""
    payload = {
        "eventType": "TIME_ENTRY_CREATED",
        "data": {"id": "123"}
    }
    
    resp = client.post("/webhooks/clockify", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "workspaceId" in data["message"]


def test_openapi_loader():
    """Test that OpenAPI loader can load and parse the spec."""
    from api_studio.openapi_loader import load_openapi, list_safe_get_operations, list_all_operations
    
    spec = load_openapi()
    assert spec is not None
    assert "paths" in spec
    assert "info" in spec
    
    # Test safe GET operations
    safe_ops = list_safe_get_operations()
    assert isinstance(safe_ops, list)
    assert len(safe_ops) > 0
    
    # Verify safe operations have required fields
    for op in safe_ops:
        assert "path" in op
        assert "operation_id" in op
        assert "method" in op
        assert op["method"] == "GET"
    
    # Test all operations
    all_ops = list_all_operations()
    assert isinstance(all_ops, list)
    assert len(all_ops) >= len(safe_ops)


def test_clockify_client_construction():
    """Test that ClockifyClient can be constructed."""
    from api_studio.clockify_client import ClockifyClient
    
    client = ClockifyClient(
        base_url="https://api.clockify.me",
        addon_token="test-token"
    )
    
    assert client.base_url == "https://api.clockify.me"
    assert client.addon_token == "test-token"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
