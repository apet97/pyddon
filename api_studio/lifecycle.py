from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Installation, BootstrapState
from .bootstrap import run_bootstrap_for_workspace
from .clockify_client import ClockifyClient
from clockify_core import increment_counter

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])
logger = logging.getLogger(__name__)


class InstallationPayload(BaseModel):
    """Payload received when add-on is installed in a workspace."""
    addon_id: str = None  # May be addonId or addon_id
    auth_token: str = None  # May be authToken or auth_token
    workspace_id: str = None  # May be workspaceId or workspace_id
    as_user: str | None = None  # May be asUser or as_user
    api_url: str = None  # May be apiUrl or api_url
    settings: dict | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    def model_post_init(self, __context) -> None:
        """Handle camelCase to snake_case conversion for Clockify payload."""
        # Map Clockify's camelCase to our snake_case
        if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
            if 'addonId' in self.__pydantic_extra__ and not self.addon_id:
                self.addon_id = self.__pydantic_extra__['addonId']
            if 'authToken' in self.__pydantic_extra__ and not self.auth_token:
                self.auth_token = self.__pydantic_extra__['authToken']
            if 'workspaceId' in self.__pydantic_extra__ and not self.workspace_id:
                self.workspace_id = self.__pydantic_extra__['workspaceId']
            if 'asUser' in self.__pydantic_extra__ and not self.as_user:
                self.as_user = self.__pydantic_extra__['asUser']
            if 'apiUrl' in self.__pydantic_extra__ and not self.api_url:
                self.api_url = self.__pydantic_extra__['apiUrl']


class UninstallationPayload(BaseModel):
    """Payload received when add-on is uninstalled from a workspace."""
    addon_id: str = None
    workspace_id: str = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    def model_post_init(self, __context) -> None:
        if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
            if 'addonId' in self.__pydantic_extra__ and not self.addon_id:
                self.addon_id = self.__pydantic_extra__['addonId']
            if 'workspaceId' in self.__pydantic_extra__ and not self.workspace_id:
                self.workspace_id = self.__pydantic_extra__['workspaceId']


class SettingsUpdatedPayload(BaseModel):
    """Payload received when add-on settings are updated."""
    addon_id: str = None
    workspace_id: str = None
    settings: dict | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    def model_post_init(self, __context) -> None:
        if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
            if 'addonId' in self.__pydantic_extra__ and not self.addon_id:
                self.addon_id = self.__pydantic_extra__['addonId']
            if 'workspaceId' in self.__pydantic_extra__ and not self.workspace_id:
                self.workspace_id = self.__pydantic_extra__['workspaceId']


@router.post("/installed")
async def lifecycle_installed(payload: InstallationPayload, session: AsyncSession = Depends(get_session)) -> dict:
    """Handle Clockify add-on installation.

    - Upsert Installation row for workspaceId
    - Store addon token, apiUrl, settings
    - Mark as active
    - Initialize bootstrap state
    - Optionally kick off bootstrap job
    """
    increment_counter("lifecycle.installed.total")
    
    if not payload.workspace_id or not payload.auth_token or not payload.api_url:
        increment_counter("lifecycle.installed.errors.missing_fields")
        raise HTTPException(status_code=400, detail="Missing required fields: workspaceId, authToken, or apiUrl")

    logger.info(f"Installation request for workspace {payload.workspace_id}")

    # Check if installation already exists
    stmt = select(Installation).where(Installation.workspace_id == payload.workspace_id)
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if installation:
        # Update existing installation
        logger.info(f"Updating existing installation for workspace {payload.workspace_id}")
        installation.addon_id = payload.addon_id or installation.addon_id
        installation.addon_token = payload.auth_token
        installation.api_url = payload.api_url
        installation.settings_json = payload.settings
        installation.active = True
        increment_counter("lifecycle.installed.updated")
    else:
        # Create new installation
        logger.info(f"Creating new installation for workspace {payload.workspace_id}")
        installation = Installation(
            workspace_id=payload.workspace_id,
            addon_id=payload.addon_id or "clockify-api-studio",
            api_url=payload.api_url,
            addon_token=payload.auth_token,
            settings_json=payload.settings,
            active=True
        )
        session.add(installation)
        increment_counter("lifecycle.installed.created")

    # Initialize or reset bootstrap state
    bootstrap_stmt = select(BootstrapState).where(BootstrapState.workspace_id == payload.workspace_id)
    bootstrap_result = await session.execute(bootstrap_stmt)
    bootstrap_state = bootstrap_result.scalar_one_or_none()

    if not bootstrap_state:
        bootstrap_state = BootstrapState(
            workspace_id=payload.workspace_id,
            status="PENDING",
            progress=0,
            total=0
        )
        session.add(bootstrap_state)

    await session.commit()

    # Check if we should run bootstrap automatically
    settings = payload.settings or {}
    bootstrap_on_install = settings.get("bootstrap_on_install", True)

    if bootstrap_on_install:
        logger.info(f"Triggering bootstrap for workspace {payload.workspace_id}")
        # Kick off bootstrap in background (non-blocking)
        client = ClockifyClient(base_url=payload.api_url, addon_token=payload.auth_token)
        # Fire and forget - don't await
        asyncio.create_task(_run_bootstrap_background(payload.workspace_id, client, session))

    return {"status": "ok", "message": "Installation successful"}


async def _run_bootstrap_background(workspace_id: str, client: ClockifyClient, session: AsyncSession) -> None:
    """Run bootstrap in the background."""
    try:
        await run_bootstrap_for_workspace(session, workspace_id, client)
        increment_counter("bootstrap.completed")
    except Exception as e:
        increment_counter("bootstrap.errors")
        logger.error(f"Background bootstrap failed for workspace {workspace_id}: {e}")


@router.post("/uninstalled")
async def lifecycle_uninstalled(payload: UninstallationPayload, session: AsyncSession = Depends(get_session)) -> dict:
    """Handle Clockify add-on uninstallation.

    Mark installation inactive and optionally clean up data.
    """
    increment_counter("lifecycle.uninstalled.total")
    
    if not payload.workspace_id:
        raise HTTPException(status_code=400, detail="Missing required field: workspaceId")

    logger.info(f"Uninstallation request for workspace {payload.workspace_id}")

    stmt = select(Installation).where(Installation.workspace_id == payload.workspace_id)
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if installation:
        installation.active = False
        await session.commit()
        logger.info(f"Marked installation inactive for workspace {payload.workspace_id}")

    return {"status": "ok", "message": "Uninstallation successful"}


@router.post("/settings-updated")
async def lifecycle_settings_updated(payload: SettingsUpdatedPayload, session: AsyncSession = Depends(get_session)) -> dict:
    """Handle structured settings updates from Clockify.

    Persist changes to Installation.settings_json and adjust behavior accordingly.
    """
    increment_counter("lifecycle.settings_updated.total")
    
    if not payload.workspace_id:
        raise HTTPException(status_code=400, detail="Missing required field: workspaceId")

    logger.info(f"Settings update for workspace {payload.workspace_id}")

    stmt = select(Installation).where(Installation.workspace_id == payload.workspace_id)
    result = await session.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found for this workspace")

    installation.settings_json = payload.settings
    await session.commit()
    
    logger.info(f"Settings updated for workspace {payload.workspace_id}")

    return {"status": "ok", "message": "Settings updated successfully"}
