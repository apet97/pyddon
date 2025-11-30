"""UI endpoints for Universal Webhook add-on."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .bootstrap import run_bootstrap_background_task
from .db import get_db
from .models import (
    BootstrapState,
    EntityCache,
    Flow,
    FlowExecution,
    Installation,
    WebhookLog,
)

router = APIRouter(prefix="/ui", tags=["ui"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "universal-webhook"}


@router.get("/dashboard")
async def dashboard(
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Dashboard with bootstrap status, entity counts, and flow statistics."""
    # Get installation
    inst_stmt = select(Installation).where(Installation.workspace_id == workspace_id)
    inst_result = await session.execute(inst_stmt)
    installation = inst_result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    # Get bootstrap state
    bs_stmt = select(BootstrapState).where(BootstrapState.workspace_id == workspace_id)
    bs_result = await session.execute(bs_stmt)
    bootstrap_state = bs_result.scalar_one_or_none()

    bootstrap_status = {
        "status": bootstrap_state.status if bootstrap_state else "NOT_STARTED",
        "progress": bootstrap_state.progress if bootstrap_state else 0,
        "total": bootstrap_state.total if bootstrap_state else 0,
        "last_error": bootstrap_state.last_error if bootstrap_state else None,
        "updated_at": (
            bootstrap_state.updated_at.isoformat() if bootstrap_state else None
        ),
    }

    # Entity counts by type
    entity_stmt = (
        select(EntityCache.entity_type, func.count(EntityCache.id))
        .where(EntityCache.workspace_id == workspace_id)
        .group_by(EntityCache.entity_type)
    )
    entity_result = await session.execute(entity_stmt)
    entity_counts = {row[0]: row[1] for row in entity_result}

    # Flow statistics
    flow_stmt = select(func.count(Flow.id)).where(Flow.workspace_id == workspace_id)
    flow_result = await session.execute(flow_stmt)
    total_flows = flow_result.scalar_one()

    flow_enabled_stmt = select(func.count(Flow.id)).where(
        Flow.workspace_id == workspace_id, Flow.enabled == True
    )
    flow_enabled_result = await session.execute(flow_enabled_stmt)
    enabled_flows = flow_enabled_result.scalar_one()

    # Recent activity (last 24 hours)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    webhook_stmt = select(func.count(WebhookLog.id)).where(
        WebhookLog.workspace_id == workspace_id,
        WebhookLog.received_at >= yesterday
    )
    webhook_result = await session.execute(webhook_stmt)
    recent_webhooks = webhook_result.scalar_one()

    execution_stmt = select(func.count(FlowExecution.id)).where(
        FlowExecution.workspace_id == workspace_id,
        FlowExecution.created_at >= yesterday
    )
    execution_result = await session.execute(execution_stmt)
    recent_executions = execution_result.scalar_one()

    entity_total = sum(entity_counts.values())
    entity_summary = (
        f"{entity_total} cached entities across {len(entity_counts)} types"
        if entity_total
        else "No cached entities yet"
    )
    flow_summary = (
        f"{enabled_flows} of {total_flows} flows enabled"
        if total_flows
        else "No flows configured yet"
    )
    activity_summary = (
        f"{recent_webhooks} webhooks / {recent_executions} flow runs in last 24h"
        if (recent_webhooks or recent_executions)
        else "No webhook or flow activity in the last 24h"
    )

    return {
        "workspace_id": workspace_id,
        "bootstrap": bootstrap_status,
        "entity_counts": {
            "by_type": entity_counts,
            "total": entity_total,
            "summary": entity_summary,
        },
        "flows": {
            "total": total_flows,
            "enabled": enabled_flows,
            "summary": flow_summary,
        },
        "recent_activity": {
            "webhooks_24h": recent_webhooks,
            "flow_executions_24h": recent_executions,
            "summary": activity_summary,
        },
    }


