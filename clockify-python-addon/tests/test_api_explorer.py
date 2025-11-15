import pytest
from app.api_explorer import (
    APIExplorerService,
    APIExplorerExecuteRequest,
    api_explorer_service,
    execute_operation,
)
from app.schemas.api_call import OpenAPIEndpoint, APICallResponse


def test_api_explorer_groups_endpoints_by_tag(monkeypatch):
    """Ensure list_endpoints groups entries per tag filter."""
    service = APIExplorerService()

    endpoints = [
        OpenAPIEndpoint(path="/v1/workspaces/{workspaceId}/projects", method="GET", tags=["Projects"]),
        OpenAPIEndpoint(path="/v1/workspaces/{workspaceId}/clients", method="GET", tags=["Clients"]),
        OpenAPIEndpoint(path="/v1/workspaces/{workspaceId}/users", method="GET", tags=["Projects"]),
    ]

    monkeypatch.setattr(service.parser, "get_all_endpoints", lambda: endpoints)

    grouped = service.list_endpoints()
    assert len(grouped) == 2
    projects = next(group for group in grouped if group["tag"] == "Projects")
    assert projects["count"] == 2


@pytest.mark.asyncio
async def test_api_explorer_execute_uses_operation_id(monkeypatch):
    """Executing via operationId should resolve method/path and call executor once."""

    class StubService:
        def __init__(self):
            self.parser = self

        def find_by_operation_id(self, operation_id):
            return OpenAPIEndpoint(
                path="/v1/workspaces/{workspaceId}/projects",
                method="GET",
                operation_id=operation_id,
            )

        def find_endpoint(self, method, path):
            return OpenAPIEndpoint(path=path, method=method)

    stub_response = APICallResponse(success=True, status_code=200, response_body={"ok": True})
    captured = {}

    async def fake_execute(workspace_id, request):
        captured["workspace_id"] = workspace_id
        captured["endpoint"] = request.endpoint
        captured["method"] = request.method
        return stub_response

    monkeypatch.setattr("app.api_explorer.api_explorer_service", StubService())
    monkeypatch.setattr("app.api_explorer.execute_api_call", fake_execute)

    payload = APIExplorerExecuteRequest(
        workspaceId="ws-123",
        operationId="listProjects",
        params={},
        query={},
    )

    result = await execute_operation(payload)
    assert result.success is True
    assert captured["workspace_id"] == "ws-123"
    assert captured["endpoint"] == "/v1/workspaces/{workspaceId}/projects"
    assert captured["method"] == "GET"
