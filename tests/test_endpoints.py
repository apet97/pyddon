"""Tests for new hardening endpoints (metrics, health)."""
import pytest
from httpx import AsyncClient, ASGITransport

from api_studio.main import app as api_studio_app
from universal_webhook.main import app as universal_webhook_app


@pytest.mark.asyncio
async def test_api_studio_metrics_endpoint():
    """Test that metrics endpoint returns Prometheus format."""
    transport = ASGITransport(app=api_studio_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        text = response.text
        assert "# HELP" in text
        assert "# TYPE" in text
        assert "addon_uptime_seconds" in text


@pytest.mark.asyncio
async def test_universal_webhook_metrics_endpoint():
    """Test that metrics endpoint returns Prometheus format."""
    transport = ASGITransport(app=universal_webhook_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        
        assert response.status_code == 200
        assert "# HELP" in response.text
        assert "addon_uptime_seconds" in response.text


@pytest.mark.asyncio
async def test_api_studio_health_with_db():
    """Test enhanced health check."""
    transport = ASGITransport(app=api_studio_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "database" in data
        assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_universal_webhook_health_with_db():
    """Test enhanced health check."""
    transport = ASGITransport(app=universal_webhook_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "service" in data
        assert "database" in data
        assert data["service"] == "universal-webhook"
