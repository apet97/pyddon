"""OpenAPI spec loader and endpoint discovery for Clockify API."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


@lru_cache(maxsize=1)
def load_openapi() -> Dict[str, Any]:
    """Load the Clockify OpenAPI spec from docs/openapi.json.
    
    Returns:
        Parsed OpenAPI specification dictionary
    """
    path = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_safe_get_operations() -> List[Dict[str, Any]]:
    """Return GET operations considered safe for automatic bootstrap.
    
    Safe operations are:
    - GET methods only
    - Contains {workspaceId} in path OR is a core endpoint (/v1/user, /v1/workspaces)
    - No other required path params (like {id}, {userId}, etc.)
    - Not heavy report endpoints (unless explicitly enabled)
    
    Returns:
        List of safe operation metadata dictionaries
    """
    spec = load_openapi()
    safe_ops: List[Dict[str, Any]] = []
    paths = spec.get("paths", {})

    core_endpoints = [
        "/v1/user",
        "/v1/workspaces",
    ]

    for path, methods in paths.items():
        get_op = methods.get("get")
        if not get_op:
            continue

        is_core = path in core_endpoints
        has_workspace_id = "{workspaceId}" in path

        if not is_core and not has_workspace_id:
            continue

        path_params = [
            p for p in (get_op.get("parameters") or []) if p.get("in") == "path"
        ]

        if has_workspace_id:
            other_required_params = [
                p
                for p in path_params
                if p.get("name") != "workspaceId" and p.get("required", False)
            ]
            if other_required_params:
                continue

        summary = (get_op.get("summary") or "").lower()
        if "detailed" in path.lower() or "report" in path.lower():
            if "detailed" in summary or "heavy" in summary:
                continue

        operation_id = get_op.get("operationId", path)
        tags = get_op.get("tags", ["Uncategorized"])

        safe_ops.append(
            {
                "path": path,
                "operation_id": operation_id,
                "method": "GET",
                "operation": get_op,
                "tags": tags,
                "summary": get_op.get("summary", ""),
                "is_core": is_core,
            }
        )

    return safe_ops


def get_operation_by_id(operation_id: str) -> Dict[str, Any] | None:
    """Get a specific operation by its operationId.
    
    Args:
        operation_id: The operationId from OpenAPI spec
        
    Returns:
        Operation metadata dictionary or None if not found
    """
    spec = load_openapi()
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return {"path": path, "method": method.upper(), "operation": operation}

    return None


def list_all_operations() -> List[Dict[str, Any]]:
    """List all operations from the OpenAPI spec.
    
    Used by API Explorer to show all available endpoints.
    
    Returns:
        List of all operation metadata dictionaries
    """
    spec = load_openapi()
    all_ops: List[Dict[str, Any]] = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue

            all_ops.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "operation_id": operation.get("operationId", f"{method}_{path}"),
                    "summary": operation.get("summary", ""),
                    "tags": operation.get("tags", ["Uncategorized"]),
                    "operation": operation,
                }
            )

    return all_ops


_HEAVY_KEYWORDS = ("report", "detailed", "export")
_HEAVY_TAGS = {
    "reports",
    "reporting",
    "detailed reports",
    "exports",
}
_TIME_ENTRY_KEYWORDS = ("time-entries", "timeentries", "time_entries")
_TIME_ENTRY_TAGS = {
    "time entry",
    "time entries",
    "time-entry",
}


def is_heavy_operation(operation: Dict[str, Any]) -> bool:
    """Return True if the operation is considered \"heavy\" (reports/exports)."""
    path_lower = (operation.get("path") or "").lower()
    op_meta = operation.get("operation") or {}
    summary_lower = (op_meta.get("summary") or "").lower()
    description_lower = (op_meta.get("description") or "").lower()
    tags_lower = [tag.lower() for tag in operation.get("tags", [])]

    if any(keyword in path_lower for keyword in _HEAVY_KEYWORDS):
        return True
    combined = f"{summary_lower} {description_lower}"
    if any(keyword in combined for keyword in _HEAVY_KEYWORDS):
        return True
    if any(tag in _HEAVY_TAGS for tag in tags_lower):
        return True
    return False


def is_time_entry_operation(operation: Dict[str, Any]) -> bool:
    """Return True if the operation fetches time-entry style data."""
    path_lower = (operation.get("path") or "").lower()
    op_meta = operation.get("operation") or {}
    summary_lower = (op_meta.get("summary") or "").lower()
    tags_lower = [tag.lower() for tag in operation.get("tags", [])]

    if any(keyword in path_lower for keyword in _TIME_ENTRY_KEYWORDS):
        return True
    if any(tag in _TIME_ENTRY_TAGS for tag in tags_lower):
        return True
    if "time entry" in summary_lower or "time-entry" in summary_lower:
        return True
    return False
