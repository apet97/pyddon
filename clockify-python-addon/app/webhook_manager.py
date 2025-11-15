"""Webhook registration and management for Clockify addon."""

import asyncio
import random
from typing import List, Dict, Any, Iterable

import httpx

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.errors import ExternalAPIError
from app.manifest import generate_manifest

settings = get_settings()
logger = get_logger(__name__)


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retry_statuses: Iterable[int] | None = None,
    **kwargs,
) -> httpx.Response:
    retry_statuses = set(retry_statuses or {429})
    attempts = max(1, settings.webhook_request_max_retries)
    base_delay = max(0.1, settings.webhook_request_backoff_base)
    cap_delay = max(base_delay, settings.webhook_request_backoff_cap)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = await client.request(method, url, **kwargs)
            status = response.status_code
            if status >= 500 or status in retry_statuses:
                raise ExternalAPIError(
                    f"Retryable status {status}",
                    status_code=status,
                    details={"url": url, "attempt": attempt},
                )
            return response
        except (ExternalAPIError, httpx.RequestError) as exc:  # pragma: no cover - network errors
            last_error = exc
            if attempt == attempts:
                break
            sleep_for = min(cap_delay, base_delay * (2 ** (attempt - 1)))
            sleep_for += random.uniform(0, sleep_for / 2)
            logger.warning(
                "webhook_request_retry",
                method=method,
                url=url,
                attempt=attempt,
                max_attempts=attempts,
                delay=round(sleep_for, 2),
            )
            await asyncio.sleep(sleep_for)

    if isinstance(last_error, ExternalAPIError):
        raise last_error
    raise ExternalAPIError("Webhook HTTP request failed", details={"url": url})


async def register_webhooks(
    workspace_id: str,
    addon_token: str,
    api_url: str,
    manifest_webhooks: List[Dict[str, str]]
) -> List[str]:
    """
    Register webhooks with Clockify API.
    
    Args:
        workspace_id: Workspace to register webhooks for
        addon_token: Authentication token
        api_url: Base API URL from installation
        manifest_webhooks: List of webhook definitions from manifest
    
    Returns:
        List of registered webhook IDs
    
    Raises:
        ExternalAPIError: If webhook registration fails
    """
    logger.info(
        "webhook_registration_starting",
        workspace_id=workspace_id,
        webhook_count=len(manifest_webhooks)
    )
    
    webhook_ids = []
    failed_count = 0
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for webhook_def in manifest_webhooks:
            event_type = webhook_def.get("event")
            callback_url = webhook_def.get("url")
            
            # Replace localhost with actual base URL in production
            if callback_url and "localhost" in callback_url:
                callback_url = callback_url.replace(
                    "http://localhost:8000",
                    settings.base_url
                )
            
            try:
                # POST /workspaces/{workspaceId}/webhooks
                webhook_url = f"{api_url}/workspaces/{workspace_id}/webhooks"
                
                payload = {
                    "webhookUrl": callback_url,
                    "eventType": event_type
                }
                
                response = await _request_with_retry(
                    client,
                    "POST",
                    webhook_url,
                    json=payload,
                    headers={
                        "X-Addon-Token": addon_token,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in (200, 201):
                    webhook_data = response.json()
                    webhook_id = webhook_data.get("id")
                    if webhook_id:
                        webhook_ids.append(webhook_id)
                        logger.info(
                            "webhook_registered",
                            workspace_id=workspace_id,
                            event_type=event_type,
                            webhook_id=webhook_id
                        )
                    else:
                        logger.warning(
                            "webhook_registered_no_id",
                            workspace_id=workspace_id,
                            event_type=event_type,
                            response=webhook_data
                        )
                else:
                    failed_count += 1
                    logger.error(
                        "webhook_registration_failed",
                        workspace_id=workspace_id,
                        event_type=event_type,
                        status_code=response.status_code,
                        response=response.text
                    )
            
            except Exception as e:
                failed_count += 1
                logger.error(
                    "webhook_registration_error",
                    workspace_id=workspace_id,
                    event_type=event_type,
                    error=str(e)
                )
    
    logger.info(
        "webhook_registration_complete",
        workspace_id=workspace_id,
        registered=len(webhook_ids),
        failed=failed_count,
        total=len(manifest_webhooks)
    )
    
    return webhook_ids


async def delete_webhooks(
    workspace_id: str,
    addon_token: str,
    api_url: str,
    webhook_ids: List[str]
) -> int:
    """
    Delete webhooks from Clockify API.
    
    Args:
        workspace_id: Workspace to delete webhooks from
        addon_token: Authentication token
        api_url: Base API URL
        webhook_ids: List of webhook IDs to delete
    
    Returns:
        Number of successfully deleted webhooks
    """
    if not webhook_ids:
        logger.info("no_webhooks_to_delete", workspace_id=workspace_id)
        return 0
    
    logger.info(
        "webhook_deletion_starting",
        workspace_id=workspace_id,
        webhook_count=len(webhook_ids)
    )
    
    deleted_count = 0
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for webhook_id in webhook_ids:
            try:
                # DELETE /workspaces/{workspaceId}/webhooks/{webhookId}
                webhook_url = f"{api_url}/workspaces/{workspace_id}/webhooks/{webhook_id}"
                
                response = await _request_with_retry(
                    client,
                    "DELETE",
                    webhook_url,
                    headers={"X-Addon-Token": addon_token},
                    retry_statuses={429, 500, 502, 503, 504},
                )

                if response.status_code in (200, 204, 404):
                    deleted_count += 1
                    logger.info(
                        "webhook_deleted",
                        workspace_id=workspace_id,
                        webhook_id=webhook_id,
                        status_code=response.status_code
                    )
                else:
                    logger.error(
                        "webhook_deletion_failed",
                        workspace_id=workspace_id,
                        webhook_id=webhook_id,
                        status_code=response.status_code,
                        response=response.text
                    )
            
            except Exception as e:
                logger.error(
                    "webhook_deletion_error",
                    workspace_id=workspace_id,
                    webhook_id=webhook_id,
                    error=str(e)
                )
    
    logger.info(
        "webhook_deletion_complete",
        workspace_id=workspace_id,
        deleted=deleted_count,
        total=len(webhook_ids)
    )
    
    return deleted_count


def load_manifest_webhooks() -> List[Dict[str, str]]:
    """Load webhook definitions from the active manifest."""
    try:
        manifest = generate_manifest()
        return manifest.get("webhooks", [])
    except Exception as e:
        logger.error("manifest_load_error", error=str(e))
        return []
