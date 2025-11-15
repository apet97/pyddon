from datetime import datetime
from fastapi import APIRouter, Request, Header
from typing import Optional, Dict, Any, Sequence
import uuid
from app.db.models import WebhookEvent
from app.db.session import get_db_session
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.token_verification import resolve_signature_header, verify_webhook_signature
from app.utils.dedupe import is_duplicate_event
from app.utils.logger import get_logger
from app.metrics import metrics_registry
from app.constants import CLOCKIFY_WEBHOOK_EVENTS_BY_PATH

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

EVENT_TYPE_HEADER_KEYS = (
    "clockify-webhook-event-type",
    "Clockify-Webhook-Event-Type",
    "clockify_webhook_event_type",
    "Clockify_Webhook_Event_Type",
)


def _resolve_event_type(
    request: Request,
    payload: Dict[str, Any],
    allowed_events: Sequence[str],
    default_event: Optional[str],
) -> str:
    """Infer the concrete Clockify event type for a webhook route."""
    header_event = next(
        (request.headers.get(key) for key in EVENT_TYPE_HEADER_KEYS if request.headers.get(key)),
        None
    )
    payload_event = payload.get("eventType") or payload.get("event_type")
    event_type = header_event or payload_event or default_event or "UNKNOWN_EVENT"

    if allowed_events and event_type not in allowed_events:
        logger.warning(
            "unexpected_webhook_event_type",
            event_type=event_type,
            allowed_events=list(allowed_events),
            path=str(request.url.path)
        )

    return event_type


async def _process_for_path(
    suffix: str,
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = None,
    default_event: Optional[str] = None,
) -> WebhookResponse:
    """Process webhook for a given router suffix using canonical event mapping."""
    full_path = f"{router.prefix}{suffix}"
    allowed_events = CLOCKIFY_WEBHOOK_EVENTS_BY_PATH.get(full_path, [])
    fallback_event = default_event or (allowed_events[0] if allowed_events else None)
    event_type = _resolve_event_type(request, payload, allowed_events, fallback_event)
    return await process_webhook(event_type, payload, request, x_webhook_signature)


async def process_webhook(
    event_type: str,
    payload: Dict[str, Any],
    request: Request,
    x_webhook_signature: Optional[str] = None
) -> WebhookResponse:
    """Common webhook processing logic."""
    
    # Generate event ID
    event_id = str(uuid.uuid4())
    if "id" in payload:
        event_id = str(payload["id"])
    elif "eventId" in payload:
        event_id = str(payload["eventId"])
    
    workspace_id = payload.get("workspaceId", "unknown")
    
    logger.info(
        "webhook_received",
        event_type=event_type,
        event_id=event_id,
        workspace_id=workspace_id
    )
    
    # Verify signature and extract claims
    body = await request.body()
    signature_token = resolve_signature_header(
        request.headers.get("Clockify-Signature"),
        request.headers.get("clockify-signature"),
        request.headers.get("X-Webhook-Signature"),
        request.headers.get("X-Addon-Signature"),
        x_webhook_signature
    )
    claims = await verify_webhook_signature(
        body, 
        signature_token,
        workspace_id=workspace_id
    )
    
    # Enforce workspace consistency
    if claims.get("workspaceId") and claims.get("workspaceId") != workspace_id:
        logger.error(
            "webhook_workspace_mismatch",
            claims_workspace=claims.get("workspaceId"),
            payload_workspace=workspace_id
        )
        return WebhookResponse(received=False, event_id=event_id)
    
    # Store webhook event and check for duplicate atomically
    try:
        async with get_db_session() as session:
            # Check for duplicate using DB
            if await is_duplicate_event(event_id, session):
                logger.warning(
                    "duplicate_webhook_ignored",
                    event_id=event_id,
                    event_type=event_type
                )
                return WebhookResponse(received=True, event_id=event_id)
            
            # Store webhook event
            webhook_event = WebhookEvent(
                event_id=event_id,
                workspace_id=workspace_id,
                event_type=event_type,
                payload=payload,
                event_metadata={
                    "headers": dict(request.headers),
                    "client_host": request.client.host if request.client else None
                },
                received_at=datetime.utcnow(),
                processed=False
            )
            session.add(webhook_event)
            await session.commit()
        
        metrics_registry.record_webhook_event(event_type)
        
        logger.info(
            "webhook_stored",
            event_id=event_id,
            event_type=event_type,
            workspace_id=workspace_id
        )
        
    except Exception as e:
        logger.error(
            "webhook_storage_failed",
            event_id=event_id,
            event_type=event_type,
            error=str(e)
        )
    
    return WebhookResponse(received=True, event_id=event_id)


# Time-related webhooks
@router.post("/time")
async def time_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle time entry related webhooks."""
    return await _process_for_path("/time", request, payload, x_webhook_signature)


@router.post("/time/new")
async def new_time_entry(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle NEW_TIME_ENTRY webhook."""
    return await _process_for_path("/time/new", request, payload, x_webhook_signature)


