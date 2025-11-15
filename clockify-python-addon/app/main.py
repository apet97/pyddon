from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.config import get_settings
from app.db.session import init_db
from app.utils.logger import get_logger
from app.utils.errors import AddonError
from app.schemas.common import HealthResponse, ErrorResponse
from app.schemas.api_call import APICallRequest, APICallResponse
from app import manifest, lifecycle, webhook_router, api_caller, bootstrap, api_explorer
from app.middleware import CorrelationIdMiddleware, PayloadLimitMiddleware
from sqlalchemy import select
from app.db.models import Installation, WebhookEvent
from app.db.session import get_db_session
from typing import List, Dict, Any
from app.metrics import metrics_registry

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("application_starting", version="1.0.0")
    
    # Initialize database
    await init_db()
    logger.info("database_initialized")
    
    yield
    
    logger.info("application_shutting_down")


# Create FastAPI application
app = FastAPI(
    title=settings.addon_name,
    description=settings.addon_description,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Payload + correlation middlewares
app.add_middleware(
    PayloadLimitMiddleware,
    limits={
        "/api-call": settings.api_call_max_payload_bytes,
        "/webhooks": settings.webhook_max_payload_bytes,
    },
)
app.add_middleware(CorrelationIdMiddleware)


# Exception handlers
@app.exception_handler(AddonError)
async def addon_error_handler(request: Request, exc: AddonError):
    """Handle addon-specific errors."""
    logger.error(
        "addon_error",
        error=exc.message,
        status_code=exc.status_code,
        path=request.url.path
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            message=exc.message,
            details=exc.details
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(
        "unexpected_error",
        error=str(exc),
        path=request.url.path,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            message="Internal server error",
            details={"error": str(exc)}
        ).model_dump()
    )


# Mount static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Include routers
app.include_router(manifest.router)
app.include_router(lifecycle.router)
app.include_router(webhook_router.router)
app.include_router(api_explorer.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint - always returns healthy if app is running."""
    from datetime import datetime
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# Readiness check endpoint
@app.get("/ready")
async def readiness_check():
    """Readiness check - verifies database connectivity."""
    from datetime import datetime
    checks = {
        "database": False,
        "redis": False if not settings.use_redis else None
    }
    
    try:
        # Check database connection
        async with get_db_session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error("readiness_check_db_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "checks": checks,
                "error": "Database connection failed"
            }
        )
    
    # Check Redis if enabled
    if settings.use_redis:
        try:
            import redis.asyncio as redis
            r = redis.from_url(settings.redis_url)
            await r.ping()
            checks["redis"] = True
            await r.close()
        except Exception as e:
            logger.error("readiness_check_redis_failed", error=str(e))
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "checks": checks,
                    "error": "Redis connection failed"
                }
            )
    
    return {
        "ready": True,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(
        metrics_registry.render(),
        media_type="text/plain; version=0.0.4",
    )


# API Caller endpoint
@app.post("/api-call", response_model=APICallResponse)
async def execute_api_call(request: APICallRequest):
    """Execute a Clockify API call."""
    
    # Use workspace_id from request or default
    workspace_id = request.workspace_id or "dev-workspace"
    
    logger.info(
        "api_call_requested",
        workspace_id=workspace_id,
        endpoint=request.endpoint,
        method=request.method
    )
    
    result = await api_caller.execute_api_call(workspace_id, request)
    return result


# Bootstrap endpoints
@app.post("/bootstrap/{workspace_id}")
async def start_bootstrap(workspace_id: str):
    """Start bootstrap for a workspace."""
    job_id = await bootstrap.start_workspace_bootstrap(workspace_id)
    return {"job_id": job_id, "status": "started"}


@app.get("/bootstrap/{workspace_id}/status")
async def get_bootstrap_status(workspace_id: str):
    """Get bootstrap status for a workspace."""
    status = await bootstrap.get_bootstrap_status(workspace_id)
    return status


# UI endpoint
@app.get("/ui")
async def serve_ui():
    """Serve the API Studio UI."""
    ui_path = Path(__file__).parent.parent / "static" / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return JSONResponse(
        status_code=404,
        content={"message": "UI not found"}
    )


# Debug endpoints (development only)
if settings.is_development:
    
    @app.get("/installations")
    async def list_installations():
        """List all installations (dev only)."""
        async with get_db_session() as session:
            result = await session.execute(select(Installation))
            installations = result.scalars().all()
            return [
                {
                    "id": inst.id,
                    "workspace_id": inst.workspace_id,
                    "addon_id": inst.addon_id,
                    "status": inst.status,
                    "created_at": inst.created_at.isoformat() if inst.created_at else None,
                    "settings": inst.settings
                }
                for inst in installations
            ]
    
    @app.get("/webhooks")
    async def list_webhooks(workspace_id: str = None, limit: int = 50):
        """List received webhooks (dev only)."""
        async with get_db_session() as session:
            query = select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(limit)
            
            if workspace_id:
                query = query.where(WebhookEvent.workspace_id == workspace_id)
            
            result = await session.execute(query)
            webhooks = result.scalars().all()
            
            return [
                {
                    "id": wh.id,
                    "event_id": wh.event_id,
                    "workspace_id": wh.workspace_id,
                    "event_type": wh.event_type,
                    "payload": wh.payload,
                    "received_at": wh.received_at.isoformat() if wh.received_at else None,
                    "processed": wh.processed
                }
                for wh in webhooks
            ]
    
    @app.get("/openapi-endpoints")
    async def list_openapi_endpoints():
        """List all endpoints from OpenAPI spec (dev only)."""
        from app.openapi_loader import get_openapi_parser
        parser = get_openapi_parser()
        endpoints = parser.get_all_endpoints()
        
        return [
            {
                "path": ep.path,
                "method": ep.method,
                "operation_id": ep.operation_id,
                "summary": ep.summary,
                "tags": ep.tags
            }
            for ep in endpoints
        ]


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.addon_name,
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "manifest": "/manifest",
            "health": "/health",
            "ui": "/ui",
            "api_call": "/api-call",
            "lifecycle": "/lifecycle/*",
            "webhooks": "/webhooks/*"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
