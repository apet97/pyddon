import httpx
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from app.config import get_settings
from app.db.models import Installation, APICall
from app.db.session import get_db_session
from app.openapi_loader import get_openapi_parser
from app.schemas.api_call import APICallRequest, APICallResponse
from app.utils.logger import get_logger
from app.utils.errors import ValidationError, ExternalAPIError, NotFoundError
from app.utils.rate_limit import rate_limit_request
from app.metrics import metrics_registry

settings = get_settings()
logger = get_logger(__name__)


class ClockifyAPIExecutor:
    """Execute Clockify API calls with validation and error handling."""
    
    _MAX_CAPTURE_BYTES = 4096
    
    def __init__(self):
        self.openapi = get_openapi_parser()
        self.openapi.load_spec()
    
    async def execute_call(
        self,
        workspace_id: str,
        request: APICallRequest
    ) -> APICallResponse:
        """Execute an API call with full validation and logging."""
        
        start_time = time.time()
        
        try:
            # Get installation and addon token
            addon_token = await self._get_addon_token(workspace_id)
            
            # Validate endpoint exists in OpenAPI spec
            endpoint = self.openapi.find_endpoint(request.method, request.endpoint)
            if not endpoint:
                raise ValidationError(
                    f"Endpoint not found: {request.method} {request.endpoint}",
                    details={"method": request.method, "endpoint": request.endpoint}
                )
            
            # Validate request parameters
            is_valid, error_msg = self.openapi.validate_request(
                endpoint,
                request.params,
                request.query,
                request.body
            )
            
            if not is_valid:
                raise ValidationError(error_msg)
            
            # Build URL
            url = self._build_url(request.endpoint, request.params, request.developer_mode)
            self._validate_target_host(url)
            
            # Apply rate limiting
            await rate_limit_request(workspace_id)
            
            response = await self._make_request(
                method=request.method,
                url=url,
                query=request.query,
                body=request.body,
                addon_token=addon_token,
            )
            duration_ms = int((time.time() - start_time) * 1000)

            parsed_body = self._capture_response_body(response)
            is_success = response.status_code < 400
            error_message = None

            if not is_success:
                detail_hint = None
                if isinstance(parsed_body, dict):
                    detail_hint = parsed_body.get("message") or parsed_body.get("error")
                suffix = f": {detail_hint}" if detail_hint else ""
                error_message = f"Clockify API returned status {response.status_code}{suffix}"
                logger.error(
                    "clockify_api_error",
                    workspace_id=workspace_id,
                    endpoint=request.endpoint,
                    status_code=response.status_code,
                    message=detail_hint,
                )

            await self._log_api_call(
                workspace_id=workspace_id,
                request=request,
                response_status=response.status_code,
                response_body=parsed_body if is_success else None,
                error_message=error_message,
                duration_ms=duration_ms,
            )

            metrics_registry.record_api_call(success=is_success)

            return APICallResponse(
                success=is_success,
                status_code=response.status_code,
                response_body=parsed_body,
                error_message=error_message,
                duration_ms=duration_ms,
                metadata={
                    "endpoint": request.endpoint,
                    "method": request.method,
                    "developer_mode": request.developer_mode,
                },
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)
            
            # Log failed API call
            await self._log_api_call(
                workspace_id=workspace_id,
                request=request,
                response_status=None,
                response_body=None,
                error_message=error_message,
                duration_ms=duration_ms
            )
            
            logger.error(
                "api_call_failed",
                workspace_id=workspace_id,
                endpoint=request.endpoint,
                error=error_message
            )
            
            metrics_registry.record_api_call(success=False)
            
            return APICallResponse(
                success=False,
                error_message=error_message,
                duration_ms=duration_ms,
                metadata={
                    "endpoint": request.endpoint,
                    "method": request.method,
                    "developer_mode": request.developer_mode
                }
            )
    
    async def _get_addon_token(self, workspace_id: str) -> str:
        """Get addon token for workspace."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Installation).where(
                    Installation.workspace_id == workspace_id,
                    Installation.status == "ACTIVE"
                )
            )
            installation = result.scalar_one_or_none()
            
            if not installation:
                raise NotFoundError(f"No active installation found for workspace {workspace_id}")
            
            return installation.addon_token
    
    def _build_url(
        self,
        endpoint: str,
        params: Dict[str, Any],
        developer_mode: bool
    ) -> str:
        """Build full URL with path parameters substituted."""
        
        # Choose base URL
        base_url = (
            settings.clockify_developer_api_base
            if developer_mode
            else settings.clockify_api_base
        )
        
        # Handle different API bases (pto, reports)
        if "/pto/" in endpoint:
            base_url = settings.clockify_pto_api_base
            endpoint = endpoint.replace("/pto/v1", "")
        elif "/reports/" in endpoint:
            base_url = settings.clockify_reports_api_base
            endpoint = endpoint.replace("/reports/v1", "")
        
        # Substitute path parameters
        path = endpoint
        for key, value in params.items():
            path = path.replace(f"{{{key}}}", str(value))
        
        # Combine base URL and path
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        
        logger.debug("url_built", url=url, developer_mode=developer_mode)
        return url
    
    def _validate_target_host(self, url: str) -> None:
        """Ensure outbound requests only target approved Clockify domains."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValidationError("Unable to determine hostname for target URL", details={"url": url})
        allowed = [domain.lower() for domain in settings.allowed_api_domains]
        for domain in allowed:
            if domain.startswith("*."):
                suffix = domain[1:]
                if hostname.endswith(suffix) or hostname == suffix.lstrip("."):
                    return
            elif hostname == domain or hostname.endswith(f".{domain}"):
                return
        raise ValidationError(
            "Domain not allowed for API Studio calls",
            details={"host": hostname, "allowed": settings.allowed_api_domains}
        )
    
    async def _make_request(
        self,
        method: str,
        url: str,
        query: Dict[str, Any],
        body: Optional[Dict[str, Any]],
        addon_token: str
    ) -> httpx.Response:
        """Make HTTP request to Clockify API."""
        
        headers = {
            "X-Addon-Token": addon_token,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=query,
                    json=body,
                    headers=headers
                )
                
                logger.debug(
                    "api_request_completed",
                    method=method,
                    url=url,
                    status=response.status_code
                )
                
                return response
                
            except httpx.TimeoutException:
                raise ExternalAPIError("Request to Clockify API timed out")
            except httpx.RequestError as e:
                raise ExternalAPIError(f"Request failed: {str(e)}")
    
    async def _log_api_call(
        self,
        workspace_id: str,
        request: APICallRequest,
        response_status: Optional[int],
        response_body: Optional[Dict[str, Any]],
        error_message: Optional[str],
        duration_ms: int
    ) -> None:
        """Log API call to database."""
        
        async with get_db_session() as session:
            api_call = APICall(
                workspace_id=workspace_id,
                endpoint=request.endpoint,
                method=request.method,
                request_params=request.params,
                request_body=request.body,
                response_status=response_status,
                response_body=response_body,
                error_message=error_message,
                developer_mode=request.developer_mode,
                duration_ms=duration_ms
            )
            session.add(api_call)
            await session.commit()

    def _capture_response_body(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """Safely capture a JSON (or raw) representation of the response body."""
        if not response.text:
            return None
        try:
            return response.json()
        except ValueError:
            snippet = response.text[: self._MAX_CAPTURE_BYTES]
            return {
                "raw": snippet,
                "truncated": len(response.text) > len(snippet)
            }


# Global API executor
api_executor = ClockifyAPIExecutor()


async def execute_api_call(workspace_id: str, request: APICallRequest) -> APICallResponse:
    """Execute a Clockify API call."""
    return await api_executor.execute_call(workspace_id, request)
