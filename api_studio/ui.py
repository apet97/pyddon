from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import BootstrapState, EntityCache, Flow, FlowExecution, WebhookLog

router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/health")
async def ui_health() -> dict:
    return {"status": "ok"}


@router.get("/dashboard")
async def ui_dashboard(
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Return high-level dashboard data for the sidebar.
    
    Includes bootstrap status, entity counts, flow counts, and recent webhook activity.
    """
    # Get bootstrap state
    bootstrap_stmt = select(BootstrapState).where(BootstrapState.workspace_id == workspace_id)
    bootstrap_result = await session.execute(bootstrap_stmt)
    bootstrap_state = bootstrap_result.scalar_one_or_none()
    
    bootstrap_data = {
        "status": bootstrap_state.status if bootstrap_state else "NOT_STARTED",
        "progress": bootstrap_state.progress if bootstrap_state else 0,
        "total": bootstrap_state.total if bootstrap_state else 0,
        "last_error": bootstrap_state.last_error if bootstrap_state else None,
        "updated_at": bootstrap_state.updated_at.isoformat() if bootstrap_state else None,
    }
    status_labels = {
        "NOT_STARTED": "Bootstrap has not been started.",
        "PENDING": "Bootstrap is queued or currently running.",
        "RUNNING": "Bootstrap is processing workspace data.",
        "COMPLETE": "Bootstrap finished successfully.",
        "FAILED": "Bootstrap failed. Review the error and retry.",
        "DISABLED": "Bootstrap is disabled for this workspace.",
    }
    bootstrap_data["status_label"] = status_labels.get(
        bootstrap_data["status"], "Status unknown."
    )
    
    # Count cached entities by type
    entity_count_stmt = select(
        EntityCache.entity_type,
        func.count(EntityCache.id).label("count")
    ).where(EntityCache.workspace_id == workspace_id).group_by(EntityCache.entity_type)
    entity_count_result = await session.execute(entity_count_stmt)
    entity_counts = {row[0]: row[1] for row in entity_count_result}
    
    # Count flows
    flow_count_stmt = select(func.count(Flow.id)).where(Flow.workspace_id == workspace_id)
    flow_count_result = await session.execute(flow_count_stmt)
    flow_count = flow_count_result.scalar()
    
    # Count enabled flows
    enabled_flow_count_stmt = select(func.count(Flow.id)).where(
        Flow.workspace_id == workspace_id,
        Flow.enabled == True
    )
    enabled_flow_count_result = await session.execute(enabled_flow_count_stmt)
    enabled_flow_count = enabled_flow_count_result.scalar()
    
    # Recent webhooks (last 24 hours)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_webhook_stmt = select(func.count(WebhookLog.id)).where(
        WebhookLog.workspace_id == workspace_id,
        WebhookLog.received_at >= recent_cutoff
    )
    recent_webhook_result = await session.execute(recent_webhook_stmt)
    recent_webhook_count = recent_webhook_result.scalar()
    
    # Recent flow executions (last 24 hours)
    recent_execution_stmt = select(func.count(FlowExecution.id)).where(
        FlowExecution.workspace_id == workspace_id,
        FlowExecution.created_at >= recent_cutoff
    )
    recent_execution_result = await session.execute(recent_execution_stmt)
    recent_execution_count = recent_execution_result.scalar()

    total_entities = sum(entity_counts.values())
    entity_summary = (
        f"{total_entities} cached entities across {len(entity_counts)} types"
        if total_entities
        else "No cached entities yet"
    )

    flows_summary = (
        f"{enabled_flow_count} of {flow_count} flows enabled"
        if flow_count
        else "No flows created yet"
    )

    recent_summary = (
        f"{recent_webhook_count} webhooks / {recent_execution_count} flow runs in last 24h"
        if (recent_webhook_count or recent_execution_count)
        else "No activity in the last 24h"
    )
    
    return {
        "workspace_id": workspace_id,
        "bootstrap": bootstrap_data,
        "entity_counts": {
            "by_type": entity_counts,
            "total": total_entities,
            "summary": entity_summary
        },
        "flows": {
            "total": flow_count,
            "enabled": enabled_flow_count,
            "summary": flows_summary
        },
        "recent_activity": {
            "webhooks_24h": recent_webhook_count,
            "executions_24h": recent_execution_count,
            "summary": recent_summary
        }
    }


@router.get("/webhooks")
async def list_webhooks(
    workspace_id: str = Query(...),
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """List webhooks for a workspace with optional filtering."""
    stmt = select(WebhookLog).where(WebhookLog.workspace_id == workspace_id)
    
    if event_type:
        stmt = stmt.where(WebhookLog.event_type == event_type)
    
    stmt = stmt.order_by(WebhookLog.received_at.desc()).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    count_stmt = select(func.count(WebhookLog.id)).where(WebhookLog.workspace_id == workspace_id)
    if event_type:
        count_stmt = count_stmt.where(WebhookLog.event_type == event_type)
    total_result = await session.execute(count_stmt)
    total_records = total_result.scalar()
    has_more = (offset + len(webhooks)) < total_records
    
    return {
        "workspace_id": workspace_id,
        "pagination": {
            "total": total_records,
            "limit": limit,
            "offset": offset,
            "has_more": has_more
        },
        "webhooks": [
            {
                "id": w.id,
                "event_type": w.event_type,
                "received_at": w.received_at.isoformat(),
                "payload": w.payload,
                "summary": f"{w.event_type} received {w.received_at.isoformat()}"
            }
            for w in webhooks
        ]
    }


@router.get("/webhooks/{webhook_id}")
async def get_webhook(
    webhook_id: int,
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Get details of a specific webhook."""
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
        "event_type": webhook.event_type,
        "headers": webhook.headers,
        "payload": webhook.payload,
        "received_at": webhook.received_at.isoformat()
    }


