"""Webhook endpoints for Universal Webhook add-on."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient

from .config import settings
from .db import async_session_maker, get_db
from .flows import evaluate_and_run_flows_for_webhook
from .models import Installation, WebhookLog

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/clockify")
async def receive_clockify_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    clockify_webhook_event_type: str | None = Header(None),
    clockify_webhook_workspace_id: str | None = Header(None),
) -> Dict[str, str]:
    """Receive and log all Clockify webhook events.
    
    This endpoint handles all 50+ Clockify webhook event types subscribed in manifest.
    Events are logged with workspace isolation and optionally trigger flows.
    """
    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    # Extract workspace ID from header or payload
    workspace_id = clockify_webhook_workspace_id
    if not workspace_id:
        workspace_id = payload.get("workspaceId")
    
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Missing workspace ID in header or payload"
        )

    # Verify installation exists and is active
    stmt = select(Installation).where(
        Installation.workspace_id == workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(
            status_code=403,
            detail=f"No active installation for workspace {workspace_id}"
        )

    # Extract event type from header or payload
    event_type = clockify_webhook_event_type
    if not event_type:
        # Some webhooks might include event type in payload
        event_type = payload.get("eventType", "UNKNOWN")

    # Get all headers as dict
    headers_dict = dict(request.headers)

    # Create webhook log entry
    webhook_log = WebhookLog(
        workspace_id=workspace_id,
        source="CLOCKIFY",
        custom_source=None,
        event_type=event_type,
        headers=headers_dict,
        payload=payload
    )
    session.add(webhook_log)
    await session.commit()
    await session.refresh(webhook_log)

    # Fire-and-forget flow evaluation if flows are enabled
    if settings.enable_flows:
        asyncio.create_task(
            _run_flow_evaluation(
                workspace_id=workspace_id,
                webhook_id=webhook_log.id,
                api_url=installation.api_url,
                addon_token=installation.addon_token,
            )
        )

    return {
        "status": "received",
        "webhookId": str(webhook_log.id),
        "eventType": event_type,
        "workspaceId": workspace_id
    }


@router.post("/custom/{source}")
async def receive_custom_webhook(
    source: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    workspace_id: str | None = Header(None, alias="X-Workspace-Id"),
) -> Dict[str, str]:
    """Receive custom webhooks from external systems.
    
    Custom webhooks are identified by source name and can trigger flows.
    Requires X-Workspace-Id header for workspace isolation.
    """
    if not settings.enable_custom_webhooks:
        raise HTTPException(
            status_code=403,
            detail="Custom webhooks are disabled in settings"
        )

    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Workspace-Id header"
        )

    # Verify installation exists and is active
    stmt = select(Installation).where(
        Installation.workspace_id == workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(
            status_code=403,
            detail=f"No active installation for workspace {workspace_id}"
        )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    # Extract event type from payload if present
    event_type = payload.get("event_type", payload.get("eventType", "CUSTOM_EVENT"))

    # Get all headers as dict
    headers_dict = dict(request.headers)

    # Create webhook log entry
    webhook_log = WebhookLog(
        workspace_id=workspace_id,
        source="CUSTOM",
        custom_source=source,
        event_type=event_type,
        headers=headers_dict,
        payload=payload
    )
    session.add(webhook_log)
    await session.commit()
    await session.refresh(webhook_log)

    # Fire-and-forget flow evaluation if flows are enabled
    if settings.enable_flows:
        asyncio.create_task(
            _run_flow_evaluation(
                workspace_id=workspace_id,
                webhook_id=webhook_log.id,
                api_url=installation.api_url,
                addon_token=installation.addon_token,
            )
        )

    return {
        "status": "received",
        "webhookId": str(webhook_log.id),
        "source": source,
        "eventType": event_type,
        "workspaceId": workspace_id
    }


async def _run_flow_evaluation(
    workspace_id: str,
    webhook_id: int,
    api_url: str,
    addon_token: str,
) -> None:
    """Evaluate flows for a webhook using a dedicated DB session."""
    client = ClockifyClient(api_url, addon_token)
    async with async_session_maker() as background_session:
        webhook = await background_session.get(WebhookLog, webhook_id)
        if not webhook:
            logger.warning(
                "webhook_not_found_for_flow_evaluation",
                workspace_id=workspace_id,
                webhook_id=webhook_id,
            )
            return
        try:
            await evaluate_and_run_flows_for_webhook(
                session=background_session,
                workspace_id=workspace_id,
                webhook=webhook,
                client=client,
            )
        except Exception as exc:
            logger.error(
                "flow_evaluation_failed",
                workspace_id=workspace_id,
                webhook_id=webhook_id,
                error=str(exc),
            )
