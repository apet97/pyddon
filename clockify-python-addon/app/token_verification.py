import httpx
import hmac
import hashlib
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
from jose import jwk, jwt as jose_jwt
from jose.exceptions import JWTError
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.errors import AuthenticationError
from app.metrics import metrics_registry

settings = get_settings()
logger = get_logger(__name__)

CANONICAL_SIGNATURE_HEADER = "Clockify-Signature"
LEGACY_SIGNATURE_HEADERS = ("X-Addon-Signature", "X-Webhook-Signature", "clockify-signature")
HMAC_ALGORITHMS = {
    "sha256": hashlib.sha256,
}


def resolve_signature_header(*candidates: Optional[str]) -> Optional[str]:
    """Return the first non-empty signature header from provided candidates."""
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _parse_hmac_components(signature: str) -> tuple[str, str]:
    """Support `sha256=<hex>` and bare hex encodings."""
    normalized = (signature or "").strip()
    if not normalized:
        raise AuthenticationError("Webhook signature verification failed: empty signature header")
    if "=" in normalized:
        prefix, digest = normalized.split("=", 1)
        digest = digest.strip()
        algorithm = prefix.strip().lower().replace("hmac-", "")
        return (algorithm or "sha256", digest)
    return "sha256", normalized


def _verify_hmac_signature(
    body: bytes,
    signature: str,
    workspace_id: Optional[str],
    scope: str = "webhook",
) -> Dict[str, Any]:
    """Validate Clockify webhook payloads using the shared secret when provided."""
    secret = settings.webhook_hmac_secret
    if not secret:
        raise AuthenticationError("Webhook signature verification failed")

    algorithm, presented = _parse_hmac_components(signature)
    hasher = HMAC_ALGORITHMS.get(algorithm)
    if not hasher:
        raise AuthenticationError(f"Webhook signature verification failed: unsupported HMAC algorithm '{algorithm}'")

    expected = hmac.new(secret.encode("utf-8"), body, hasher).hexdigest()
    if not hmac.compare_digest(presented.lower(), expected.lower()):
        raise AuthenticationError("Webhook signature verification failed: HMAC mismatch")

    logger.info(
        "webhook_signature_verified_hmac",
        workspace_id=workspace_id,
        algorithm=algorithm,
    )
    metrics_registry.record_hmac_fallback(scope)
    return {"workspaceId": workspace_id, "algorithm": algorithm}


# Cache for JWKS
_jwks_cache: Dict[str, Dict[str, Any]] = {}
_jwks_cache_time: Dict[str, float] = {}


async def fetch_jwks(jwks_url: Optional[str] = None) -> Dict[str, Any]:
    """Fetch JWKS from Clockify with caching per JWKS endpoint."""
    global _jwks_cache, _jwks_cache_time
    
    import time
    current_time = time.time()
    endpoint = jwks_url or settings.get_clockify_jwks_url()
    cached = _jwks_cache.get(endpoint)
    cached_time = _jwks_cache_time.get(endpoint, 0)
    
    # Cache for 1 hour
    if cached and (current_time - cached_time) < 3600:
        return cached
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, timeout=10.0)
            response.raise_for_status()
            parsed = response.json()
            _jwks_cache[endpoint] = parsed
            _jwks_cache_time[endpoint] = current_time
            logger.info("jwks_fetched", url=endpoint)
            return parsed
    except Exception as e:
        logger.error("jwks_fetch_failed", error=str(e), url=endpoint)
        if cached:
            logger.warning("using_cached_jwks_after_fetch_failure", url=endpoint)
            return cached
        raise AuthenticationError("Failed to fetch JWKS for token verification")


async def verify_jwt_token_rs256(
    token: str, 
    expected_workspace_id: Optional[str] = None,
    expected_addon_id: Optional[str] = None
) -> Dict[str, Any]:
    """Verify JWT token using RS256 and JWKS (production mode)."""
    
    try:
        # Get unverified header to find key ID
        unverified_header = jose_jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise AuthenticationError("Missing 'kid' in JWT header")
        
        # Fetch JWKS
        jwks = await fetch_jwks()
        
        # Find matching key
        key_data = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                key_data = key
                break
        
        if not key_data:
            raise AuthenticationError(f"Key with kid '{kid}' not found in JWKS")
        
        # Verify token with public key
        payload = jose_jwt.decode(
            token,
            key_data,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_aud": False}
        )
        
        # Validate required claims
        required_claims = ["iss", "sub", "workspaceId"]
        for claim in required_claims:
            if claim not in payload:
                raise AuthenticationError(f"Missing required claim: {claim}")
        
        # Validate issuer (must be 'clockify' according to docs)
        if payload.get("iss") != "clockify":
            raise AuthenticationError(f"Invalid issuer: {payload.get('iss')} (expected 'clockify')")
        
        # Validate sub claim must match addon key from manifest
        if payload.get("sub") != settings.addon_key:
            raise AuthenticationError(
                f"Sub claim mismatch: expected '{settings.addon_key}', got '{payload.get('sub')}'"
            )
        
        # Validate type claim must be 'addon'
        if payload.get("type") != "addon":
            raise AuthenticationError(f"Invalid type: {payload.get('type')} (expected 'addon')")
        
        # Validate workspace ID if provided
        if expected_workspace_id and payload.get("workspaceId") != expected_workspace_id:
            raise AuthenticationError(
                f"Workspace ID mismatch: expected {expected_workspace_id}, got {payload.get('workspaceId')}"
            )
        
        # Validate addon ID if provided
        if expected_addon_id and payload.get("addonId") != expected_addon_id:
            raise AuthenticationError(
                f"Addon ID mismatch: expected {expected_addon_id}, got {payload.get('addonId')}"
            )
        
        logger.info(
            "jwt_verified",
            workspace_id=payload.get("workspaceId"),
            addon_id=payload.get("addonId"),
            sub=payload.get("sub")
        )
        
        return payload
        
    except JWTError as e:
        logger.error("jwt_verification_failed", error=str(e))
        raise AuthenticationError(f"JWT verification failed: {str(e)}")


