from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class APICallRequest(BaseModel):
    """Request to execute an API call."""
    method: str = Field(..., description="HTTP method (GET, POST, PUT, PATCH, DELETE)")
    endpoint: str = Field(..., description="API endpoint path")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Path parameters")
    query: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body")
    developer_mode: bool = Field(default=False, description="Use developer API endpoint")
    workspace_id: Optional[str] = Field(None, description="Workspace ID for the request")


class APICallResponse(BaseModel):
    """Response from API call execution."""
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class OpenAPIEndpoint(BaseModel):
    """Represents an endpoint from OpenAPI spec."""
    path: str
    method: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[list] = Field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[list] = Field(default_factory=list)
