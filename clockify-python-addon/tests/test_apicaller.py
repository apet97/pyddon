import pytest
from app.api_caller import ClockifyAPIExecutor
from app.config import Settings
from app.openapi_loader import OpenAPIParser
from app.schemas.api_call import OpenAPIEndpoint, APICallRequest
from app.utils.errors import ValidationError
from app.metrics import metrics_registry


def test_openapi_parser_initialization():
    """Test OpenAPI parser initialization."""
    parser = OpenAPIParser()
    assert parser is not None


def test_openapi_spec_loading():
    """Test loading OpenAPI spec."""
    parser = OpenAPIParser()
    spec = parser.load_spec()
    
    assert spec is not None
    assert "openapi" in spec or "paths" in spec


def test_endpoint_extraction():
    """Test extracting endpoints from spec."""
    parser = OpenAPIParser()
    parser.load_spec()
    
    endpoints = parser.get_all_endpoints()
    assert isinstance(endpoints, list)


def test_get_endpoints_filtering():
    """Test filtering GET endpoints."""
    parser = OpenAPIParser()
    parser.load_spec()
    
    get_endpoints = parser.get_get_endpoints()
    
    for endpoint in get_endpoints:
        assert endpoint.method == "GET"


def test_safe_endpoint_detection():
    """Test that safe endpoints are correctly identified."""
    parser = OpenAPIParser()
    
    # Safe endpoint - only workspaceId parameter
    safe_ep = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/projects",
        method="GET",
        parameters=[{"name": "workspaceId", "in": "path", "required": True}]
    )
    
    assert parser._is_safe_for_bootstrap(safe_ep) is True
    
    # Unsafe endpoint - requires additional unknown ID
    unsafe_ep = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/projects/{projectId}",
        method="GET",
        parameters=[
            {"name": "workspaceId", "in": "path", "required": True},
            {"name": "projectId", "in": "path", "required": True}
        ]
    )
    
    assert parser._is_safe_for_bootstrap(unsafe_ep) is False


def test_endpoint_validation():
    """Test endpoint request validation."""
    parser = OpenAPIParser()
    
    endpoint = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/projects",
        method="GET",
        parameters=[
            {"name": "workspaceId", "in": "path", "required": True}
        ]
    )
    
    # Valid request
    is_valid, error = parser.validate_request(
        endpoint,
        params={"workspaceId": "test-123"},
        query={},
        body=None
    )
    assert is_valid is True
    assert error is None
    
    # Invalid request - missing required parameter
    is_valid, error = parser.validate_request(
        endpoint,
        params={},
        query={},
        body=None
    )
    assert is_valid is False
    assert error is not None


def test_find_endpoint():
    """Test finding specific endpoint."""
    parser = OpenAPIParser()
    parser.load_spec()
    
    # Try to find a common endpoint
    endpoints = parser.get_all_endpoints()
    
    if endpoints:
        first_endpoint = endpoints[0]
        found = parser.find_endpoint(first_endpoint.method, first_endpoint.path)
        
        if found:
            assert found.path == first_endpoint.path
            assert found.method == first_endpoint.method


def test_entity_type_extraction():
    """Test extracting entity type from path."""
    from app.bootstrap import BootstrapService
    
    service = BootstrapService()
    
    test_cases = [
        ("/v1/workspaces/{workspaceId}/projects", "projects"),
        ("/v1/workspaces/{workspaceId}/users", "users"),
        ("/v1/workspaces/{workspaceId}/time-entries", "time-entries"),
    ]
    
    for path, expected_type in test_cases:
        entity_type = service._extract_entity_type(path)
        assert entity_type == expected_type


def test_domain_whitelist_allows_clockify_hosts():
    executor = ClockifyAPIExecutor()
    executor._validate_target_host("https://api.clockify.me/api/v1/workspaces")
    executor._validate_target_host("https://reports.api.clockify.me/v1/reports")


def test_domain_whitelist_blocks_external_hosts():
    executor = ClockifyAPIExecutor()
    with pytest.raises(ValidationError):
        executor._validate_target_host("https://malicious.example.com/api")