def verify_jwt_token(token: str, expected_workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """Verify JWT token with proper production/dev mode handling."""
    
    # Developer mode bypass
    if not settings.require_signature_verification or settings.is_development:
        logger.warning("jwt_verification_disabled_or_dev_mode")
        try:
            payload = jose_jwt.get_unverified_claims(token)
            return payload
        except Exception as e:
            logger.error("jwt_decode_failed", error=str(e))
            raise AuthenticationError("Invalid JWT token format")
    
    # Production mode - requires async, so this is a sync wrapper placeholder
    # In practice, use verify_jwt_token_rs256 directly in async contexts
    logger.error("verify_jwt_token_called_in_production_sync_context")
    raise AuthenticationError("Use async JWT verification in production mode")


def extract_token_from_header(authorization: Optional[str] = None) -> Optional[str]:
    """Extract token from Authorization header."""
    if not authorization:
        return None
    
    if authorization.startswith("Bearer "):
        return authorization[7:]
    
    return authorization


async def verify_addon_token(
    x_addon_token: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Dependency to verify addon token from request headers."""
    
    # Try X-Addon-Token first, then Authorization header
    token = x_addon_token or extract_token_from_header(authorization)
    
    if not token:
        if settings.is_development:
            logger.warning("no_token_provided_dev_mode")
            return {"workspaceId": "dev-workspace", "userId": "dev-user"}
        raise AuthenticationError("Missing authentication token")
    
    try:
        payload = verify_jwt_token(token)
        return payload
    except AuthenticationError:
        if settings.is_development:
            logger.warning("token_verification_failed_dev_mode")
            return {"workspaceId": "dev-workspace", "userId": "dev-user"}
        raise


async def verify_lifecycle_signature(
    request_body: bytes,
    clockify_signature: Optional[str],
    workspace_id: Optional[str] = None,
    addon_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify Clockify lifecycle event signature using the canonical Clockify-Signature header.
    """
    
    # Developer mode bypass
    if not settings.require_signature_verification:
        logger.warning("lifecycle_signature_verification_disabled")
        return {"workspaceId": workspace_id or "dev-workspace", "addonId": addon_id or settings.addon_key}
    
    if not clockify_signature:
        metrics_registry.record_signature_failure("lifecycle")
        raise AuthenticationError(f"Missing {CANONICAL_SIGNATURE_HEADER} header")
    
    try:
        # Verify JWT token with RS256
        payload = await verify_jwt_token_rs256(
            clockify_signature,
            expected_workspace_id=workspace_id,
            expected_addon_id=addon_id
        )
        
        logger.info(
            "lifecycle_signature_verified",
            workspace_id=payload.get("workspaceId"),
            addon_id=payload.get("addonId")
        )
        
        return payload
        
    except Exception as e:
        metrics_registry.record_signature_failure("lifecycle")
        logger.error("lifecycle_signature_verification_failed", error=str(e))
        raise AuthenticationError(f"Lifecycle signature verification failed: {str(e)}")


async def verify_webhook_signature(
    body: bytes,
    clockify_signature: Optional[str],
    workspace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify webhook signature using the canonical Clockify-Signature header.
    
    Clockify webhooks may use JWT tokens or HMAC signatures depending on configuration.
    Returns validated claims if using JWT, or basic validation info if using HMAC.
    """
    
    # Developer mode bypass
    if not settings.require_signature_verification:
        logger.warning("webhook_signature_verification_disabled")
        return {"workspaceId": workspace_id or "dev-workspace"}
    
    if not clockify_signature:
        metrics_registry.record_signature_failure("webhook")
        raise AuthenticationError(f"Missing {CANONICAL_SIGNATURE_HEADER} header")
    
    try:
        jwt_claims = await verify_jwt_token_rs256(
            clockify_signature,
            expected_workspace_id=workspace_id
        )

        logger.info(
            "webhook_signature_verified_jwt",
            workspace_id=jwt_claims.get("workspaceId")
        )

        return jwt_claims

    except AuthenticationError as err:
        logger.warning("jwt_verification_failed_trying_hmac", error=str(err))
        if settings.webhook_hmac_secret:
            try:
                return _verify_hmac_signature(body, clockify_signature, workspace_id, scope="webhook")
            except AuthenticationError:
                metrics_registry.record_signature_failure("webhook")
                raise
        metrics_registry.record_signature_failure("webhook")
        raise
    except Exception as e:
        metrics_registry.record_signature_failure("webhook")
        logger.error("webhook_signature_verification_failed", error=str(e))
        raise AuthenticationError(f"Webhook signature verification failed: {str(e)}") from e
