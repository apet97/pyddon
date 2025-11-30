"""Security utilities for JWT validation and PII redaction."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from jwt import PyJWTError

# Clockify public key for JWT verification (RSA256)
CLOCKIFY_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAubktufFNO/op+E5WBWL6
/Y9QRZGSGGCsV00FmPRl5A0mSfQu3yq2Yaq47IlN0zgFy9IUG8/JJfwiehsmbrKa
49t/xSkpG1u9w1GUyY0g4eKDUwofHKAt3IPw0St4qsWLK9mO+koUo56CGQOEpTui
5bMfmefVBBfShXTaZOtXPB349FdzSuYlU/5o3L12zVWMutNhiJCKyGfsuu2uXa9+
6uQnZBw1wO3/QEci7i4TbC+ZXqW1rCcbogSMORqHAP6qSAcTFRmrjFAEsOWiUUhZ
rLDg2QJ8VTDghFnUhYklNTJlGgfo80qEWe1NLIwvZj0h3bWRfrqZHsD/Yjh0duk6
yQIDAQAB
-----END PUBLIC KEY-----"""


class SecurityError(Exception):
    """Exception raised for security validation failures."""
    pass


def verify_jwt_token(
    token: str,
    expected_addon_key: str,
    expected_workspace_id: Optional[str] = None,
    token_type: str = "addon"
) -> Dict[str, Any]:
    """Verify a Clockify JWT token.
    
    Args:
        token: JWT token string
        expected_addon_key: Expected add-on key (sub claim)
        expected_workspace_id: Optional expected workspace ID
        token_type: Expected token type (default: "addon")
        
    Returns:
        Decoded token claims if valid
        
    Raises:
        SecurityError: If token validation fails
    """
    try:
        # Decode and verify signature
        payload = jwt.decode(
            token,
            CLOCKIFY_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": True}
        )
        
        # Verify issuer
        if payload.get("iss") != "clockify":
            raise SecurityError("Invalid issuer: expected 'clockify'")
        
        # Verify token type
        if payload.get("type") != token_type:
            raise SecurityError(f"Invalid token type: expected '{token_type}'")
        
        # Verify subject (addon key)
        if payload.get("sub") != expected_addon_key:
            raise SecurityError(f"Invalid subject: expected '{expected_addon_key}'")
        
        # Optionally verify workspace ID
        if expected_workspace_id:
            token_workspace = payload.get("workspaceId")
            if token_workspace != expected_workspace_id:
                raise SecurityError(f"Workspace ID mismatch: expected '{expected_workspace_id}', got '{token_workspace}'")
        
        return payload
        
    except PyJWTError as e:
        raise SecurityError(f"JWT validation failed: {str(e)}")


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
