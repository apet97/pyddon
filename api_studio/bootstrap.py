from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient, RateLimiter, list_safe_get_operations

from .config import settings
from .models import BootstrapState, EntityCache


async def run_bootstrap_for_workspace(session: AsyncSession, workspace_id: str, client: ClockifyClient) -> None:
    """Run the initial GET bootstrap for a workspace.

    This should:
    - Discover safe GET endpoints from the OpenAPI spec
    - Call them with appropriate path/query params (workspaceId, pagination)
    - Store results into EntityCache
    - Update BootstrapState with progress and status
    """
    # Update bootstrap state to IN_PROGRESS
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

    # Get safe GET operations
    safe_ops = list_safe_get_operations()
    bootstrap_state.total = len(safe_ops)
    await session.commit()

    # Create rate limiter
    max_rps = settings.bootstrap_max_rps
    rate_limiter = RateLimiter(max_rps)

    errors = []
    progress = 0

    try:
        # Process core endpoints first (user, workspaces)
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
                print(error_msg)

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
                print(error_msg)

        # Mark as complete
        bootstrap_state.status = "COMPLETE" if not errors else "COMPLETE_WITH_ERRORS"
        if errors:
            bootstrap_state.last_error = "; ".join(errors[:5])  # Store first 5 errors

    except Exception as e:
        bootstrap_state.status = "FAILED"
        bootstrap_state.last_error = str(e)
        print(f"Bootstrap failed for workspace {workspace_id}: {e}")

    await session.commit()


async def _fetch_and_store_operation(
    session: AsyncSession,
    workspace_id: str,
    client: ClockifyClient,
    operation: Dict[str, Any],
    rate_limiter: RateLimiter,
    workspace_context: Dict[str, str]
) -> None:
    """Fetch a single operation and store results with pagination."""
    path = operation["path"]
    operation_id = operation["operation_id"]
    tags = operation.get("tags", ["Uncategorized"])
    entity_type = tags[0] if tags else "Uncategorized"

    # Substitute path parameters
    actual_path = path
    for param_name, param_value in workspace_context.items():
        actual_path = actual_path.replace(f"{{{param_name}}}", param_value)

    # Handle pagination
    page = 1
    page_size = 50
    all_items = []

    while True:
        await rate_limiter.acquire()

        # Build query params for pagination
        params = {
            "page": str(page),
            "page-size": str(page_size)
        }

        try:
            response = await client.get(actual_path, params=params)
            response.raise_for_status()
            data = response.json() if response.content else []

            # Handle different response formats
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Some endpoints return objects, not lists
                items = [data]
            else:
                items = []

            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < page_size:
                break

            page += 1

            # Safety limit to avoid infinite loops
            if page > 100:
                print(f"Warning: Reached page limit for {path}")
                break

        except Exception as e:
            # If first page fails, raise; otherwise, log and continue
            if page == 1:
                raise
            print(f"Error fetching page {page} of {path}: {e}")
            break

    # Store in EntityCache
    if all_items:
        cache_entry = EntityCache(
            workspace_id=workspace_id,
            entity_type=entity_type,
            endpoint_id=operation_id,
            payload=all_items if isinstance(all_items, list) else all_items,
            fetched_at=datetime.now(timezone.utc)
        )
        session.add(cache_entry)
