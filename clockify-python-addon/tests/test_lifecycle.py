import pytest
from sqlalchemy import select
from app.db.models import Installation
from app.schemas.lifecycle import LifecycleInstallPayload


@pytest.mark.asyncio
async def test_installation_storage(db_session, sample_lifecycle_install_payload):
    """Test that installation is properly stored in database."""
    
    payload = LifecycleInstallPayload(**sample_lifecycle_install_payload)
    
    # Create installation
    installation = Installation(
        id=f"{payload.workspaceId}:{payload.addonId}",
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId,
        addon_token=payload.addonToken,
        api_url=payload.apiUrl,
        status="ACTIVE",
        settings={}
    )
    
    db_session.add(installation)
    await db_session.commit()
    
    # Verify installation was stored
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == payload.workspaceId
        )
    )
    stored_installation = result.scalar_one_or_none()
    
    assert stored_installation is not None
    assert stored_installation.workspace_id == payload.workspaceId
    assert stored_installation.addon_id == payload.addonId
    assert stored_installation.addon_token == payload.addonToken
    assert stored_installation.status == "ACTIVE"


@pytest.mark.asyncio
async def test_installation_update(db_session, sample_lifecycle_install_payload):
    """Test that existing installation can be updated."""
    
    payload = LifecycleInstallPayload(**sample_lifecycle_install_payload)
    
    # Create initial installation
    installation = Installation(
        id=f"{payload.workspaceId}:{payload.addonId}",
        workspace_id=payload.workspaceId,
        addon_id=payload.addonId,
        addon_token="old-token",
        api_url=payload.apiUrl,
        status="ACTIVE"
    )
    db_session.add(installation)
    await db_session.commit()
    
    # Update installation
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == payload.workspaceId
        )
    )
    existing = result.scalar_one()
    existing.addon_token = payload.addonToken
    await db_session.commit()
    
    # Verify update
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == payload.workspaceId
        )
    )
    updated = result.scalar_one()
    assert updated.addon_token == payload.addonToken


@pytest.mark.asyncio
async def test_settings_update(db_session, sample_workspace_id, sample_addon_id):
    """Test that settings can be updated."""
    
    # Create installation
    installation = Installation(
        id=f"{sample_workspace_id}:{sample_addon_id}",
        workspace_id=sample_workspace_id,
        addon_id=sample_addon_id,
        addon_token="test-token",
        api_url="https://api.clockify.me/api/v1",
        status="ACTIVE",
        settings={}
    )
    db_session.add(installation)
    await db_session.commit()
    
    # Update settings
    new_settings = {
        "developer_mode": True,
        "logging_level": "DEBUG"
    }
    
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == sample_workspace_id
        )
    )
    existing = result.scalar_one()
    existing.settings = new_settings
    await db_session.commit()
    
    # Verify settings
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == sample_workspace_id
        )
    )
    updated = result.scalar_one()
    assert updated.settings == new_settings


@pytest.mark.asyncio
async def test_soft_deletion(db_session, sample_workspace_id, sample_addon_id):
    """Test that installation is soft deleted."""
    
    # Create installation
    installation = Installation(
        id=f"{sample_workspace_id}:{sample_addon_id}",
        workspace_id=sample_workspace_id,
        addon_id=sample_addon_id,
        addon_token="test-token",
        api_url="https://api.clockify.me/api/v1",
        status="ACTIVE"
    )
    db_session.add(installation)
    await db_session.commit()
    
    # Soft delete
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == sample_workspace_id
        )
    )
    existing = result.scalar_one()
    existing.status = "DELETED"
    await db_session.commit()
    
    # Verify soft deletion
    result = await db_session.execute(
        select(Installation).where(
            Installation.workspace_id == sample_workspace_id
        )
    )
    deleted = result.scalar_one()
    assert deleted.status == "DELETED"
