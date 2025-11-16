from __future__ import annotations

from typing import Any, Dict

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clockify_client import ClockifyClient
from .db import get_session
from .models import Installation
from .openapi_loader import get_operation_by_id, list_all_operations

router = APIRouter(prefix="/ui/api-explorer", tags=["api-explorer"])
logger = logging.getLogger(__name__)


@router.get("/endpoints")
async def list_endpoints() -> dict:
    """Return a grouped list of API endpoints from the Clockify OpenAPI spec.

    Groups operations by tag for easy navigation in the UI.
    """
    operations = list_all_operations()
    
    # Group by tags
    grouped: Dict[str, list] = {}
    for op in operations:
        tags = op.get("tags", ["Uncategorized"])
        tag = tags[0] if tags else "Uncategorized"
        
        if tag not in grouped:
            grouped[tag] = []
        
        grouped[tag].append({
            "operation_id": op["operation_id"],
            "method": op["method"],
            "path": op["path"],
            "summary": op["summary"]
        })
    
    return {"groups": grouped}


class ExecuteRequest(BaseModel):
    """Request to execute an API operation."""
    workspace_id: str
    operation_id: str
    path_params: Dict[str, Any] = {}
    query_params: Dict[str, Any] = {}
    body: Any = None


@router.post("/execute")
async def execute_endpoint(
    request: ExecuteRequest,
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Execute a Clockify API call via the backend.

    Validates the operation against OpenAPI spec, resolves parameters,
    and executes the call using the workspace's ClockifyClient.
    """
    # Get installation for workspace
    stmt = select(Installation).where(
        Installation.workspace_id == request.workspace_id,
        Installation.active == True
    )
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()
    
    if not installation:
        raise HTTPException(status_code=404, detail="No active installation for workspace")
    
    # Get operation details from OpenAPI
    op_info = get_operation_by_id(request.operation_id)
    if not op_info:
        raise HTTPException(status_code=400, detail=f"Operation {request.operation_id} not found")
    
    logger.info(
        "api_explorer_execute",
        workspace_id=request.workspace_id,
        operation_id=request.operation_id,
        method=op_info["method"],
        path=op_info["path"],
    )
    
    # Build path with parameters
    path = op_info["path"]
    for param_name, param_value in request.path_params.items():
        path = path.replace(f"{{{param_name}}}", str(param_value))
    
    # Create client
    client = ClockifyClient(
        base_url=installation.api_url,
        addon_token=installation.addon_token
    )
    
    # Execute request
    method = op_info["method"]
    request_kwargs = {}
    
    if request.query_params:
        request_kwargs["params"] = request.query_params
    
    if request.body is not None:
        request_kwargs["json"] = request.body
    
    try:
        if method == "GET":
            response = await client.get(path, **request_kwargs)
        elif method == "POST":
            response = await client.post(path, **request_kwargs)
        elif method == "PUT":
            response = await client.put(path, **request_kwargs)
        elif method == "PATCH":
            response = await client.patch(path, **request_kwargs)
        elif method == "DELETE":
            response = await client.delete(path, **request_kwargs)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")
        
        # Parse response
        try:
            response_data = response.json() if response.content else None
        except Exception:
            response_data = None
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "data": response_data
        }
    
    except Exception as e:
        logger.error(
            "api_explorer_execute_failed",
            workspace_id=request.workspace_id,
            operation_id=request.operation_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"API call failed: {str(e)}")