def test_domain_whitelist_rejects_nested_subdomains_for_exact_hosts(monkeypatch):
    executor = ClockifyAPIExecutor()
    custom_settings = Settings(
        base_url="https://example.com",
        addon_key="addon",
        database_url="sqlite+aiosqlite:///./addon.db",
        allowed_api_domains=["api.clockify.me"],
    )
    monkeypatch.setattr("app.api_caller.settings", custom_settings)
    with pytest.raises(ValidationError):
        executor._validate_target_host("https://nested.api.clockify.me/v1/resource")


def test_domain_whitelist_accepts_nested_subdomains_with_wildcard(monkeypatch):
    executor = ClockifyAPIExecutor()
    custom_settings = Settings(
        base_url="https://example.com",
        addon_key="addon",
        database_url="sqlite+aiosqlite:///./addon.db",
        allowed_api_domains=["*.clockify.me"],
    )
    monkeypatch.setattr("app.api_caller.settings", custom_settings)
    # Should not raise
    executor._validate_target_host("https://nested.api.clockify.me/v1/resource")


class _DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = '{"payload": true}' if payload is None else str(payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_execute_call_records_http_errors(monkeypatch):
    executor = ClockifyAPIExecutor()
    endpoint = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/projects",
        method="GET",
        parameters=[{"name": "workspaceId", "in": "path", "required": True}],
    )

    executor.openapi.find_endpoint = lambda method, path: endpoint  # type: ignore[assignment]
    executor.openapi.validate_request = lambda *args, **kwargs: (True, None)  # type: ignore[assignment]

    async def fake_token(_workspace_id):
        return "addon-token"

    async def fake_rate_limit(_workspace_id):
        return None

    failure_body = {"message": "Forbidden"}

    async def fake_request(**_kwargs):
        resp = _DummyResponse(status_code=403, payload=failure_body)
        resp.text = '{"message": "Forbidden"}'
        return resp

    logged = []

    async def fake_log(*_args, **kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(executor, "_get_addon_token", fake_token)
    monkeypatch.setattr("app.api_caller.rate_limit_request", fake_rate_limit)
    monkeypatch.setattr(executor, "_make_request", fake_request)
    monkeypatch.setattr(executor, "_log_api_call", fake_log)

    metrics_registry.reset()

    request = APICallRequest(
        method="GET",
        endpoint="/v1/workspaces/{workspaceId}/projects",
        params={"workspaceId": "ws-1"},
        query={},
        body=None,
    )

    response = await executor.execute_call("ws-1", request)
    assert response.success is False
    assert response.status_code == 403
    assert "Forbidden" in response.error_message
    assert response.response_body == failure_body
    assert metrics_registry.api_calls_failed == 1
    assert logged and logged[0]["error_message"] is not None


@pytest.mark.asyncio
async def test_execute_call_success_path(monkeypatch):
    executor = ClockifyAPIExecutor()
    endpoint = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/clients",
        method="GET",
        parameters=[{"name": "workspaceId", "in": "path", "required": True}],
    )

    executor.openapi.find_endpoint = lambda method, path: endpoint  # type: ignore[assignment]
    executor.openapi.validate_request = lambda *args, **kwargs: (True, None)  # type: ignore[assignment]

    async def fake_token(_workspace_id):
        return "addon-token"

    async def fake_rate_limit(_workspace_id):
        return None

    payload = {"data": []}

    async def fake_request(**_kwargs):
        resp = _DummyResponse(status_code=200, payload=payload)
        resp.text = '{"data": []}'
        return resp

    monkeypatch.setattr(executor, "_get_addon_token", fake_token)
    monkeypatch.setattr("app.api_caller.rate_limit_request", fake_rate_limit)
    monkeypatch.setattr(executor, "_make_request", fake_request)
    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(executor, "_log_api_call", noop)

    metrics_registry.reset()

    request = APICallRequest(
        method="GET",
        endpoint="/v1/workspaces/{workspaceId}/clients",
        params={"workspaceId": "ws-1"},
        query={},
        body=None,
    )

    response = await executor.execute_call("ws-1", request)
    assert response.success is True
    assert response.error_message is None
    assert response.response_body == payload
    assert metrics_registry.api_calls_failed == 0
    assert metrics_registry.api_calls_total == 1
