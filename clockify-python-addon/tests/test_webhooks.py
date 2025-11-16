import json
from contextlib import asynccontextmanager
from typing import Dict, List
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from starlette.requests import Request

from app import webhook_router
from app.db.models import WebhookEvent
from app.utils.dedupe import dedupe_store


@pytest.mark.asyncio
async def test_webhook_storage(db_session, sample_webhook_payload, sample_workspace_id):
    """Test that webhook event is stored in database."""
    
    event_id = sample_webhook_payload["id"]
    event_type = "NEW_TIME_ENTRY"
    
    # Store webhook
    webhook = WebhookEvent(
        event_id=event_id,
        workspace_id=sample_workspace_id,
        event_type=event_type,
        payload=sample_webhook_payload,
        metadata={"source": "test"},
        processed=False
    )
    
    db_session.add(webhook)
    await db_session.commit()
    
    # Verify storage
    result = await db_session.execute(
        select(WebhookEvent).where(
            WebhookEvent.event_id == event_id
        )
    )
    stored_webhook = result.scalar_one_or_none()
    
    assert stored_webhook is not None
    assert stored_webhook.event_id == event_id
    assert stored_webhook.workspace_id == sample_workspace_id
    assert stored_webhook.event_type == event_type
    assert stored_webhook.payload == sample_webhook_payload
    assert stored_webhook.processed is False


@pytest.mark.asyncio
async def test_webhook_deduplication():
    """Test that duplicate webhooks are detected."""
    
    event_id = "test-event-123"
    
    # First call should not be duplicate
    is_dup_1 = await dedupe_store.is_duplicate(event_id)
    assert is_dup_1 is False
    
    # Second call with same ID should be duplicate
    is_dup_2 = await dedupe_store.is_duplicate(event_id)
    assert is_dup_2 is True


@pytest.mark.asyncio
async def test_webhook_different_events():
    """Test that different events are not considered duplicates."""
    
    event_id_1 = "event-1"
    event_id_2 = "event-2"
    
    # Both should not be duplicates
    is_dup_1 = await dedupe_store.is_duplicate(event_id_1)
    is_dup_2 = await dedupe_store.is_duplicate(event_id_2)
    
    assert is_dup_1 is False
    assert is_dup_2 is False


@pytest.mark.asyncio
async def test_webhook_query_by_workspace(db_session, sample_workspace_id):
    """Test querying webhooks by workspace."""
    
    # Create multiple webhooks
    for i in range(3):
        webhook = WebhookEvent(
            event_id=f"event-{i}",
            workspace_id=sample_workspace_id,
            event_type="TEST_EVENT",
            payload={"index": i},
            processed=False
        )
        db_session.add(webhook)
    
    await db_session.commit()
    
    # Query webhooks
    result = await db_session.execute(
        select(WebhookEvent).where(
            WebhookEvent.workspace_id == sample_workspace_id
        )
    )
    webhooks = result.scalars().all()
    
    assert len(webhooks) == 3


@pytest.mark.asyncio
async def test_webhook_query_by_type(db_session, sample_workspace_id):
    """Test querying webhooks by event type."""
    
    # Create webhooks with different types
    types = ["NEW_TIME_ENTRY", "TIME_ENTRY_UPDATED", "NEW_TIME_ENTRY"]
    
    for i, event_type in enumerate(types):
        webhook = WebhookEvent(
            event_id=f"event-{i}",
            workspace_id=sample_workspace_id,
            event_type=event_type,
            payload={},
            processed=False
        )
        db_session.add(webhook)
    
    await db_session.commit()
    
    # Query by specific type
    result = await db_session.execute(
        select(WebhookEvent).where(
            WebhookEvent.event_type == "NEW_TIME_ENTRY"
        )
    )
    webhooks = result.scalars().all()
    
    assert len(webhooks) == 2


def _build_request(path: str, payload: Dict[str, object]) -> Request:
    """Build a Starlette Request object for invoking router handlers directly."""
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        if receive.sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        receive.sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    receive.sent = False  # type: ignore[attr-defined]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "root_path": "",
        "scheme": "https",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "client": ("testclient", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope, receive)


def _mock_webhook_dependencies(monkeypatch, workspace_id: str) -> List[object]:
    """Patch DB + signature helpers so router handlers can be exercised in isolation."""
    recorded_sessions: List[object] = []

    class DummySession:
        def __init__(self) -> None:
            self.added: List[object] = []

        def add(self, obj) -> None:
            self.added.append(obj)

        async def commit(self) -> None:
            return None

    @asynccontextmanager
    async def fake_session():
        session = DummySession()
        recorded_sessions.append(session)
        yield session

    monkeypatch.setattr("app.webhook_router.get_db_session", fake_session)
    monkeypatch.setattr(
        "app.webhook_router.verify_webhook_signature",
        AsyncMock(return_value={"workspaceId": workspace_id}),
    )
    monkeypatch.setattr("app.webhook_router.is_duplicate_event", AsyncMock(return_value=False))
    return recorded_sessions


@pytest.mark.asyncio
async def test_time_off_request_webhook_flow(monkeypatch):
    """TIME_OFF_REQUESTED should flow through /webhooks/timeoff without drift."""
    workspace_id = "ws-timeoff"
    sessions = _mock_webhook_dependencies(monkeypatch, workspace_id)
    payload = {
        "workspaceId": workspace_id,
        "eventType": "TIME_OFF_REQUESTED",
        "id": "evt-timeoff-1",
    }
    request = _build_request("/webhooks/timeoff", payload)

    response = await webhook_router.time_off_events(
        request, payload, x_webhook_signature="signature-token"
    )
    assert response.received is True
    stored = sessions[-1].added[0]
    assert stored.workspace_id == workspace_id
    assert stored.event_type == "TIME_OFF_REQUESTED"
    assert stored.event_id == payload["id"]


@pytest.mark.asyncio
async def test_balance_updated_webhook_flow(monkeypatch):
    """BALANCE_UPDATED events map to /webhooks/balance with full persistence."""
    workspace_id = "ws-balance"
    sessions = _mock_webhook_dependencies(monkeypatch, workspace_id)
    payload = {
        "workspaceId": workspace_id,
        "eventType": "BALANCE_UPDATED",
        "id": "evt-balance-99",
    }
    request = _build_request("/webhooks/balance", payload)

    response = await webhook_router.balance_updated(
        request, payload, x_webhook_signature="signature-token"
    )
    assert response.received is True
    stored = sessions[-1].added[0]
    assert stored.workspace_id == workspace_id
    assert stored.event_type == "BALANCE_UPDATED"
