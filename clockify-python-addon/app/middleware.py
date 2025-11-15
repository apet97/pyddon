from __future__ import annotations

import uuid
from typing import Dict, Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.utils.logger import get_logger


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assign and propagate a per-request correlation ID via headers and logs."""

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        self.logger.info(
            "request_received",
            path=str(request.url.path),
            method=request.method,
            request_id=request_id,
        )

        try:
            response: Response = await call_next(request)
        except Exception as exc:  # pragma: no cover - surfaced in tests
            self.logger.error(
                "request_failed",
                path=str(request.url.path),
                request_id=request_id,
                error=str(exc),
            )
            raise
        else:
            response.headers[self.header_name] = request_id
            self.logger.info(
                "request_completed",
                path=str(request.url.path),
                status_code=response.status_code,
                request_id=request_id,
            )
            return response
        finally:
            try:
                structlog.contextvars.unbind_contextvars("request_id")
            except Exception:
                pass


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    """Enforce request payload size limits on selected path prefixes."""

    def __init__(self, app, limits: Optional[Dict[str, int]] = None):
        super().__init__(app)
        self.limits = limits or {}
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        prefix, limit = self._limit_for_path(str(request.url.path))
        if not limit:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > limit:
                    return self._reject(prefix, limit, int(content_length))
            except ValueError:
                pass

        body = await request.body()
        if len(body) > limit:
            return self._reject(prefix, limit, len(body))

        async def receive_body():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive=receive_body)
        return await call_next(request)

    def _limit_for_path(self, path: str) -> tuple[str, Optional[int]]:
        for prefix, limit in self.limits.items():
            if path.startswith(prefix):
                return prefix, limit
        return "", None

    def _reject(self, prefix: str, limit: int, actual: int) -> JSONResponse:
        self.logger.warning(
            "payload_limit_exceeded",
            path_prefix=prefix,
            limit_bytes=limit,
            actual_bytes=actual,
        )
        return JSONResponse(
            status_code=413,
            content={
                "message": f"Payload exceeds allowed size for {prefix or 'request'}",
                "max_bytes": limit,
                "actual_bytes": actual,
            },
        )
