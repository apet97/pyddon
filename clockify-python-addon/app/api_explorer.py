from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from app.api_caller import execute_api_call
from app.openapi_loader import get_openapi_parser
from app.schemas.api_call import APICallRequest, APICallResponse, OpenAPIEndpoint
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ui/api-explorer", tags=["api-explorer"])


class APIExplorerExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workspace_id: str = Field(..., alias="workspaceId")
    operation_id: Optional[str] = Field(
        default=None, alias="operationId", description="Clockify operationId to execute"
    )
    method: Optional[str] = Field(
        default=None, description="HTTP method (ignored when operationId provided)"
    )
    path: Optional[str] = Field(
        default=None,
        description="API path (ignored when operationId provided, e.g. /v1/workspaces/{workspaceId}/projects)",
    )
    params: Dict[str, Any] = Field(default_factory=dict, description="Path parameters")
    query: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Dict[str, Any]] = Field(default=None, description="Request body payload")
    developer_mode: bool = Field(
        default=False, alias="developerMode", description="Use developer Clockify API"
    )


class APIExplorerService:
    """Expose OpenAPI-driven metadata for the API explorer UI."""

    def __init__(self) -> None:
        self.parser = get_openapi_parser()
        self.parser.load_spec()

    def list_endpoints(
        self, tag_filter: Optional[str] = None, method_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        endpoints = self.parser.get_all_endpoints()

        if method_filter:
            method = method_filter.upper()
            endpoints = [ep for ep in endpoints if ep.method == method]
        if tag_filter:
            tag_lower = tag_filter.lower()
            endpoints = [
                ep for ep in endpoints if any(t.lower() == tag_lower for t in ep.tags or ["Untagged"])
            ]

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for ep in endpoints:
            tags = ep.tags or ["Untagged"]
            serialized = self._serialize_endpoint(ep)
            for tag in tags:
                grouped.setdefault(tag, []).append(serialized)

        response = []
        for tag in sorted(grouped.keys(), key=str.lower):
            response.append(
                {
                    "tag": tag,
                    "count": len(grouped[tag]),
                    "endpoints": sorted(grouped[tag], key=lambda e: (e["path"], e["method"])),
                }
            )
        return response

    def find_by_operation_id(self, operation_id: str) -> Optional[OpenAPIEndpoint]:
        if not operation_id:
            return None
        for endpoint in self.parser.get_all_endpoints():
            if endpoint.operation_id == operation_id:
                return endpoint
        return None

    def _serialize_endpoint(self, endpoint: OpenAPIEndpoint) -> Dict[str, Any]:
        return {
            "operationId": endpoint.operation_id,
            "method": endpoint.method,
            "path": endpoint.path,
            "summary": endpoint.summary,
            "description": endpoint.description,
            "parameters": endpoint.parameters,
            "requestBody": endpoint.request_body,
            "tags": endpoint.tags,
        }


api_explorer_service = APIExplorerService()


@router.get("/endpoints")
async def list_api_endpoints(
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    method: Optional[str] = Query(default=None, description="Filter by HTTP method"),
):
    """List Clockify operations grouped by tag for the no-code explorer."""
    data = api_explorer_service.list_endpoints(tag_filter=tag, method_filter=method)
    return {"groups": data, "total_operations": sum(group["count"] for group in data)}


@router.post("/execute", response_model=APICallResponse)
async def execute_operation(payload: APIExplorerExecuteRequest):
    """
    Execute a Clockify API operation resolved by operationId or method/path.
    """

    method: Optional[str] = payload.method.upper() if payload.method else None
    path: Optional[str] = payload.path
    endpoint: Optional[OpenAPIEndpoint] = None

    if payload.operation_id:
        endpoint = api_explorer_service.find_by_operation_id(payload.operation_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="operationId not found in OpenAPI spec")
        method = endpoint.method
        path = endpoint.path
    else:
        if not method or not path:
            raise HTTPException(
                status_code=400,
                detail="operationId or (method and path) must be provided",
            )
        endpoint = api_explorer_service.parser.find_endpoint(method, path)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Endpoint {method} {path} not found in OpenAPI spec",
            )

    params = dict(payload.params or {})
    params.setdefault("workspaceId", payload.workspace_id)

    request = APICallRequest(
        method=method,
        endpoint=path,
        params=params,
        query=payload.query,
        body=payload.body,
        developer_mode=payload.developer_mode,
        workspace_id=payload.workspace_id,
    )

    logger.info(
        "api_explorer_execute",
        workspace_id=payload.workspace_id,
        operation_id=payload.operation_id or endpoint.operation_id,
        method=method,
        path=path,
    )

    return await execute_api_call(payload.workspace_id, request)
