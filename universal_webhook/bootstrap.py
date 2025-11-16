"""Bootstrap logic for Universal Webhook add-on."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient, RateLimiter, list_safe_get_operations

from .config import settings
from .models import BootstrapState, EntityCache

logger = logging.getLogger(__name__)


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
            bootstrap_state.last_error = "; ".join(errors[:5])
            logger.warning(
                "bootstrap_completed_with_errors",
                workspace_id=workspace_id,
                error_count=len(errors),
            )
        else:
            bootstrap_state.last_error = None
        await session.commit()

    except Exception as e:
        bootstrap_state.status = "FAILED"
        bootstrap_state.last_error = str(e)
        await session.commit()
        logger.exception("bootstrap_failed", workspace_id=workspace_id)
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
    path_template = operation["path"]
    actual_path = path_template
    for key, value in workspace_context.items():
        actual_path = actual_path.replace(f"{{{key}}}", value)

    entity_type = operation.get("tags", ["Unknown"])[0]
    page = 1
    page_size = 50
    total_items = 0
    max_pages = max(1, settings.bootstrap_max_pages)

    while True:
        await rate_limiter.acquire()
        params = {"page": page, "page-size": page_size}
        resp = await client.get(actual_path, params=params)
        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception as exc:
            logger.warning(
                "bootstrap_json_parse_failed",
                path=actual_path,
                page=page,
                error=str(exc),
            )
            break

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            items = []

        if not items:
            break

        for item in items:
            cache_entry = EntityCache(
                workspace_id=workspace_id,
                entity_type=entity_type,
                endpoint_id=operation["operation_id"],
                payload=item,
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(cache_entry)

        total_items += len(items)

        if len(items) < page_size:
            break

        page += 1
        if page > max_pages:
            logger.warning(
                "bootstrap_page_limit_reached",
                path=actual_path,
                max_pages=max_pages,
            )
            break

    if total_items:
        await session.commit()
