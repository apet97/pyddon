"""Security utilities for JWT validation and PII redaction."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

import jwt
from jwt import PyJWTError, PyJWKClient

# Default JWKS endpoints; override via env to target dev/sandbox or custom hosts.
DEFAULT_JWKS_PROD_URL = "https://api.clockify.me/.well-known/jwks.json"
DEFAULT_JWKS_DEV_URL = "https://developer.clockify.me/.well-known/jwks.json"

_jwk_clients: dict[str, PyJWKClient] = {}


class SecurityError(Exception):
    """Exception raised for security validation failures."""
    pass


def _resolve_jwks_url(api_base_url: Optional[str] = None) -> str:
    """Resolve JWKS URL based on env overrides or API host hints."""
    override = os.getenv("CLOCKIFY_JWKS_URL")
    if override:
        return override

    env_hint = (os.getenv("CLOCKIFY_ENVIRONMENT") or "prod").lower()
    if api_base_url:
        host = api_base_url.lower()
        if "developer.clockify.me" in host:
            env_hint = "dev"

    if env_hint in {"dev", "developer", "staging", "sandbox"}:
        return os.getenv("CLOCKIFY_JWKS_DEV_URL", DEFAULT_JWKS_DEV_URL)
    return os.getenv("CLOCKIFY_JWKS_PROD_URL", DEFAULT_JWKS_PROD_URL)


def _get_jwk_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given JWKS URL."""
    client = _jwk_clients.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url, cache_keys=True)
        _jwk_clients[jwks_url] = client
    return client


def verify_jwt_token(
    token: str,
    expected_addon_key: str,
    expected_workspace_id: Optional[str] = None,
    token_type: str = "addon",
    api_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify a Clockify JWT token using JWKS with claim enforcement."""
    try:
        jwks_url = _resolve_jwks_url(api_base_url)
        client = _get_jwk_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token).key

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_exp": True, "verify_aud": False},
            leeway=1,
        )

        if payload.get("iss") != "clockify":
            raise SecurityError("Invalid issuer: expected 'clockify'")
        if payload.get("type") != token_type:
            raise SecurityError(f"Invalid token type: expected '{token_type}'")
        if payload.get("sub") != expected_addon_key:
            raise SecurityError(f"Invalid subject: expected '{expected_addon_key}'")

        if expected_workspace_id:
            token_workspace = payload.get("workspaceId")
            if token_workspace != expected_workspace_id:
                raise SecurityError(f"Workspace ID mismatch: expected '{expected_workspace_id}', got '{token_workspace}'")

        return payload

    except PyJWTError as e:
        raise SecurityError(f"JWT validation failed: {str(e)}") from e


def verify_webhook_signature(
    signature_token: str,
    expected_addon_key: str,
    expected_workspace_id: str,
    webhook_id: Optional[str] = None
) -> Dict[str, Any]:
    """Verify a Clockify webhook signature (JWT).
    
    Args:
        signature_token: JWT signature from Clockify-Signature header
        expected_addon_key: Expected add-on key
        expected_workspace_id: Expected workspace ID from webhook payload
        webhook_id: Optional webhook ID for additional verification
        
    Returns:
        Decoded signature claims if valid
        
    Raises:
        SecurityError: If signature validation fails
    """
    # Verify basic JWT structure
    payload = verify_jwt_token(
        signature_token,
        expected_addon_key,
        expected_workspace_id,
        token_type="addon"
    )
    
    # Additional webhook-specific validations can be added here
    # For example, verifying webhook ID if provided in claims
    if webhook_id and "webhookId" in payload:
        if payload["webhookId"] != webhook_id:
            raise SecurityError("Webhook ID mismatch")
    
    return payload


def verify_lifecycle_signature(
    signature_token: str,
    expected_addon_key: str,
    expected_workspace_id: Optional[str] = None
) -> Dict[str, Any]:
    """Verify a Clockify lifecycle event signature (JWT).
    
    Args:
        signature_token: JWT signature from Clockify-Signature header
        expected_addon_key: Expected add-on key
        expected_workspace_id: Optional expected workspace ID
        
    Returns:
        Decoded signature claims if valid
        
    Raises:
        SecurityError: If signature validation fails
    """
    return verify_jwt_token(
        signature_token,
        expected_addon_key,
        expected_workspace_id,
        token_type="addon"
    )


def redact_sensitive_data(data: Any, redact_fields: Optional[set] = None) -> Any:
    """Recursively redact sensitive fields from data structures.
    
    Args:
        data: Data structure to redact (dict, list, or primitive)
        redact_fields: Set of field names to redact (case-insensitive)
        
    Returns:
        Redacted copy of data
    """
    if redact_fields is None:
        redact_fields = {
            "token", "authtoken", "auth_token", "addon_token", "addontoken",
            "password", "secret", "api_key", "apikey", "authorization",
            "x-addon-token", "clockify-signature", "signature"
        }
    
    # Convert to lowercase for case-insensitive matching
    redact_fields_lower = {f.lower() for f in redact_fields}
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key.lower() in redact_fields_lower:
                result[key] = "***REDACTED***"
            else:
                result[key] = redact_sensitive_data(value, redact_fields)
        return result
    elif isinstance(data, list):
        return [redact_sensitive_data(item, redact_fields) for item in data]
    else:
        return data


def redact_email(text: str) -> str:
    """Redact email addresses from text.
    
    Args:
        text: Text that may contain email addresses
        
    Returns:
        Text with emails redacted
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.sub(email_pattern, '***@***', text)


def sanitize_log_message(message: str, payload: Optional[Dict] = None) -> str:
    """Sanitize a log message by removing sensitive data.
    
    Args:
        message: Log message
        payload: Optional payload dict to check for sensitive patterns
        
    Returns:
        Sanitized message
    """
    # Redact emails
    message = redact_email(message)
    
    # Redact common ID patterns if they look like tokens (long alphanumeric)
    # Keep short IDs (workspace IDs, user IDs) but redact long tokens
    token_pattern = r'\b[a-f0-9]{32,}\b'
    message = re.sub(token_pattern, '***TOKEN***', message, flags=re.IGNORECASE)
    
    return message
