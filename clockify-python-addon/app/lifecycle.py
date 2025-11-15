from datetime import datetime
from fastapi import APIRouter, Request, Header
from typing import Optional
from sqlalchemy import select
from app.config import get_settings
from app.db.models import Installation
from app.db.session import get_db_session
from app.schemas.lifecycle import (
    LifecycleInstallPayload,
    LifecycleSettingsPayload,
    LifecycleStatusPayload,
    LifecycleDeletePayload,
    LifecycleResponse
)
from app.bootstrap import start_workspace_bootstrap
from app.token_verification import resolve_signature_header, verify_lifecycle_signature
from app.utils.logger import get_logger
from app.metrics import metrics_registry

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.post("/installed", response_model=LifecycleResponse)
async def addon_installed(
    payload: LifecycleInstallPayload,
    request: Request,
    clockify_signature: Optional[str] = Header(None, alias="Clockify-Signature"),
    clockify_signature_lower: Optional[str] = Header(None, alias="clockify-signature"),
    legacy_addon_signature: Optional[str] = Header(None, alias="X-Addon-Signature")
):
    """Handle addon installation event."""
    
    logger.info(
        "lifecycle_installed",
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Verify signature and extract claims
    body = await request.body()
    signature_token = resolve_signature_header(
        clockify_signature,
        clockify_signature_lower,
        legacy_addon_signature
    )
    claims = await verify_lifecycle_signature(
        body, 
        signature_token,
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Enforce workspace consistency
    if claims.get("workspaceId") != payload.workspaceId:
        logger.error(
            "workspace_mismatch",
            claims_workspace=claims.get("workspaceId"),
            payload_workspace=payload.workspaceId
        )
        metrics_registry.record_lifecycle_event("installed", success=False)
        return LifecycleResponse(
            success=False,
            message="Workspace ID mismatch between signature and payload"
        )
    
    try:
        # Store installation
        async with get_db_session() as session:
            # Check if installation already exists
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == payload.workspaceId,
                    Installation.addon_id == payload.addonId
                )
            )
            installation = result.scalar_one_or_none()
            
            if installation:
                # Update existing installation
                installation.addon_token = payload.addonToken
                installation.api_url = payload.apiUrl
                installation.status = "ACTIVE"
                installation.updated_at = datetime.utcnow()
                installation.deleted_at = None
                logger.info("installation_updated", workspace_id=payload.workspaceId)
            else:
                # Create new installation
                installation = Installation(
                    id=f"{payload.workspaceId}:{payload.addonId}",
                    workspace_id=payload.workspaceId,
                    addon_id=payload.addonId,
                    addon_token=payload.addonToken,
                    api_url=payload.apiUrl,
                    status="ACTIVE",
                    settings={}
                )
                session.add(installation)
                logger.info("installation_created", workspace_id=payload.workspaceId)
            
            await session.commit()
            installation_id = installation.id
        
        # Register webhooks with Clockify
        try:
            from app.webhook_manager import register_webhooks, load_manifest_webhooks
            manifest_webhooks = load_manifest_webhooks()
            
            if manifest_webhooks:
                webhook_ids = await register_webhooks(
                    workspace_id=payload.workspaceId,
                    addon_token=payload.addonToken,
                    api_url=payload.apiUrl,
                    manifest_webhooks=manifest_webhooks
                )
                
                # Store webhook IDs for cleanup
                async with get_db_session() as session:
                    result = await session.execute(
                        select(Installation).where(Installation.id == installation_id)
                    )
                    inst = result.scalar_one_or_none()
                    if inst:
                        inst.webhook_ids = webhook_ids
                        await session.commit()
                        logger.info(
                            "webhooks_registered",
                            workspace_id=payload.workspaceId,
                            count=len(webhook_ids)
                        )
        except Exception as e:
            logger.error(
                "webhook_registration_failed",
                workspace_id=payload.workspaceId,
                error=str(e)
            )
        
        # Start bootstrap if enabled
        if settings.auto_bootstrap_on_install:
            bootstrap_job_id = await start_workspace_bootstrap(payload.workspaceId)
            logger.info(
                "bootstrap_triggered",
                workspace_id=payload.workspaceId,
                job_id=bootstrap_job_id
            )
        
        metrics_registry.record_lifecycle_event("installed", success=True)
        return LifecycleResponse(
            success=True,
            message="Addon installed successfully",
            data={
                "workspace_id": payload.workspaceId,
                "addon_id": payload.addonId,
                "bootstrap_enabled": settings.auto_bootstrap_on_install
            }
        )
        
    except Exception as e:
        logger.error(
            "lifecycle_installed_failed",
            workspace_id=payload.workspaceId,
            error=str(e)
        )
        metrics_registry.record_lifecycle_event("installed", success=False)
        return LifecycleResponse(
            success=False,
            message=f"Installation failed: {str(e)}"
        )


