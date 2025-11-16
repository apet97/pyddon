"""API Explorer endpoints for Universal Webhook add-on."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient, get_operation_by_id, list_all_operations

from .db import get_db
from .models import Installation

router = APIRouter(prefix="/ui/api-explorer", tags=["api-explorer"])
logger = logging.getLogger(__name__)


class ExecuteRequest(BaseModel):
    """Request to execute a Clockify API operation."""
    operation_id: str = Field(..., description="Operation ID from OpenAPI spec")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters: {path: {}, query: {}, body: {}}"
    )


@router.get("/endpoints")
async def list_endpoints(
    workspace_id: str = Query(..., description="Workspace ID"),
    tag: str | None = Query(None, description="Filter by tag"),
    method: str | None = Query(None, description="Filter by HTTP method"),
) -> Dict[str, Any]:
    """List all Clockify API operations from OpenAPI spec.
    
    Returns all operations (not just safe GET) for the API Explorer.
    Supports filtering by tag and method.
    """
    all_ops = list_all_operations()
    
    # Filter by tag if specified
    if tag:
        all_ops = [op for op in all_ops if tag in op.get("tags", [])]
    
    # Filter by method if specified
    if method:
        all_ops = [op for op in all_ops if op["method"].upper() == method.upper()]
    
    # Group by tag
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for op in all_ops:
        for tag_name in op.get("tags", ["Uncategorized"]):
            if tag_name not in grouped:
                grouped[tag_name] = []
            
            grouped[tag_name].append({
                "operation_id": op["operation_id"],
                "method": op["method"],
                "path": op["path"],
                "summary": op["summary"]
            })
    
    return {
        "workspace_id": workspace_id,
        "total": len(all_ops),
        "groups": grouped
    }


@router.post("/execute")
async def execute_operation(
    request: ExecuteRequest,
    workspace_id: str = Query(..., description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute any Clockify API operation.
    
    Validates operation_id, builds request, and executes via ClockifyClient.
    Returns response data and metadata (status, latency).
    """
    # Get installation for workspace
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

    # Get operation from OpenAPI spec
    operation = get_operation_by_id(request.operation_id)
    if not operation:
        raise HTTPException(
            status_code=404,
            detail=f"Operation not found: {request.operation_id}"
        )
    
    logger.info(
        "uw_api_explorer_execute",
        workspace_id=workspace_id,
        operation_id=request.operation_id,
        method=operation["method"],
        path=operation["path"],
    )

    # Build request
    path = operation["path"]
    method = operation["method"]
    
    # Replace path parameters
    path_params = request.params.get("path", {})
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", str(value))
    
    # Create client
    client = ClockifyClient(installation.api_url, installation.addon_token)
    
    # Execute request with timing
    import time
    start_time = time.time()
    
    try:
        query_params = request.params.get("query", {})
        body = request.params.get("body", {})
        
        if method == "GET":
            resp = await client.get(path, params=query_params)
        elif method == "POST":
            resp = await client.post(path, params=query_params, json=body)
        elif method == "PUT":
            resp = await client.put(path, params=query_params, json=body)
        elif method == "PATCH":
            resp = await client.patch(path, params=query_params, json=body)
        elif method == "DELETE":
            resp = await client.delete(path, params=query_params)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported method: {method}"
            )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "status": "success",
            "status_code": resp.status_code,
            "data": resp.json() if resp.content else None,
            "metadata": {
                "operation_id": request.operation_id,
                "method": method,
                "path": path,
                "latency_ms": latency_ms
            }
        }
    
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "uw_api_explorer_execute_failed",
            workspace_id=workspace_id,
            operation_id=request.operation_id,
            method=method,
            path=path,
            error=str(e),
        )
        return {
            "status": "error",
            "error": str(e),
            "metadata": {
                "operation_id": request.operation_id,
                "method": method,
                "path": path,
                "latency_ms": latency_ms
            }
        }
