"""
Tests for security features including JWT verification and signature validation.
"""
import hashlib
import hmac

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.token_verification import (
    fetch_jwks,
    verify_jwt_token_rs256,
    verify_lifecycle_signature,
    verify_webhook_signature,
)
from app.utils.errors import AuthenticationError


@pytest.mark.asyncio
async def test_jwks_caching():
    """Test that JWKS is cached properly."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"keys": [{"kid": "test-key", "kty": "RSA"}]}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # First call should fetch
        jwks1 = await fetch_jwks()
        assert "keys" in jwks1
        
        # Second call should use cache
        jwks2 = await fetch_jwks()
        assert jwks1 == jwks2
        
        # Should only call once due to caching
        assert mock_client.return_value.__aenter__.return_value.get.call_count == 1


@pytest.mark.asyncio
async def test_jwt_verification_missing_kid():
    """Test JWT verification fails when token is invalid."""
    with pytest.raises(AuthenticationError, match="JWT verification failed"):
        # Invalid token format
        await verify_jwt_token_rs256("invalid.token.here", "workspace-123")


@pytest.mark.asyncio
async def test_lifecycle_signature_disabled_flag():
    """Lifecycle signature verification bypasses only when explicitly disabled."""
    with patch("app.token_verification.settings") as mock_settings:
        mock_settings.require_signature_verification = False
        mock_settings.addon_key = "test-addon"
        
        result = await verify_lifecycle_signature(
            b"test body",
            "fake-signature",
            workspace_id="workspace-123",
            addon_id="test-addon"
        )
        
        assert result["workspaceId"] == "workspace-123"
        assert result["addonId"] == "test-addon"


@pytest.mark.asyncio
async def test_lifecycle_signature_missing_header():
    """Test lifecycle signature fails when header is missing."""
    with patch("app.token_verification.settings") as mock_settings:
        mock_settings.require_signature_verification = True
        
        with pytest.raises(AuthenticationError, match="Missing Clockify-Signature"):
            await verify_lifecycle_signature(
                b"test body",
                None,
                workspace_id="workspace-123"
            )


@pytest.mark.asyncio
async def test_webhook_signature_disabled_flag():
    """Webhook signature verification bypasses only when explicitly disabled."""
    with patch("app.token_verification.settings") as mock_settings:
        mock_settings.require_signature_verification = False
        
        result = await verify_webhook_signature(
            b"test body",
            "fake-signature",
            workspace_id="workspace-123"
        )
        
        assert result["workspaceId"] == "workspace-123"


@pytest.mark.asyncio
async def test_webhook_signature_missing_header():
    """Test webhook signature fails when header is missing."""
    with patch("app.token_verification.settings") as mock_settings:
        mock_settings.require_signature_verification = True
        
        with pytest.raises(AuthenticationError, match="Missing Clockify-Signature"):
            await verify_webhook_signature(
                b"test body",
                None,
                workspace_id="workspace-123"
            )


def test_signature_disabled_logs_warning(caplog, capsys):
    """Disabling verification should emit a clear warning."""
    import logging
    caplog.set_level(logging.WARNING)
    
    with patch("app.token_verification.settings") as mock_settings:
        mock_settings.require_signature_verification = False
        mock_settings.is_development = True
        
        from app.token_verification import verify_jwt_token
        
        try:
            # Call with unverified token
            payload = verify_jwt_token("fake.token.here")
        except:
            pass  # May fail to decode, but should log warning
        
        stdout = capsys.readouterr().out
        assert "jwt_verification_disabled_or_dev_mode" in stdout


@pytest.mark.asyncio
async def test_workspace_id_enforcement(monkeypatch):
    """Mismatch between expected and claimed workspace IDs should be rejected."""
    monkeypatch.setattr(
        "app.token_verification.fetch_jwks",
        AsyncMock(return_value={"keys": [{"kid": "kid-1"}]}),
    )
    monkeypatch.setattr(
        "app.token_verification.jose_jwt.get_unverified_header",
        lambda _token: {"kid": "kid-1"},
    )
    monkeypatch.setattr(
        "app.token_verification.jose_jwt.decode",
        lambda *args, **kwargs: {
            "iss": "clockify",
            "sub": "clockify-python-addon",
            "type": "addon",
            "workspaceId": "ws-actual",
            "addonId": "addon-1",
        },
    )

    with pytest.raises(AuthenticationError, match="Workspace ID mismatch"):
        await verify_jwt_token_rs256("test.token", expected_workspace_id="ws-expected")


@pytest.mark.asyncio
async def test_addon_id_enforcement(monkeypatch):
    """Addon ID mismatches must raise AuthenticationError."""
    monkeypatch.setattr(
        "app.token_verification.fetch_jwks",
        AsyncMock(return_value={"keys": [{"kid": "kid-2"}]}),
    )
    monkeypatch.setattr(
        "app.token_verification.jose_jwt.get_unverified_header",
        lambda _token: {"kid": "kid-2"},
    )
    monkeypatch.setattr(
        "app.token_verification.jose_jwt.decode",
        lambda *args, **kwargs: {
            "iss": "clockify",
            "sub": "clockify-python-addon",
            "type": "addon",
            "workspaceId": "workspace-123",
            "addonId": "addon-real",
        },
    )

    with pytest.raises(AuthenticationError, match="Addon ID mismatch"):
        await verify_jwt_token_rs256("test.token", expected_addon_id="addon-expected")


@pytest.mark.asyncio
async def test_webhook_hmac_fallback_success(monkeypatch):
    """When JWT fails but HMAC secret is set, signatures should still verify."""
    body = b'{"workspaceId":"ws-1"}'
    shared_secret = "top-secret"
    digest = hmac.new(shared_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        "app.token_verification.verify_jwt_token_rs256",
        AsyncMock(side_effect=AuthenticationError("bad jwt")),
    )
    from app.token_verification import settings as global_settings

    monkeypatch.setattr(global_settings, "require_signature_verification", True)
    monkeypatch.setattr(global_settings, "webhook_hmac_secret", shared_secret)

    result = await verify_webhook_signature(body, f"sha256={digest}", workspace_id="ws-1")
    assert result["workspaceId"] == "ws-1"
    assert result["algorithm"] == "sha256"


@pytest.mark.asyncio
async def test_webhook_hmac_fallback_rejects_mismatch(monkeypatch):
    """Invalid HMAC signatures should raise AuthenticationError."""
    body = b'{"workspaceId":"ws-2"}'
    shared_secret = "top-secret"

    monkeypatch.setattr(
        "app.token_verification.verify_jwt_token_rs256",
        AsyncMock(side_effect=AuthenticationError("bad jwt")),
    )
    from app.token_verification import settings as global_settings

    monkeypatch.setattr(global_settings, "require_signature_verification", True)
    monkeypatch.setattr(global_settings, "webhook_hmac_secret", shared_secret)

    with pytest.raises(AuthenticationError, match="HMAC mismatch"):
        await verify_webhook_signature(body, "sha256=deadbeef", workspace_id="ws-2")


def test_signature_header_resolution_prefers_canonical():
    from app.token_verification import resolve_signature_header
    assert resolve_signature_header("canonical", "legacy") == "canonical"
    assert resolve_signature_header(None, "legacy") == "legacy"
    assert resolve_signature_header(None, None) is None


def test_settings_auto_selects_jwks_url():
    from app.config import Settings
    prod_settings = Settings(clockify_environment="prod", clockify_jwks_url=None)
    dev_settings = Settings(clockify_environment="dev", clockify_jwks_url=None)
    override_settings = Settings(clockify_jwks_url="https://custom.example/jwks.json")
    assert "api.clockify.me" in prod_settings.get_clockify_jwks_url()
    assert "developer.clockify.me" in dev_settings.get_clockify_jwks_url()
    assert override_settings.get_clockify_jwks_url() == "https://custom.example/jwks.json"
