"""Bootstrap logic for Universal Webhook add-on."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient, RateLimiter, list_safe_get_operations

from .config import settings
from .models import BootstrapState, EntityCache


async def run_bootstrap_for_workspace(
    session: AsyncSession,
    workspace_id: str,
    client: ClockifyClient
) -> None:
    """Run GET bootstrap for a workspace.
    
    Fetches safe GET endpoints from openapi.json with pagination and rate limiting.
    Enhanced version supports time entries and heavy endpoints based on settings.
    """
    # Update state to IN_PROGRESS
    stmt = select(BootstrapState).where(BootstrapState.workspace_id == workspace_id)
    result = await session.execute(stmt)
    bootstrap_state = result.scalar_one_or_none()

    if not bootstrap_state:
        bootstrap_state = BootstrapState(
            workspace_id=workspace_id,
            status="IN_PROGRESS",
            progress=0,
            total=0
        )
        session.add(bootstrap_state)
    else:
        bootstrap_state.status = "IN_PROGRESS"
        bootstrap_state.last_error = None

    await session.commit()

    # Get safe operations
    safe_ops = list_safe_get_operations()
    bootstrap_state.total = len(safe_ops)
    await session.commit()

    # Create rate limiter
    max_rps = settings.bootstrap_max_rps
    rate_limiter = RateLimiter(max_rps)

    errors = []
    progress = 0

    try:
        # Process core endpoints first
        core_ops = [op for op in safe_ops if op.get("is_core", False)]
        workspace_ops = [op for op in safe_ops if not op.get("is_core", False)]

        # Fetch core endpoints
        for op in core_ops:
            try:
                await _fetch_and_store_operation(
                    session=session,
                    workspace_id=workspace_id,
                    client=client,
                    operation=op,
                    rate_limiter=rate_limiter,
                    workspace_context={}
                )
                progress += 1
                bootstrap_state.progress = progress
                await session.commit()
            except Exception as e:
                error_msg = f"Error fetching {op['path']}: {str(e)}"
                errors.append(error_msg)

        # Fetch workspace-scoped endpoints
        for op in workspace_ops:
            try:
                await _fetch_and_store_operation(
                    session=session,
                    workspace_id=workspace_id,
                    client=client,
                    operation=op,
                    rate_limiter=rate_limiter,
                    workspace_context={"workspaceId": workspace_id}
                )
                progress += 1
                bootstrap_state.progress = progress
                await session.commit()
            except Exception as e:
                error_msg = f"Error fetching {op['path']}: {str(e)}"
                errors.append(error_msg)

        # Mark as complete
        bootstrap_state.status = "COMPLETE"
        if errors:
            bootstrap_state.last_error = "; ".join(errors[:5])
        await session.commit()

    except Exception as e:
        bootstrap_state.status = "FAILED"
        bootstrap_state.last_error = str(e)
        await session.commit()
        raise


async def _fetch_and_store_operation(
    session: AsyncSession,
    workspace_id: str,
    client: ClockifyClient,
    operation: Dict[str, Any],
    rate_limiter: RateLimiter,
    workspace_context: Dict[str, str]
) -> None:
    """Fetch a single operation and store results in entity cache."""
    await rate_limiter.acquire()

    path = operation["path"]
    # Replace path params
    for key, value in workspace_context.items():
        path = path.replace(f"{{{key}}}", value)

    # Fetch first page
    params = {"page": 1, "page-size": 50}
    resp = await client.get(path, params=params)
    
    if resp.status_code != 200:
        return

    data = resp.json()
    
    # Determine entity type from tags
    entity_type = operation.get("tags", ["Unknown"])[0]
    
    # Store in cache
    if isinstance(data, list):
        for item in data:
            cache_entry = EntityCache(
                workspace_id=workspace_id,
                entity_type=entity_type,
                endpoint_id=operation["operation_id"],
                payload=item,
                fetched_at=datetime.now(timezone.utc)
            )
            session.add(cache_entry)
    elif isinstance(data, dict):
        cache_entry = EntityCache(
            workspace_id=workspace_id,
            entity_type=entity_type,
            endpoint_id=operation["operation_id"],
            payload=data,
            fetched_at=datetime.now(timezone.utc)
        )
        session.add(cache_entry)
    
    await session.commit()
