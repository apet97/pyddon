from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import (
    ClockifyClient,
    RateLimiter,
    increment_counter,
    is_heavy_operation,
    list_safe_get_operations,
)

from .db import async_session_maker
from .config import settings
from .models import BootstrapState, EntityCache

logger = logging.getLogger(__name__)


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

    # Get safe GET operations with optional heavy filtering
    safe_ops = _filter_operations(list_safe_get_operations())
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
                logger.error(
                    "bootstrap_core_operation_failed",
                    workspace_id=workspace_id,
                    path=op.get("path"),
                    error=str(e),
                )

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
                logger.error(
                    "bootstrap_workspace_operation_failed",
                    workspace_id=workspace_id,
                    path=op.get("path"),
                    error=str(e),
                )

        # Mark as complete
        bootstrap_state.status = "COMPLETE" if not errors else "COMPLETE_WITH_ERRORS"
        if errors:
            bootstrap_state.last_error = "; ".join(errors[:5])  # Store first 5 errors
            logger.warning(
                "bootstrap_completed_with_errors",
                workspace_id=workspace_id,
                error_count=len(errors),
            )
        else:
            logger.info("bootstrap_completed", workspace_id=workspace_id)

    except Exception as e:
        bootstrap_state.status = "FAILED"
        bootstrap_state.last_error = str(e)
        logger.exception("bootstrap_failed", workspace_id=workspace_id)

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
                logger.warning(
                    "bootstrap_page_limit_reached",
                    path=path,
                    workspace_id=workspace_id,
                    page_limit=100,
                )
                break

        except Exception as e:
            # If first page fails, raise; otherwise, log and continue
            if page == 1:
                raise
            logger.warning(
                "bootstrap_page_fetch_failed",
                workspace_id=workspace_id,
                path=path,
                page=page,
                error=str(e),
            )
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


def _filter_operations(operations: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Filter operations based on configured flags."""
    if settings.bootstrap_include_heavy_endpoints:
        return operations
    filtered = []
    for op in operations:
        if is_heavy_operation(op):
            logger.info(
                "bootstrap_skipping_heavy_operation",
                path=op.get("path"),
                operation_id=op.get("operation_id"),
            )
            continue
        filtered.append(op)
    return filtered


async def run_bootstrap_background_task(
    workspace_id: str,
    api_url: str,
    addon_token: str,
) -> None:
    """Run bootstrap with an isolated DB session for background jobs."""
    client = ClockifyClient(base_url=api_url, addon_token=addon_token)
    async with async_session_maker() as background_session:
        try:
            await run_bootstrap_for_workspace(background_session, workspace_id, client)
            increment_counter("bootstrap.completed")
        except Exception as exc:  # pragma: no cover - background path
            increment_counter("bootstrap.errors")
            logger.error(
                "bootstrap_background_failed",
                workspace_id=workspace_id,
                error=str(exc),
            )
