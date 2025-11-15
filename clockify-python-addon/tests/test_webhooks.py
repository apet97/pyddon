import pytest
from sqlalchemy import select
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
