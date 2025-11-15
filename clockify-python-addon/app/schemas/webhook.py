from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class WebhookPayload(BaseModel):
    """Generic webhook payload."""
    workspaceId: Optional[str] = None
    userId: Optional[str] = None
    eventType: Optional[str] = None
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(extra="allow")


class WebhookResponse(BaseModel):
    """Response for webhook endpoints."""
    received: bool = True
    event_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebhookLogEntry(BaseModel):
    """Webhook log entry for debugging."""
    id: int
    event_id: str
    workspace_id: str
    event_type: str
    payload: Dict[str, Any]
    received_at: datetime
    processed: bool
