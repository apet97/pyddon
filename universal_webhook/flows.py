"""Flow engine for Universal Webhook add-on."""
from __future__ import annotations

import json
from typing import Any, Dict

from jsonpath_ng import parse as jsonpath_parse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clockify_core import ClockifyClient, get_operation_by_id

from .models import Flow, FlowExecution, WebhookLog


async def evaluate_and_run_flows_for_webhook(
    session: AsyncSession,
    workspace_id: str,
    webhook: WebhookLog,
    client: ClockifyClient,
) -> None:
    """Evaluate all flows for webhook and execute matching actions."""
    # Query enabled flows for this workspace
    stmt = (
        select(Flow)
        .where(Flow.workspace_id == workspace_id)
        .where(Flow.enabled == True)
    )
    result = await session.execute(stmt)
    flows = result.scalars().all()

    # Filter flows matching this webhook
    matching_flows = []
    for flow in flows:
        # Check source match
        if flow.trigger_source != webhook.source:
            continue
        
        # Check event type match
        if webhook.event_type not in (flow.trigger_event_types or []):
            continue
        
        matching_flows.append(flow)

    # Execute each matching flow
    for flow in matching_flows:
        # Evaluate conditions
        if not _evaluate_conditions(flow.conditions, webhook.payload):
            continue

        # Execute flow
        await _execute_flow(session, flow, webhook, client)


def _evaluate_conditions(
    conditions: Dict[str, Any] | None,
    payload: Dict[str, Any]
) -> bool:
    """Evaluate flow conditions against webhook payload."""
    if not conditions or not conditions.get("rules"):
        return True

    rules = conditions.get("rules", [])
    match_type = conditions.get("type", "ALL")

    results = []
    for rule in rules:
        field_path = rule.get("field", "")
        operator = rule.get("operator", "==")
        expected_value = rule.get("value")

        # Extract value using JSONPath
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

    # Combine results
    if match_type == "ALL":
        return all(results)
    else:
        return any(results)


async def _execute_flow(
    session: AsyncSession,
    flow: Flow,
    webhook: WebhookLog,
    client: ClockifyClient
) -> None:
    """Execute a flow's actions."""
    actions_result = []
    context = {"webhook": webhook.payload}

    try:
        for idx, action in enumerate(flow.actions):
            action_type = action.get("type", "CLOCKIFY_API")
            
            if action_type == "CLOCKIFY_API":
                result = await _execute_clockify_action(
                    action, context, client
                )
                actions_result.append(result)
                context[f"action_{idx}"] = result
            elif action_type == "GENERIC_HTTP":
                # TODO: Implement generic HTTP actions
                actions_result.append({"status": "skipped", "reason": "not implemented"})

        # Log successful execution
        execution = FlowExecution(
            workspace_id=flow.workspace_id,
            flow_id=flow.id,
            webhook_log_id=webhook.id,
            status="SUCCESS",
            detail="All actions completed successfully",
            actions_result={"actions": actions_result}
        )
        session.add(execution)
        await session.commit()

    except Exception as e:
        # Log failed execution
        execution = FlowExecution(
            workspace_id=flow.workspace_id,
            flow_id=flow.id,
            webhook_log_id=webhook.id,
            status="FAILED",
            detail=str(e),
            actions_result={"actions": actions_result, "error": str(e)}
        )
        session.add(execution)
        await session.commit()


async def _execute_clockify_action(
    action: Dict[str, Any],
    context: Dict[str, Any],
    client: ClockifyClient
) -> Dict[str, Any]:
    """Execute a Clockify API action."""
    operation_id = action.get("operation_id")
    if not operation_id:
        return {"status": "error", "message": "Missing operation_id"}

    # Get operation details from OpenAPI spec
    operation = get_operation_by_id(operation_id)
    if not operation:
        return {"status": "error", "message": f"Unknown operation: {operation_id}"}

    # Build request
    path = operation["path"]
    method = operation["method"]
    
    # Resolve parameters from context
    params = action.get("params", {})
    resolved_params = _resolve_params(params, context)
    
    # Replace path parameters
    path_params = resolved_params.get("path", {})
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", str(value))
    
    # Execute request
    query_params = resolved_params.get("query", {})
    body = resolved_params.get("body", {})
    
    try:
        if method == "GET":
            resp = await client.get(path, params=query_params)
        elif method == "POST":
            resp = await client.post(path, params=query_params, json=body)
        elif method == "PUT":
            resp = await client.put(path, params=query_params, json=body)
        elif method == "PATCH":
            resp = await client.patch(path, params=query_params, json=body)
        elif method == "DELETE":
            resp = await client.delete(path, params=query_params)
        else:
            return {"status": "error", "message": f"Unsupported method: {method}"}

        return {
            "status": "success",
            "status_code": resp.status_code,
            "data": resp.json() if resp.content else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _resolve_params(
    params: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve parameter values from context using JSONPath."""
    resolved = {}
    
    for param_type, param_values in params.items():
        resolved[param_type] = {}
        for key, value in param_values.items():
            if isinstance(value, str) and value.startswith("$"):
                # JSONPath expression
                try:
                    jsonpath_expr = jsonpath_parse(value)
                    matches = jsonpath_expr.find(context)
                    resolved[param_type][key] = matches[0].value if matches else None
                except Exception:
                    resolved[param_type][key] = None
            else:
                resolved[param_type][key] = value
    
    return resolved
