import contextlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import structlog
from structlog.testing import LogCapture

from app.middleware import CorrelationIdMiddleware, PayloadLimitMiddleware
from app.utils.logger import get_logger


@contextlib.contextmanager
def capture_structlog_entries():
    cap = LogCapture()
    config = structlog.get_config()
    processors = config["processors"]
    insert_at = max(len(processors) - 1, 0)
    processors.insert(insert_at, cap)
    structlog.configure(processors=processors)
    try:
        yield cap.entries
    finally:
        processors.pop(insert_at)
        structlog.configure(processors=processors)


@pytest.fixture()
def middleware_client() -> TestClient:
    app = FastAPI()
    logger = get_logger("middleware-tests")

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(PayloadLimitMiddleware, limits={"/limited": 10})

    @app.get("/ping")
    async def ping():
        logger.info("api_call_requested")
        return {"status": "ok"}

    @app.post("/limited")
    async def limited(request: Request):
        body = await request.body()
        logger.info("webhook_received", payload_size=len(body))
        return {"size": len(body)}

    @app.post("/lifecycle/install")
    async def lifecycle_install():
        logger.info("lifecycle_installed", workspace_id="ws-test")
        return {"installed": True}

    return TestClient(app)


def test_request_id_header_and_logs_present(middleware_client: TestClient):
    with capture_structlog_entries() as logs:
        api_response = middleware_client.get("/ping")
        webhook_response = middleware_client.post("/limited", data="123")
        lifecycle_response = middleware_client.post("/lifecycle/install")

    assert api_response.status_code == 200
    assert webhook_response.status_code == 200
    assert lifecycle_response.status_code == 200

    for response in (api_response, webhook_response, lifecycle_response):
        assert response.headers.get("X-Request-ID")

    for event_name in ("api_call_requested", "webhook_received", "lifecycle_installed"):
        assert any(log["event"] == event_name and "request_id" in log for log in logs)


def test_payload_limit_rejects_large_body(middleware_client: TestClient):
    too_large = middleware_client.post("/limited", data="x" * 20)
    assert too_large.status_code == 413
    body = too_large.json()
    assert body["max_bytes"] == 10
    assert body["actual_bytes"] >= 20
