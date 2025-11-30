from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from jsonpath_ng import parse as jsonpath_parse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clockify_client import ClockifyClient
from .models import Flow, FlowExecution, WebhookLog
from .openapi_loader import get_operation_by_id
from clockify_core import increment_counter

logger = logging.getLogger(__name__)


async def evaluate_and_run_flows_for_webhook(
    session: AsyncSession,
    workspace_id: str,
    webhook: WebhookLog,
    client: ClockifyClient,
) -> None:
    """Evaluate all flows for this webhook and run matching actions.

    High-level algorithm:
    - Load enabled flows for workspace_id where trigger_event_types contains webhook.event_type
    - For each flow, evaluate conditions against webhook.payload
    - For matching flows, execute actions sequentially via ClockifyClient
    - Persist FlowExecution rows with status and truncated results
    """
    # Query for enabled flows matching this event type
    stmt = (
        select(Flow)
        .where(Flow.workspace_id == workspace_id)
        .where(Flow.enabled == True)
    )
    result = await session.execute(stmt)
    flows = result.scalars().all()

    # Filter flows that match this event type
    matching_flows = [
        flow for flow in flows
        if webhook.event_type in (flow.trigger_event_types or [])
    ]

    for flow in matching_flows:
        # Evaluate conditions
        if not _evaluate_conditions(flow.conditions, webhook.payload):
            continue

        # Execute flow
        await _execute_flow(session, flow, webhook, client)


def _evaluate_conditions(conditions: Dict[str, Any] | None, payload: Dict[str, Any]) -> bool:
    """Evaluate flow conditions against webhook payload.

    Conditions format:
    {
        "type": "ALL" | "ANY",
        "rules": [
            {"field": "$.projectId", "operator": "==", "value": "123"},
            {"field": "$.userId", "operator": "!=", "value": "456"}
        ]
    }
    """
    if not conditions or not conditions.get("rules"):
        return True  # No conditions means always match

    rules = conditions.get("rules", [])
    match_type = conditions.get("type", "ALL")

    results = []
    for rule in rules:
        field_path = rule.get("field", "")
        operator = rule.get("operator", "==")
        expected_value = rule.get("value")

        # Extract value from payload using JSONPath
        try:
            jsonpath_expr = jsonpath_parse(field_path)
            matches = jsonpath_expr.find(payload)
            actual_value = matches[0].value if matches else None
        except Exception:
            actual_value = None

        # Evaluate operator
        if operator == "==":
            result = actual_value == expected_value
        elif operator == "!=":
            result = actual_value != expected_value
        elif operator == "contains":
            result = expected_value in (actual_value or "")
        elif operator == "exists":
            result = actual_value is not None
        else:
            result = False

        results.append(result)

    # Combine results based on match type
    if match_type == "ALL":
        return all(results) if results else True
    else:  # ANY
        return any(results) if results else False


async def _execute_flow(
    session: AsyncSession,
    flow: Flow,
    webhook: WebhookLog,
    client: ClockifyClient
) -> None:
    """Execute all actions in a flow sequentially."""
    increment_counter("flows.executed.total")
    logger.info(f"Executing flow {flow.id} ({flow.name}) for webhook {webhook.id}")
    
    execution = FlowExecution(
        workspace_id=flow.workspace_id,
        flow_id=flow.id,
        webhook_log_id=webhook.id,
        status="IN_PROGRESS",
        created_at=datetime.now(timezone.utc)
    )
    session.add(execution)
    await session.commit()

    actions = flow.actions or []
    action_results = []
    context = {"webhook": webhook.payload}

    try:
        for idx, action in enumerate(actions):
            try:
                result = await _execute_action(action, context, client)
                action_results.append({
                    "action_index": idx,
                    "status": "SUCCESS",
                    "result": result
                })
                # Add action result to context for subsequent actions
                context[f"action_{idx}_result"] = result
                increment_counter("flows.actions.executed")
            except Exception as e:
                action_results.append({
                    "action_index": idx,
                    "status": "ERROR",
                    "error": str(e)
                })
                logger.error(f"Flow action {idx} failed for flow {flow.id}: {e}")
                increment_counter("flows.actions.errors")
                # Stop on first error
                execution.status = "FAILED"
                execution.detail = f"Action {idx} failed: {str(e)}"
                increment_counter("flows.executed.failed")
                break
        else:
            # All actions succeeded
            execution.status = "COMPLETED"
            increment_counter("flows.executed.completed")
            logger.info(f"Flow {flow.id} completed successfully")

        execution.actions_result = action_results
        await session.commit()

    except Exception as e:
        execution.status = "FAILED"
        execution.detail = str(e)
        increment_counter("flows.executed.failed")
        logger.error(f"Flow {flow.id} execution failed: {e}")
        await session.commit()


async def _execute_action(
    action: Dict[str, Any],
    context: Dict[str, Any],
    client: ClockifyClient
) -> Dict[str, Any]:
    """Execute a single action from a flow.

    Action format:
    {
        "operation_id": "updateTimeEntry",
        "path_params": {"workspaceId": "$.workspace.id", "id": "$.timeEntry.id"},
        "query_params": {},
        "body": {"description": "Updated via flow", "projectId": "$.webhook.projectId"}
    }
    """
    operation_id = action.get("operation_id")
    if not operation_id:
        raise ValueError("Action missing operation_id")

    # Get operation details from OpenAPI spec
    op_info = get_operation_by_id(operation_id)
    if not op_info:
        raise ValueError(f"Operation {operation_id} not found in OpenAPI spec")

    path = op_info["path"]
    method = op_info["method"]

    # Resolve path parameters
    path_params = action.get("path_params", {})
    for param_name, param_value_expr in path_params.items():
        resolved_value = _resolve_value(param_value_expr, context)
        path = path.replace(f"{{{param_name}}}", str(resolved_value))

    # Resolve query parameters
    query_params = {}
    for param_name, param_value_expr in action.get("query_params", {}).items():
        query_params[param_name] = _resolve_value(param_value_expr, context)

    # Resolve body
    body = None
    if action.get("body"):
        body = _resolve_object(action["body"], context)

    # Execute the API call
    request_kwargs = {"params": query_params} if query_params else {}
    if body:
        request_kwargs["json"] = body

    if method == "GET":
        response = await client.get(path, **request_kwargs)
    elif method == "POST":
        response = await client.post(path, **request_kwargs)
    elif method == "PUT":
        response = await client.put(path, **request_kwargs)
    elif method == "PATCH":
        response = await client.patch(path, **request_kwargs)
    elif method == "DELETE":
        response = await client.delete(path, **request_kwargs)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    response.raise_for_status()

    # Return response data (truncated for storage)
    result_data = response.json() if response.content else {}
    result_str = json.dumps(result_data)
    if len(result_str) > 5000:
        result_str = result_str[:5000] + "... (truncated)"

    return {
        "status_code": response.status_code,
        "data": result_str
    }


def _resolve_value(value_expr: Any, context: Dict[str, Any]) -> Any:
    """Resolve a value expression using context.

    - If value_expr starts with '$.' it's treated as a JSONPath expression
    - Otherwise, it's returned as-is (constant value)
    """
    if not isinstance(value_expr, str):
        return value_expr

    if value_expr.startswith("$."):
        try:
            jsonpath_expr = jsonpath_parse(value_expr)
            matches = jsonpath_expr.find(context)
            return matches[0].value if matches else None
        except Exception:
            return None

    return value_expr


def _resolve_object(obj: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve all values in an object."""
    if isinstance(obj, dict):
        return {k: _resolve_object(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_object(item, context) for item in obj]
    else:
        return _resolve_value(obj, context)
