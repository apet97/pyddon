import asyncio
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import select
from app.config import get_settings
from app.db.models import BootstrapJob, WorkspaceData, Installation
from app.db.session import get_db_session
from app.openapi_loader import get_openapi_parser
from app.schemas.api_call import APICallRequest, OpenAPIEndpoint
from app.api_caller import execute_api_call
from app.utils.logger import get_logger
from app.metrics import metrics_registry

settings = get_settings()
logger = get_logger(__name__)


class BootstrapService:
    """Service to bootstrap workspace data by calling all safe GET endpoints."""
    
    def __init__(self):
        self.openapi = get_openapi_parser()
        self.openapi.load_spec()
    
    async def start_bootstrap(self, workspace_id: str) -> int:
        """Start bootstrap job for a workspace."""
        
        logger.info("bootstrap_starting", workspace_id=workspace_id)
        
        # Create bootstrap job
        async with get_db_session() as session:
            job = BootstrapJob(
                workspace_id=workspace_id,
                status="PENDING"
            )
            session.add(job)
            await session.commit()
            job_id = job.id
        
        # Run bootstrap in background
        asyncio.create_task(self._run_bootstrap(job_id, workspace_id))
        
        return job_id
    
    async def _run_bootstrap(self, job_id: int, workspace_id: str) -> None:
        """Execute bootstrap process."""
        
        try:
            # Update job status
            async with get_db_session() as session:
                result = await session.execute(
                    select(BootstrapJob).where(BootstrapJob.id == job_id)
                )
                job = result.scalar_one()
                job.status = "RUNNING"
                job.started_at = datetime.utcnow()
                await session.commit()
            
            # Get safe GET endpoints
            endpoints = self.openapi.get_get_endpoints()
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(BootstrapJob).where(BootstrapJob.id == job_id)
                )
                job = result.scalar_one()
                job.total_endpoints = len(endpoints)
                await session.commit()
            
            logger.info(
                "bootstrap_endpoints_found",
                workspace_id=workspace_id,
                count=len(endpoints)
            )
            
            # Process endpoints in batches
            completed = 0
            failed = 0
            errors = []
            results = {}
            
            for i in range(0, len(endpoints), settings.bootstrap_batch_size):
                batch = endpoints[i:i + settings.bootstrap_batch_size]
                
                tasks = [
                    self._fetch_endpoint_data(workspace_id, ep)
                    for ep in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for endpoint, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        failed += 1
                        error_msg = f"{endpoint.path}: {str(result)}"
                        errors.append(error_msg)
                        logger.error(
                            "bootstrap_endpoint_failed",
                            workspace_id=workspace_id,
                            endpoint=endpoint.path,
                            error=str(result)
                        )
                    else:
                        completed += 1
                        results[endpoint.path] = {
                            "count": len(result) if isinstance(result, list) else 1,
                            "fetched_at": datetime.utcnow().isoformat()
                        }
                
                # Update progress
                async with get_db_session() as session:
                    result = await session.execute(
                        select(BootstrapJob).where(BootstrapJob.id == job_id)
                    )
                    job = result.scalar_one()
                    job.completed_endpoints = completed
                    job.failed_endpoints = failed
                    job.errors = errors
                    job.results = results
                    await session.commit()
                
                logger.info(
                    "bootstrap_batch_completed",
                    workspace_id=workspace_id,
                    completed=completed,
                    failed=failed,
                    total=len(endpoints)
                )
            
            # Mark job as completed
            async with get_db_session() as session:
                result = await session.execute(
                    select(BootstrapJob).where(BootstrapJob.id == job_id)
                )
                job = result.scalar_one()
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                await session.commit()
            
            logger.info(
                "bootstrap_completed",
                workspace_id=workspace_id,
                completed=completed,
                failed=failed
            )
            metrics_registry.record_bootstrap_job(success=True)
            
        except Exception as e:
            logger.error("bootstrap_failed", workspace_id=workspace_id, error=str(e))
            
            # Mark job as failed
            async with get_db_session() as session:
                result = await session.execute(
                    select(BootstrapJob).where(BootstrapJob.id == job_id)
                )
                job = result.scalar_one()
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                job.errors = [str(e)]
                await session.commit()
            metrics_registry.record_bootstrap_job(success=False)
    
    async def _fetch_endpoint_data(
        self,
        workspace_id: str,
        endpoint: OpenAPIEndpoint
    ) -> List[Dict[str, Any]]:
        """Fetch data from a single endpoint with pagination."""
        
        all_data = []
        page = 1
        max_pages = max(1, settings.bootstrap_max_pages)
        
        while page <= max_pages:
            # Build API call request
            request = APICallRequest(
                method="GET",
                endpoint=endpoint.path,
                params={"workspaceId": workspace_id},
                query={"page": page, "page-size": 50} if page > 1 else {},
                developer_mode=False
            )
            
            # Execute API call
            response = await execute_api_call(workspace_id, request)
            
            if not response.success:
                raise Exception(f"API call failed: {response.error_message}")
            
            # Extract data
            data = response.response_body
            
            if not data:
                break
            
            # Handle different response formats
            if isinstance(data, list):
                if not data:
                    break
                all_data.extend(data)
                
                # Check if there are more pages
                if len(data) < 50:
                    break
            elif isinstance(data, dict):
                # Single object response
                all_data.append(data)
                break
            else:
                break
            
            page += 1
        
        if page > max_pages:
            logger.warning(
                "bootstrap_page_limit_hit",
                workspace_id=workspace_id,
                endpoint=endpoint.path,
                max_pages=max_pages
            )
        
        # Store data in database
        await self._store_workspace_data(
            workspace_id,
            endpoint,
            all_data
        )
        
        logger.debug(
            "endpoint_data_fetched",
            workspace_id=workspace_id,
            endpoint=endpoint.path,
            count=len(all_data)
        )
        
        return all_data
    
    async def _store_workspace_data(
        self,
        workspace_id: str,
        endpoint: OpenAPIEndpoint,
        data: List[Dict[str, Any]]
    ) -> None:
        """Store fetched data in database."""
        
        if not data:
            return
        
        # Determine entity type from endpoint
        entity_type = self._extract_entity_type(endpoint.path)
        
        async with get_db_session() as session:
            for item in data:
                # Extract entity ID if available
                entity_id = None
                if isinstance(item, dict):
                    entity_id = item.get("id") or item.get("_id")
                
                workspace_data = WorkspaceData(
                    workspace_id=workspace_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    data=item,
                    source_endpoint=endpoint.path
                )
                session.add(workspace_data)
            
            await session.commit()
    
    def _extract_entity_type(self, path: str) -> str:
        """Extract entity type from endpoint path."""
        
        # Remove workspace ID and parameters
        parts = path.split("/")
        
        # Find the main resource name
        for part in reversed(parts):
            if part and "{" not in part:
                return part.lower()
        
        return "unknown"
    
    async def get_bootstrap_status(self, workspace_id: str) -> Dict[str, Any]:
        """Get status of latest bootstrap job for workspace."""
        
        async with get_db_session() as session:
            result = await session.execute(
                select(BootstrapJob)
                .where(BootstrapJob.workspace_id == workspace_id)
                .order_by(BootstrapJob.created_at.desc())
                .limit(1)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return {"status": "NOT_STARTED"}
            
            return {
                "id": job.id,
                "status": job.status,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "total_endpoints": job.total_endpoints,
                "completed_endpoints": job.completed_endpoints,
                "failed_endpoints": job.failed_endpoints,
                "errors": job.errors,
                "results": job.results
            }


# Global bootstrap service
bootstrap_service = BootstrapService()


async def start_workspace_bootstrap(workspace_id: str) -> int:
    """Start bootstrap for a workspace."""
    return await bootstrap_service.start_bootstrap(workspace_id)


async def get_bootstrap_status(workspace_id: str) -> Dict[str, Any]:
    """Get bootstrap status for a workspace."""
    return await bootstrap_service.get_bootstrap_status(workspace_id)
