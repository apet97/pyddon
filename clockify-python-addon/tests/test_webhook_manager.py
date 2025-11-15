import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.webhook_manager import _request_with_retry
from app.config import Settings


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, sequence):
        self.sequence = sequence
        self.calls = 0

    async def request(self, method, url, **kwargs):  # pragma: no cover - invoked via helper
        behavior = self.sequence[self.calls]
        self.calls += 1
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


@pytest.mark.asyncio
async def test_request_with_retry_succeeds_after_retries(monkeypatch):
    request = httpx.Request("POST", "https://api.clockify.me")
    client = DummyClient(
        [
            httpx.RequestError("boom", request=request),
            DummyResponse(status_code=500),
            DummyResponse(201, {"id": "abc"}),
        ]
    )

    response = await _request_with_retry(client, "POST", "https://example", json={})
    assert response.status_code == 201
    assert client.calls == 3


@pytest.mark.asyncio
async def test_request_with_retry_exhausts_attempts(monkeypatch):
    request = httpx.Request("POST", "https://api.clockify.me")
    client = DummyClient([httpx.RequestError("boom", request=request)] * 2)

    settings_override = Settings(webhook_request_max_retries=2)
    monkeypatch.setattr("app.webhook_manager.settings", settings_override)

    with pytest.raises(Exception):
        await _request_with_retry(client, "POST", "https://example", json={})