@router.post("/settings-updated", response_model=LifecycleResponse)
async def settings_updated(
    payload: LifecycleSettingsPayload,
    request: Request,
    clockify_signature: Optional[str] = Header(None, alias="Clockify-Signature"),
    clockify_signature_lower: Optional[str] = Header(None, alias="clockify-signature"),
    legacy_addon_signature: Optional[str] = Header(None, alias="X-Addon-Signature")
):
    """Handle addon settings update event."""
    
    logger.info(
        "lifecycle_settings_updated",
        workspace_id=payload.workspaceId,
        settings=payload.settings
    )
    
    # Verify signature and extract claims
    body = await request.body()
    signature_token = resolve_signature_header(
        clockify_signature,
        clockify_signature_lower,
        legacy_addon_signature
    )
    claims = await verify_lifecycle_signature(
        body, 
        signature_token,
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Enforce workspace consistency
    if claims.get("workspaceId") != payload.workspaceId:
        logger.error(
            "workspace_mismatch",
            claims_workspace=claims.get("workspaceId"),
            payload_workspace=payload.workspaceId
        )
        metrics_registry.record_lifecycle_event("settings_updated", success=False)
        return LifecycleResponse(
            success=False,
            message="Workspace ID mismatch"
        )
    
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == payload.workspaceId,
                    Installation.addon_id == payload.addonId
                )
            )
            installation = result.scalar_one_or_none()
            
            if not installation:
                logger.warning(
                    "installation_not_found",
                    workspace_id=payload.workspaceId
                )
                return LifecycleResponse(
                    success=False,
                    message="Installation not found"
                )
            
            installation.settings = payload.settings
            installation.updated_at = datetime.utcnow()
            await session.commit()
        
        logger.info(
            "settings_updated_success",
            workspace_id=payload.workspaceId
        )
        
        metrics_registry.record_lifecycle_event("settings_updated", success=True)
        return LifecycleResponse(
            success=True,
            message="Settings updated successfully",
            data={"settings": payload.settings}
        )
        
    except Exception as e:
        logger.error(
            "lifecycle_settings_update_failed",
            workspace_id=payload.workspaceId,
            error=str(e)
        )
        metrics_registry.record_lifecycle_event("settings_updated", success=False)
        return LifecycleResponse(
            success=False,
            message=f"Settings update failed: {str(e)}"
        )


@router.post("/status-changed", response_model=LifecycleResponse)
async def status_changed(
    payload: LifecycleStatusPayload,
    request: Request,
    clockify_signature: Optional[str] = Header(None, alias="Clockify-Signature"),
    clockify_signature_lower: Optional[str] = Header(None, alias="clockify-signature"),
    legacy_addon_signature: Optional[str] = Header(None, alias="X-Addon-Signature")
):
    """Handle addon status change event."""
    
    logger.info(
        "lifecycle_status_changed",
        workspace_id=payload.workspaceId,
        status=payload.status
    )
    
    # Verify signature and extract claims
    body = await request.body()
    signature_token = resolve_signature_header(
        clockify_signature,
        clockify_signature_lower,
        legacy_addon_signature
    )
    claims = await verify_lifecycle_signature(
        body, 
        signature_token,
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Enforce workspace consistency
    if claims.get("workspaceId") != payload.workspaceId:
        logger.error("workspace_mismatch")
        metrics_registry.record_lifecycle_event("status_changed", success=False)
        return LifecycleResponse(success=False, message="Workspace ID mismatch")
    
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == payload.workspaceId,
                    Installation.addon_id == payload.addonId
                )
            )
            installation = result.scalar_one_or_none()
            
            if not installation:
                logger.warning(
                    "installation_not_found",
                    workspace_id=payload.workspaceId
                )
                return LifecycleResponse(
                    success=False,
                    message="Installation not found"
                )
            
            installation.status = payload.status
            installation.updated_at = datetime.utcnow()
            await session.commit()
        
        logger.info(
            "status_changed_success",
            workspace_id=payload.workspaceId,
            new_status=payload.status
        )
        
        metrics_registry.record_lifecycle_event("status_changed", success=True)
        return LifecycleResponse(
            success=True,
            message="Status updated successfully",
            data={"status": payload.status}
        )
        
    except Exception as e:
        logger.error(
            "lifecycle_status_change_failed",
            workspace_id=payload.workspaceId,
            error=str(e)
        )
        metrics_registry.record_lifecycle_event("status_changed", success=False)
        return LifecycleResponse(
            success=False,
            message=f"Status update failed: {str(e)}"
        )