@router.get("/webhooks")
async def list_webhooks(
    workspace_id: str = Query(..., description="Workspace ID"),
    source: str | None = Query(None, description="Filter by source (CLOCKIFY/CUSTOM)"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=100, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List webhook logs with filtering and pagination."""
    # Build query
    conditions = [WebhookLog.workspace_id == workspace_id]
    
    if source:
        conditions.append(WebhookLog.source == source)
    
    if event_type:
        conditions.append(WebhookLog.event_type == event_type)
    
    stmt = (
        select(WebhookLog)
        .where(and_(*conditions))
        .order_by(WebhookLog.received_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    # Count total
    count_stmt = select(func.count(WebhookLog.id)).where(and_(*conditions))
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    has_more = (offset + len(webhooks)) < total

    return {
        "workspace_id": workspace_id,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        },
        "webhooks": [
            {
                "id": w.id,
                "source": w.source,
                "custom_source": w.custom_source,
                "event_type": w.event_type,
                "received_at": w.received_at.isoformat(),
                "summary": (
                    f"{w.source} :: {w.event_type} "
                    f"({w.received_at.astimezone(timezone.utc).isoformat()})"
                ),
            }
            for w in webhooks
        ],
    }


@router.get("/webhooks/{webhook_id}")
async def get_webhook_details(
    webhook_id: int,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get webhook details including full payload."""
    stmt = select(WebhookLog).where(
        WebhookLog.id == webhook_id,
        WebhookLog.workspace_id == workspace_id
    )
    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {
        "id": webhook.id,
        "workspace_id": webhook.workspace_id,
        "source": webhook.source,
        "custom_source": webhook.custom_source,
        "event_type": webhook.event_type,
        "headers": webhook.headers,
        "payload": webhook.payload,
        "received_at": webhook.received_at.isoformat(),
    }


class FlowCreate(BaseModel):
    """Flow creation request."""
    name: str = Field(..., max_length=255)
    enabled: bool = Field(default=True)
    trigger_source: str = Field(default="CLOCKIFY")
    trigger_event_types: List[str] = Field(...)
    conditions: Dict[str, Any] | None = Field(default=None)
    actions: List[Dict[str, Any]] = Field(...)


@router.get("/flows")
async def list_flows(
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all flows for workspace."""
    stmt = (
        select(Flow)
        .where(Flow.workspace_id == workspace_id)
        .order_by(Flow.created_at.desc())
    )
    result = await session.execute(stmt)
    flows = result.scalars().all()

    total_flows = len(flows)
    enabled_flows = sum(1 for f in flows if f.enabled)
    flow_summary = (
        f"{enabled_flows} of {total_flows} flows enabled"
        if total_flows
        else "No flows configured yet"
    )

    return {
        "workspace_id": workspace_id,
        "total": total_flows,
        "enabled": enabled_flows,
        "summary": flow_summary,
        "flows": [
            {
                "id": f.id,
                "name": f.name,
                "enabled": f.enabled,
                "trigger_source": f.trigger_source,
                "trigger_event_types": f.trigger_event_types,
                "created_at": f.created_at.isoformat(),
                "updated_at": f.updated_at.isoformat(),
            }
            for f in flows
        ],
    }


@router.post("/flows")
async def create_flow(
    flow_data: FlowCreate,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new flow."""
    flow = Flow(
        workspace_id=workspace_id,
        name=flow_data.name,
        enabled=flow_data.enabled,
        trigger_source=flow_data.trigger_source,
        trigger_event_types=flow_data.trigger_event_types,
        conditions=flow_data.conditions,
        actions=flow_data.actions,
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)

    return {
        "id": flow.id,
        "name": flow.name,
        "enabled": flow.enabled,
        "created_at": flow.created_at.isoformat(),
    }


@router.get("/flows/{flow_id}")
async def get_flow(
    flow_id: int,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get flow details."""
    stmt = select(Flow).where(
        Flow.id == flow_id,
        Flow.workspace_id == workspace_id
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    return {
        "id": flow.id,
        "workspace_id": flow.workspace_id,
        "name": flow.name,
        "enabled": flow.enabled,
        "trigger_source": flow.trigger_source,
        "trigger_event_types": flow.trigger_event_types,
        "conditions": flow.conditions,
        "actions": flow.actions,
        "created_at": flow.created_at.isoformat(),
        "updated_at": flow.updated_at.isoformat(),
    }


@router.put("/flows/{flow_id}")
async def update_flow(
    flow_id: int,
    flow_data: FlowCreate,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update a flow."""
    stmt = select(Flow).where(
        Flow.id == flow_id,
        Flow.workspace_id == workspace_id
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow.name = flow_data.name
    flow.enabled = flow_data.enabled
    flow.trigger_source = flow_data.trigger_source
    flow.trigger_event_types = flow_data.trigger_event_types
    flow.conditions = flow_data.conditions
    flow.actions = flow_data.actions

    await session.commit()

    return {"status": "updated", "id": flow.id}


@router.delete("/flows/{flow_id}")
async def delete_flow(
    flow_id: int,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Delete a flow."""
    stmt = select(Flow).where(
        Flow.id == flow_id,
        Flow.workspace_id == workspace_id
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    await session.delete(flow)
    await session.commit()

    return {"status": "deleted", "id": str(flow_id)}


@router.get("/flows/{flow_id}/executions")
async def list_flow_executions(
    flow_id: int,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List executions for a flow."""
    stmt = (
        select(FlowExecution)
        .where(
            FlowExecution.flow_id == flow_id,
            FlowExecution.workspace_id == workspace_id
        )
        .order_by(FlowExecution.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    executions = result.scalars().all()

    return {
        "flow_id": flow_id,
        "total": len(executions),
        "executions": [
            {
                "id": e.id,
                "webhook_log_id": e.webhook_log_id,
                "status": e.status,
                "detail": e.detail,
                "created_at": e.created_at.isoformat(),
            }
            for e in executions
        ],
    }


@router.post("/bootstrap/trigger")
async def trigger_bootstrap(
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Manually trigger bootstrap for workspace."""
    # Get installation
    stmt = select(Installation).where(
        Installation.workspace_id == workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    asyncio.create_task(
        run_bootstrap_background_task(
            workspace_id=workspace_id,
            api_url=installation.api_url,
            addon_token=installation.addon_token,
        )
    )

    return {
        "status": "scheduled",
        "workspace_id": workspace_id
    }
