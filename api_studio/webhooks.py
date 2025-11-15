from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clockify_client import ClockifyClient
from .db import get_session
from .flows import evaluate_and_run_flows_for_webhook
from .models import Installation, WebhookLog
from clockify_core import increment_counter, redact_sensitive_data

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/clockify")
async def receive_clockify_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    clockify_signature: str | None = Header(None, alias="Clockify-Signature")
) -> dict:
    """Receive and log Clockify webhooks.

    - Parse and validate webhook payload
    - Extract workspaceId and eventType
    - Persist WebhookLog
    - Invoke flows.evaluate_and_run_flows_for_webhook
    """
    # Increment webhook counter
    increment_counter("webhooks.received.total")
    
    # Parse request body
    body = await request.json()

    # Extract workspace ID from payload
    # Clockify webhooks typically have a workspaceId in the payload
    workspace_id = body.get("workspaceId") or body.get("workspace_id")

    if not workspace_id:
        # Try to extract from nested structures
        workspace = body.get("workspace") or {}
        workspace_id = workspace.get("id")

    if not workspace_id:
        increment_counter("webhooks.errors.missing_workspace")
        logger.warning("Webhook received without workspaceId")
        return {"status": "error", "message": "Missing workspaceId in payload"}

    # Extract event type
    event_type = body.get("eventType") or body.get("event_type") or "UNKNOWN"
    increment_counter(f"webhooks.received.{event_type}")

    # Get installation for this workspace
    stmt = select(Installation).where(
        Installation.workspace_id == workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        increment_counter("webhooks.errors.no_installation")
        logger.warning(f"Webhook for workspace {workspace_id} but no active installation")
        return {"status": "error", "message": "No active installation found for workspace"}

    # Collect headers (redact sensitive ones for logging)
    headers_dict = dict(request.headers)
    redacted_headers = redact_sensitive_data(headers_dict)
    
    logger.info(f"Webhook received: {event_type} for workspace {workspace_id}")
    logger.debug(f"Webhook headers (redacted): {redacted_headers}")

    # Store webhook in log (store full headers in DB, redact in logs)
    webhook_log = WebhookLog(
        workspace_id=workspace_id,
        event_type=event_type,
        headers=headers_dict,
        payload=body,
        received_at=datetime.now(timezone.utc)
    )
    session.add(webhook_log)
    await session.commit()

    # Refresh to get the ID
    await session.refresh(webhook_log)

    # Create Clockify client for potential flow actions
    client = ClockifyClient(
        base_url=installation.api_url,
        addon_token=installation.addon_token
    )

    # Evaluate and run flows for this webhook (fire and forget)
    try:
        await evaluate_and_run_flows_for_webhook(
            session=session,
            workspace_id=workspace_id,
            webhook=webhook_log,
            client=client
        )
    except Exception as e:
        increment_counter("webhooks.errors.flow_execution")
        logger.error(f"Error running flows for webhook {webhook_log.id}: {e}")

    return {"status": "received", "webhook_id": webhook_log.id}
