"""Lifecycle endpoints for Universal Webhook add-on."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .bootstrap import run_bootstrap_background_task
from .config import settings
from .db import get_db
from .models import BootstrapState, Installation

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


class InstallPayload(BaseModel):
    """Installation payload from Clockify."""
    addonId: str = Field(..., description="Add-on ID")
    authToken: str = Field(..., description="Add-on authentication token")
    workspaceId: str = Field(..., description="Workspace ID")
    apiUrl: str = Field(..., description="Clockify API base URL")
    settings: Dict[str, Any] | None = Field(default=None, description="Add-on settings")


class UninstallPayload(BaseModel):
    """Uninstall payload from Clockify."""
    workspaceId: str = Field(..., description="Workspace ID")


class SettingsUpdatedPayload(BaseModel):
    """Settings updated payload from Clockify."""
    workspaceId: str = Field(..., description="Workspace ID")
    settings: Dict[str, Any] = Field(..., description="Updated settings")


@router.post("/installed")
async def installed(
    payload: InstallPayload,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle add-on installation for a workspace.
    
    - Upserts installation record with addon token
    - Initializes bootstrap state
    - Optionally triggers background bootstrap job
    """
    # Check if installation already exists
    stmt = select(Installation).where(Installation.workspace_id == payload.workspaceId)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing installation
        existing.addon_id = payload.addonId
        existing.api_url = payload.apiUrl
        existing.addon_token = payload.authToken
        existing.settings_json = payload.settings
        existing.active = True
    else:
        # Create new installation
        installation = Installation(
            workspace_id=payload.workspaceId,
            addon_id=payload.addonId,
            api_url=payload.apiUrl,
            addon_token=payload.authToken,
            settings_json=payload.settings,
            active=True
        )
        session.add(installation)

    await session.commit()

    # Initialize or reset bootstrap state
    bootstrap_stmt = select(BootstrapState).where(
        BootstrapState.workspace_id == payload.workspaceId
    )
    bootstrap_result = await session.execute(bootstrap_stmt)
    bootstrap_state = bootstrap_result.scalar_one_or_none()

    # Determine if bootstrap should run based on settings
    run_bootstrap = True
    if payload.settings:
        bootstrap_settings = payload.settings.get("bootstrap", {})
        run_bootstrap = bootstrap_settings.get("run_on_install", True)

    if bootstrap_state:
        if run_bootstrap:
            bootstrap_state.status = "PENDING"
            bootstrap_state.progress = 0
            bootstrap_state.total = 0
            bootstrap_state.last_error = None
    else:
        bootstrap_state = BootstrapState(
            workspace_id=payload.workspaceId,
            status="PENDING" if run_bootstrap else "DISABLED",
            progress=0,
            total=0
        )
        session.add(bootstrap_state)

    await session.commit()

    # TODO: Trigger background bootstrap job if enabled
    # For now, we'll implement this in bootstrap.py and call it later
    if run_bootstrap:
        asyncio.create_task(
            run_bootstrap_background_task(
                workspace_id=payload.workspaceId,
                api_url=payload.apiUrl,
                addon_token=payload.authToken,
            )
        )

    return {
        "status": "installed",
        "workspaceId": payload.workspaceId,
        "bootstrap": "scheduled" if run_bootstrap else "disabled"
    }


@router.post("/uninstalled")
async def uninstalled(
    payload: UninstallPayload,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle add-on uninstallation.
    
    Marks installation as inactive (soft delete).
    """
    stmt = select(Installation).where(Installation.workspace_id == payload.workspaceId)
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    installation.active = False
    await session.commit()

    return {
        "status": "uninstalled",
        "workspaceId": payload.workspaceId
    }


@router.post("/settings-updated")
async def settings_updated(
    payload: SettingsUpdatedPayload,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Handle settings update for a workspace.
    
    Updates installation settings and can trigger actions based on new settings.
    """
    stmt = select(Installation).where(Installation.workspace_id == payload.workspaceId)
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    installation.settings_json = payload.settings
    await session.commit()

    return {
        "status": "settings_updated",
        "workspaceId": payload.workspaceId
    }