class FlowCreateRequest(BaseModel):
    name: str
    enabled: bool = True
    trigger_event_types: List[str]
    conditions: Dict[str, Any] | None = None
    actions: List[Dict[str, Any]]


class FlowUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    trigger_event_types: List[str] | None = None
    conditions: Dict[str, Any] | None = None
    actions: List[Dict[str, Any]] | None = None


@router.get("/flows")
async def list_flows(
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """List all flows for a workspace."""
    stmt = select(Flow).where(Flow.workspace_id == workspace_id).order_by(Flow.created_at.desc())
    result = await session.execute(stmt)
    flows = result.scalars().all()
    total = len(flows)
    enabled = sum(1 for f in flows if f.enabled)
    summary = (
        f"{enabled} of {total} flows enabled"
        if total
        else "No flows have been configured for this workspace"
    )
    
    return {
        "workspace_id": workspace_id,
        "total": total,
        "enabled": enabled,
        "summary": summary,
        "flows": [
            {
                "id": f.id,
                "name": f.name,
                "enabled": f.enabled,
                "trigger_event_types": f.trigger_event_types,
                "conditions": f.conditions,
                "actions": f.actions,
                "created_at": f.created_at.isoformat(),
                "updated_at": f.updated_at.isoformat()
            }
            for f in flows
        ]
    }


@router.post("/flows")
async def create_flow(
    request: FlowCreateRequest,
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Create a new flow."""
    flow = Flow(
        workspace_id=workspace_id,
        name=request.name,
        enabled=request.enabled,
        trigger_event_types=request.trigger_event_types,
        conditions=request.conditions,
        actions=request.actions
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    
    return {
        "id": flow.id,
        "name": flow.name,
        "enabled": flow.enabled,
        "trigger_event_types": flow.trigger_event_types,
        "conditions": flow.conditions,
        "actions": flow.actions,
        "created_at": flow.created_at.isoformat(),
        "updated_at": flow.updated_at.isoformat()
    }


@router.get("/flows/{flow_id}")
async def get_flow(
    flow_id: int,
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Get details of a specific flow."""
    stmt = select(Flow).where(Flow.id == flow_id, Flow.workspace_id == workspace_id)
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    return {
        "id": flow.id,
        "name": flow.name,
        "enabled": flow.enabled,
        "trigger_event_types": flow.trigger_event_types,
        "conditions": flow.conditions,
        "actions": flow.actions,
        "created_at": flow.created_at.isoformat(),
        "updated_at": flow.updated_at.isoformat()
    }


@router.put("/flows/{flow_id}")
async def update_flow(
    flow_id: int,
    request: FlowUpdateRequest,
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Update an existing flow."""
    stmt = select(Flow).where(Flow.id == flow_id, Flow.workspace_id == workspace_id)
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    if request.name is not None:
        flow.name = request.name
    if request.enabled is not None:
        flow.enabled = request.enabled
    if request.trigger_event_types is not None:
        flow.trigger_event_types = request.trigger_event_types
    if request.conditions is not None:
        flow.conditions = request.conditions
    if request.actions is not None:
        flow.actions = request.actions
    
    await session.commit()
    await session.refresh(flow)
    
    return {
        "id": flow.id,
        "name": flow.name,
        "enabled": flow.enabled,
        "trigger_event_types": flow.trigger_event_types,
        "conditions": flow.conditions,
        "actions": flow.actions,
        "created_at": flow.created_at.isoformat(),
        "updated_at": flow.updated_at.isoformat()
    }


@router.delete("/flows/{flow_id}")
async def delete_flow(
    flow_id: int,
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Delete a flow."""
    stmt = select(Flow).where(Flow.id == flow_id, Flow.workspace_id == workspace_id)
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    await session.delete(flow)
    await session.commit()
    
    return {"status": "deleted", "id": flow_id}


@router.get("/flows/{flow_id}/executions")
async def list_flow_executions(
    flow_id: int,
    workspace_id: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """List executions for a specific flow."""
    stmt = select(FlowExecution).where(
        FlowExecution.flow_id == flow_id,
        FlowExecution.workspace_id == workspace_id
    ).order_by(FlowExecution.created_at.desc()).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    executions = result.scalars().all()
    
    return {
        "executions": [
            {
                "id": e.id,
                "flow_id": e.flow_id,
                "webhook_log_id": e.webhook_log_id,
                "status": e.status,
                "detail": e.detail,
                "actions_result": e.actions_result,
                "created_at": e.created_at.isoformat()
            }
            for e in executions
        ]
    }


@router.post("/bootstrap/trigger")
async def trigger_bootstrap(
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Manually trigger bootstrap for a workspace."""
    from .bootstrap import run_bootstrap_for_workspace
    from .clockify_client import ClockifyClient
    from .models import Installation
    import asyncio
    
    # Get installation
    stmt = select(Installation).where(
        Installation.workspace_id == workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()
    
    if not installation:
        raise HTTPException(status_code=404, detail="No active installation for workspace")
    
    # Create client
    client = ClockifyClient(
        base_url=installation.api_url,
        addon_token=installation.addon_token
    )
    
    # Trigger bootstrap in background
    asyncio.create_task(run_bootstrap_for_workspace(session, workspace_id, client))
    
    return {"status": "triggered", "message": "Bootstrap started in background"}
