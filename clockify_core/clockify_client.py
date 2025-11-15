"""Clockify API client with automatic retry and rate limit handling."""
from __future__ import annotations

import logging
from typing import Any, Dict
from urllib.parse import urlparse

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class ClockifyClientError(Exception):
    """Exception raised for Clockify API client errors."""
    pass


# Approved Clockify API hosts
APPROVED_HOSTS = {
    "api.clockify.me",
    "developer.clockify.me",
    "api.clockify.dev",  # Development environment
}


class ClockifyClient:
    """Async HTTP client for Clockify API with retry and rate limit handling.
    
    Features:
    - Automatic X-Addon-Token authentication
    - Exponential backoff retry on transient errors
    - Rate limit (429) handling
    - Support for all HTTP methods
    - Host validation (only approved Clockify hosts)
    """
    
    def __init__(self, base_url: str, addon_token: str) -> None:
        """Initialize Clockify client.
        
        Args:
            base_url: Clockify API base URL (e.g., https://api.clockify.me)
            addon_token: Add-on authentication token
            
        Raises:
            ClockifyClientError: If base_url host is not approved
        """
        self.base_url = base_url.rstrip("/")
        self.addon_token = addon_token
        
        # Validate base URL is a Clockify host
        parsed = urlparse(self.base_url)
        if parsed.hostname not in APPROVED_HOSTS:
            raise ClockifyClientError(
                f"Invalid base URL host: {parsed.hostname}. "
                f"Only approved Clockify hosts are allowed: {APPROVED_HOSTS}"
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an HTTP request with retry and rate limit handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path: API endpoint path
            **kwargs: Additional arguments passed to httpx.request
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPStatusError: On non-retryable HTTP errors
        """
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers: Dict[str, str] = kwargs.pop("headers", {})
        headers["X-Addon-Token"] = self.addon_token
        
        # Log request (without token)
        logger.debug(f"Clockify API request: {method} {path}")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.request(
                        method=method, url=url, headers=headers, **kwargs
                    )
                    if resp.status_code == 429:
                        logger.warning(f"Rate limited on {method} {path}, retrying...")
                        raise httpx.HTTPStatusError(
                            "Rate limited", request=resp.request, response=resp
                        )
                    logger.debug(f"Clockify API response: {resp.status_code} for {method} {path}")
                    return resp

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request."""
        return await self._request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a PATCH request."""
        return await self._request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request."""
        return await self._request("DELETE", path, **kwargs)
