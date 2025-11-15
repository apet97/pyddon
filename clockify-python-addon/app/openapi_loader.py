import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from app.utils.logger import get_logger
from app.schemas.api_call import OpenAPIEndpoint

logger = get_logger(__name__)


class OpenAPIParser:
    """Parse and query OpenAPI specification."""
    
    def __init__(self, spec_path: str = "openapi.json"):
        self.spec_path = Path(spec_path)
        self.spec: Optional[Dict[str, Any]] = None
        self._endpoints_cache: Optional[List[OpenAPIEndpoint]] = None
    
    def load_spec(self) -> Dict[str, Any]:
        """Load OpenAPI specification from file."""
        try:
            if self.spec_path.exists():
                with open(self.spec_path, 'r') as f:
                    self.spec = json.load(f)
                    logger.info("openapi_spec_loaded", path=str(self.spec_path))
            else:
                logger.warning("openapi_spec_not_found", path=str(self.spec_path))
                self.spec = self._get_minimal_spec()
            return self.spec
        except Exception as e:
            logger.error("openapi_spec_load_failed", error=str(e))
            self.spec = self._get_minimal_spec()
            return self.spec
    
    def _get_minimal_spec(self) -> Dict[str, Any]:
        """Return minimal OpenAPI spec as fallback."""
        return {
            "openapi": "3.0.1",
            "info": {"title": "Clockify API", "version": "v1"},
            "paths": {}
        }
    
    def get_all_endpoints(self) -> List[OpenAPIEndpoint]:
        """Get all endpoints from OpenAPI spec."""
        if self._endpoints_cache:
            return self._endpoints_cache
        
        if not self.spec:
            self.load_spec()
        
        endpoints = []
        paths = self.spec.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    endpoint = OpenAPIEndpoint(
                        path=path,
                        method=method.upper(),
                        operation_id=operation.get("operationId"),
                        summary=operation.get("summary"),
                        description=operation.get("description"),
                        parameters=operation.get("parameters", []),
                        request_body=operation.get("requestBody"),
                        responses=operation.get("responses", {}),
                        tags=operation.get("tags", [])
                    )
                    endpoints.append(endpoint)
        
        self._endpoints_cache = endpoints
        logger.info("endpoints_parsed", count=len(endpoints))
        return endpoints
    
    def get_get_endpoints(self) -> List[OpenAPIEndpoint]:
        """Get all GET endpoints suitable for bootstrap."""
        all_endpoints = self.get_all_endpoints()
        get_endpoints = [ep for ep in all_endpoints if ep.method == "GET"]
        
        # Filter out endpoints that require unknown IDs
        safe_endpoints = []
        for ep in get_endpoints:
            # Check if path contains parameters that can't be inferred
            if self._is_safe_for_bootstrap(ep):
                safe_endpoints.append(ep)
        
        logger.info("safe_get_endpoints_found", count=len(safe_endpoints))
        return safe_endpoints
    
    def _is_safe_for_bootstrap(self, endpoint: OpenAPIEndpoint) -> bool:
        """Check if endpoint is safe to call during bootstrap."""
        path = endpoint.path
        
        # Allow endpoints with workspaceId only
        if "{workspaceId}" in path:
            # Count path parameters
            param_count = path.count("{")
            
            # Only workspaceId parameter
            if param_count == 1:
                return True
            
            # Multiple parameters - only allow specific safe list endpoints
            # These must end with the resource name (no additional ID parameters)
            safe_patterns = [
                "/workspaces/{workspaceId}/users",
                "/workspaces/{workspaceId}/projects",
                "/workspaces/{workspaceId}/clients",
                "/workspaces/{workspaceId}/tags",
                "/workspaces/{workspaceId}/custom-fields",
                "/workspaces/{workspaceId}/user-groups",
                "/workspaces/{workspaceId}/time-entries",
            ]
            
            # Check if path ends with a safe pattern (to avoid matching detail endpoints)
            for pattern in safe_patterns:
                if path.endswith(pattern) or path.endswith(pattern + "/"):
                    return True
        
        return False
    
    def find_endpoint(self, method: str, path: str) -> Optional[OpenAPIEndpoint]:
        """Find specific endpoint by method and path."""
        endpoints = self.get_all_endpoints()
        
        for ep in endpoints:
            if ep.method == method.upper() and ep.path == path:
                return ep
        
        return None
    
    def validate_request(
        self,
        endpoint: OpenAPIEndpoint,
        params: Dict[str, Any],
        query: Dict[str, Any],
        body: Optional[Dict[str, Any]]
    ) -> tuple[bool, Optional[str]]:
        """Validate request against OpenAPI spec."""
        
        # Basic validation - in production, use a proper OpenAPI validator
        required_params = [
            p["name"] for p in endpoint.parameters
            if p.get("in") == "path" and p.get("required", False)
        ]
        
        for param in required_params:
            if param not in params:
                return False, f"Missing required path parameter: {param}"
        
        # Validate request body if required
        if endpoint.request_body:
            required = endpoint.request_body.get("required", False)
            if required and not body:
                return False, "Request body is required"
        
        return True, None


# Global OpenAPI parser instance
openapi_parser = OpenAPIParser()


def get_openapi_parser() -> OpenAPIParser:
    """Get OpenAPI parser instance."""
    return openapi_parser
