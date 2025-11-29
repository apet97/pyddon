"""Main FastAPI application for Universal Webhook add-on."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import api_explorer, lifecycle, ui, webhooks
from .config import settings
from .db import get_db
from .models import EntityCache, FlowExecution, WebhookLog
from clockify_core import get_metrics_collector, run_retention_cleanup

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO)
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Universal Webhook starting up...")
        stop_event = asyncio.Event()
        cleanup_task = asyncio.create_task(periodic_cleanup_task(stop_event))
        try:
            yield
        finally:
            stop_event.set()
            with suppress(asyncio.CancelledError):
                await cleanup_task

    app = FastAPI(
        title="Universal Webhook + Any API Call",
        version="0.1.0",
        description="Enterprise Clockify add-on for universal webhook ingestion and API operations",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(lifecycle.router)
    app.include_router(webhooks.router)
    app.include_router(api_explorer.router)
    app.include_router(ui.router)

    @app.get("/healthz")
    async def healthz(session: AsyncSession = Depends(get_db)) -> dict:
        """Health check endpoint with DB connectivity."""
        try:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {str(e)}"

        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "service": "universal-webhook",
            "database": db_status
        }

    @app.get("/ready")
    async def ready(session: AsyncSession = Depends(get_db)) -> dict:
        """
        Readiness check endpoint with comprehensive dependency validation.

        Returns 200 if service can accept traffic, 503 if not ready.
        Used by Kubernetes and Docker Compose for orchestration.
        """
        checks = {
            "database": False,
            "service": "universal-webhook"
        }

        try:
            # Check database connectivity
            await session.execute(text("SELECT 1"))
            checks["database"] = True

            # All checks must pass
            all_ready = checks["database"]

            if not all_ready:
                return JSONResponse(
                    status_code=503,
                    content={
                        "ready": False,
                        "checks": checks
                    }
                )

            return {
                "ready": True,
                "checks": checks
            }
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "checks": checks,
                    "error": str(e)
                }
            )

    @app.get("/manifest")
    async def manifest() -> JSONResponse:
        """Serve the add-on manifest for Clockify."""
        manifest_path = Path(__file__).resolve().parents[1] / "manifest.universal-webhook.json"
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        return JSONResponse(content=manifest_data)
    
    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        """Prometheus-style metrics endpoint."""
        collector = get_metrics_collector()
        return collector.get_prometheus_format()

    return app


async def periodic_cleanup_task(stop_event: asyncio.Event):
    """Periodically clean up old records based on retention settings."""
    while not stop_event.is_set():
        try:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=86400)
                break
            except asyncio.TimeoutError:
                pass
            
            logger.info("Starting periodic data retention cleanup...")
            
            from .db import async_session_maker
            async with async_session_maker() as session:
                cleanup_tasks = [
                    (WebhookLog, "received_at", settings.webhook_log_retention_days),
                    (FlowExecution, "created_at", settings.flow_execution_retention_days),
                    (EntityCache, "fetched_at", settings.cache_ttl_days),
                ]

                results = await run_retention_cleanup(session, cleanup_tasks)
                
                for table, result in results.items():
                    if result["status"] == "success":
                        logger.info(
                            f"Cleaned up {result['deleted']} records from {table} "
                            f"(retention: {result['retention_days']} days)"
                        )
                    else:
                        logger.error(f"Failed to clean up {table}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error in periodic cleanup task: {e}")
            await asyncio.sleep(5)
    logger.info("Periodic cleanup task stopped")


app = create_app()