@router.post("/deleted", response_model=LifecycleResponse)
async def addon_deleted(
    payload: LifecycleDeletePayload,
    request: Request,
    clockify_signature: Optional[str] = Header(None, alias="Clockify-Signature"),
    clockify_signature_lower: Optional[str] = Header(None, alias="clockify-signature"),
    legacy_addon_signature: Optional[str] = Header(None, alias="X-Addon-Signature")
):
    """Handle addon deletion event."""
    
    logger.info(
        "lifecycle_deleted",
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Verify signature and extract claims
    body = await request.body()
    signature_token = resolve_signature_header(
        clockify_signature,
        clockify_signature_lower,
        legacy_addon_signature
    )
    claims = await verify_lifecycle_signature(
        body, 
        signature_token,
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId
    )
    
    # Enforce workspace consistency
    if claims.get("workspaceId") != payload.workspaceId:
        logger.error("workspace_mismatch")
        metrics_registry.record_lifecycle_event("deleted", success=False)
        return LifecycleResponse(success=False, message="Workspace ID mismatch")
    
    try:
        # Retrieve installation for cleanup
        webhook_ids = []
        addon_token = None
        api_url = None
        
        async with get_db_session() as session:
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == payload.workspaceId,
                    Installation.addon_id == payload.addonId
                )
            )
            installation = result.scalar_one_or_none()
            
            if not installation:
                logger.warning(
                    "installation_not_found",
                    workspace_id=payload.workspaceId
                )
                return LifecycleResponse(
                    success=True,
                    message="Installation not found (already deleted)"
                )
            
            webhook_ids = installation.webhook_ids or []
            addon_token = installation.addon_token
            api_url = installation.api_url
        
        # Delete webhooks from Clockify
        if webhook_ids and addon_token and api_url:
            try:
                from app.webhook_manager import delete_webhooks
                deleted_count = await delete_webhooks(
                    workspace_id=payload.workspaceId,
                    addon_token=addon_token,
                    api_url=api_url,
                    webhook_ids=webhook_ids
                )
                logger.info(
                    "webhooks_deleted_on_uninstall",
                    workspace_id=payload.workspaceId,
                    deleted=deleted_count
                )
            except Exception as e:
                logger.error(
                    "webhook_deletion_failed_on_uninstall",
                    workspace_id=payload.workspaceId,
                    error=str(e)
                )
        
        # Soft delete installation
        async with get_db_session() as session:
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == payload.workspaceId,
                    Installation.addon_id == payload.addonId
                )
            )
            installation = result.scalar_one_or_none()
            if installation:
                installation.status = "DELETED"
                installation.deleted_at = datetime.utcnow()
                await session.commit()
        
        logger.info(
            "deletion_success",
            workspace_id=payload.workspaceId
        )
        
        metrics_registry.record_lifecycle_event("deleted", success=True)
        return LifecycleResponse(
            success=True,
            message="Addon deleted successfully",
            data={"workspace_id": payload.workspaceId}
        )
        
    except Exception as e:
        logger.error(
            "lifecycle_deletion_failed",
            workspace_id=payload.workspaceId,
            error=str(e)
        )
        metrics_registry.record_lifecycle_event("deleted", success=False)
        return LifecycleResponse(
            success=False,
            message=f"Deletion failed: {str(e)}"
        )