@router.post("/time/updated")
async def time_entry_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle TIME_ENTRY_UPDATED webhook."""
    return await _process_for_path("/time/updated", request, payload, x_webhook_signature)


@router.post("/time/deleted")
async def time_entry_deleted(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle TIME_ENTRY_DELETED webhook."""
    return await _process_for_path("/time/deleted", request, payload, x_webhook_signature)


# Project-related webhooks
@router.post("/project")
async def project_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle project related webhooks."""
    return await _process_for_path("/project", request, payload, x_webhook_signature, default_event="PROJECT_EVENT")


@router.post("/project/new")
async def new_project(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle NEW_PROJECT webhook."""
    return await _process_for_path("/project/new", request, payload, x_webhook_signature)


@router.post("/project/updated")
async def project_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle PROJECT_UPDATED webhook."""
    return await _process_for_path("/project/updated", request, payload, x_webhook_signature)


@router.post("/project/deleted")
async def project_deleted(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle PROJECT_DELETED webhook."""
    return await _process_for_path("/project/deleted", request, payload, x_webhook_signature)


# User-related webhooks
@router.post("/user")
async def user_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle user related webhooks."""
    return await _process_for_path("/user", request, payload, x_webhook_signature)


@router.post("/user/updated")
async def user_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle USER_UPDATED webhook."""
    return await _process_for_path("/user/updated", request, payload, x_webhook_signature)


@router.post("/workspace")
async def workspace_events(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle workspace invitation/limited user webhooks."""
    return await _process_for_path("/workspace", request, payload, x_webhook_signature)


@router.post("/user-group")
async def user_group_events(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle user group related webhooks."""
    return await _process_for_path("/user-group", request, payload, x_webhook_signature)


# Expense-related webhooks
@router.post("/expense")
async def expense_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle expense related webhooks."""
    return await _process_for_path("/expense", request, payload, x_webhook_signature)


@router.post("/expense/created")
async def expense_created(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle EXPENSE_CREATED webhook."""
    return await _process_for_path("/expense/created", request, payload, x_webhook_signature)


@router.post("/expense/updated")
async def expense_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle EXPENSE_UPDATED webhook."""
    return await _process_for_path("/expense/updated", request, payload, x_webhook_signature)


@router.post("/expense/deleted")
async def expense_deleted(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle EXPENSE_DELETED webhook."""
    return await _process_for_path("/expense/deleted", request, payload, x_webhook_signature)


@router.post("/balance")
async def balance_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle BALANCE_UPDATED webhook."""
    return await _process_for_path("/balance", request, payload, x_webhook_signature)


@router.post("/rate")
async def rate_events(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle BILLABLE_RATE_UPDATED and COST_RATE_UPDATED webhooks."""
    return await _process_for_path("/rate", request, payload, x_webhook_signature)


@router.post("/invoice")
async def invoice_events(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle NEW_INVOICE and INVOICE_UPDATED webhooks."""
    return await _process_for_path("/invoice", request, payload, x_webhook_signature)


# Custom field webhooks
@router.post("/custom")
async def custom_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle custom field related webhooks."""
    return await process_webhook("CUSTOM_FIELD_EVENT", payload, request, x_webhook_signature)


# Assignment webhooks
@router.post("/assignment")
async def assignment_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle assignment related webhooks."""
    return await _process_for_path("/assignment", request, payload, x_webhook_signature)


@router.post("/assignment/created")
async def assignment_created(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle ASSIGNMENT_CREATED webhook."""
    return await _process_for_path("/assignment/created", request, payload, x_webhook_signature)


@router.post("/assignment/updated")
async def assignment_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle ASSIGNMENT_UPDATED webhook."""
    return await _process_for_path("/assignment/updated", request, payload, x_webhook_signature)


@router.post("/assignment/deleted")
async def assignment_deleted(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle ASSIGNMENT_DELETED webhook."""
    return await _process_for_path("/assignment/deleted", request, payload, x_webhook_signature)


# Approval webhooks
@router.post("/approval")
async def approval_webhooks(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle approval related webhooks."""
    return await _process_for_path("/approval", request, payload, x_webhook_signature)


@router.post("/approval/status-updated")
async def approval_status_updated(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle APPROVAL_REQUEST_STATUS_UPDATED webhook."""
    return await _process_for_path("/approval/status-updated", request, payload, x_webhook_signature)


# Generic webhook endpoint for all other events
@router.post("/generic")
async def generic_webhook(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle all other webhook events."""
    return await _process_for_path("/generic", request, payload, x_webhook_signature)


@router.post("/timeoff")
async def time_off_events(
    request: Request,
    payload: Dict[str, Any],
    x_webhook_signature: Optional[str] = Header(None)
):
    """Handle TIME_OFF_REQUEST* webhooks."""
    return await _process_for_path("/timeoff", request, payload, x_webhook_signature)
