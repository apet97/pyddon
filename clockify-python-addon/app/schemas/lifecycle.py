from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class LifecycleInstallPayload(BaseModel):
    """Payload for addon installation."""
    workspaceId: str
    addonId: str
    apiUrl: str
    addonToken: str
    userId: Optional[str] = None
    timestamp: Optional[datetime] = None


class LifecycleSettingsPayload(BaseModel):
    """Payload for settings update."""
    workspaceId: str
    addonId: str
    settings: Dict[str, Any]
    timestamp: Optional[datetime] = None


class LifecycleStatusPayload(BaseModel):
    """Payload for status change."""
    workspaceId: str
    addonId: str
    status: str
    timestamp: Optional[datetime] = None


class LifecycleDeletePayload(BaseModel):
    """Payload for addon deletion."""
    workspaceId: str
    addonId: str
    timestamp: Optional[datetime] = None


class LifecycleResponse(BaseModel):
    """Response from lifecycle endpoints."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
