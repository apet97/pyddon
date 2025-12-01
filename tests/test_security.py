"""Tests for security utilities."""
from __future__ import annotations

import pytest

from clockify_core.security import (
    SecurityError,
    redact_sensitive_data,
    sanitize_log_message,
    verify_jwt_token,
    verify_lifecycle_signature,
    verify_webhook_signature,
)


@pytest.fixture(autouse=True)
def stub_jwk_client(monkeypatch):
    """Prevent network calls by stubbing JWKS client resolution."""

    class DummyKey:
        def __init__(self):
            self.key = "dummy"

    class DummyClient:
        def get_signing_key_from_jwt(self, token: str):
            return DummyKey()

    monkeypatch.setattr("clockify_core.security._get_jwk_client", lambda url: DummyClient())


def test_redact_sensitive_data_simple():
    data = {"username": "john", "token": "secret123", "api_key": "key456", "email": "test@example.com"}
    redacted = redact_sensitive_data(data)

    assert redacted["username"] == "john"
    assert redacted["token"] == "***REDACTED***"
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["email"] == "test@example.com"


def test_redact_sensitive_data_nested():
    data = {"user": {"name": "john", "auth_token": "secret123"}, "config": {"addon_token": "token456", "setting": "value"}}
    redacted = redact_sensitive_data(data)

    assert redacted["user"]["name"] == "john"
    assert redacted["user"]["auth_token"] == "***REDACTED***"
    assert redacted["config"]["addon_token"] == "***REDACTED***"
    assert redacted["config"]["setting"] == "value"


def test_redact_sensitive_data_list():
    data = {"items": [{"id": 1, "token": "secret1"}, {"id": 2, "password": "secret2"}]}
    redacted = redact_sensitive_data(data)

    assert redacted["items"][0]["id"] == 1
    assert redacted["items"][0]["token"] == "***REDACTED***"
    assert redacted["items"][1]["password"] == "***REDACTED***"


def test_redact_sensitive_data_case_insensitive():
    data = {"Token": "secret1", "AUTH_TOKEN": "secret2", "X-Addon-Token": "secret3"}
    redacted = redact_sensitive_data(data)

    assert redacted["Token"] == "***REDACTED***"
    assert redacted["AUTH_TOKEN"] == "***REDACTED***"
    assert redacted["X-Addon-Token"] == "***REDACTED***"


def test_sanitize_log_message_email():
    message = "User john.doe@example.com logged in"
    sanitized = sanitize_log_message(message)

    assert "john.doe@example.com" not in sanitized
    assert "***@***" in sanitized


def test_sanitize_log_message_token():
    message = "Token abcdef123456789abcdef123456789abc is invalid"
    sanitized = sanitize_log_message(message)

    assert "abcdef123456789abcdef123456789abc" not in sanitized
    assert "***TOKEN***" in sanitized


def test_verify_jwt_token_enforces_issuer(monkeypatch):
    monkeypatch.setattr(
        "clockify_core.security.jwt.decode",
        lambda *args, **kwargs: {"iss": "evil", "sub": "addon", "type": "addon"},
    )

    with pytest.raises(SecurityError, match="Invalid issuer"):
        verify_jwt_token("token", expected_addon_key="addon")


def test_verify_jwt_token_enforces_subject(monkeypatch):
    monkeypatch.setattr(
        "clockify_core.security.jwt.decode",
        lambda *args, **kwargs: {"iss": "clockify", "sub": "other", "type": "addon"},
    )

    with pytest.raises(SecurityError, match="Invalid subject"):
        verify_jwt_token("token", expected_addon_key="addon")


def test_verify_jwt_token_enforces_type(monkeypatch):
    monkeypatch.setattr(
        "clockify_core.security.jwt.decode",
        lambda *args, **kwargs: {"iss": "clockify", "sub": "addon", "type": "user"},
    )

    with pytest.raises(SecurityError, match="Invalid token type"):
        verify_jwt_token("token", expected_addon_key="addon")


def test_verify_jwt_token_workspace_mismatch(monkeypatch):
    monkeypatch.setattr(
        "clockify_core.security.jwt.decode",
        lambda *args, **kwargs: {
            "iss": "clockify",
            "sub": "addon",
            "type": "addon",
            "workspaceId": "wrong",
        },
    )

    with pytest.raises(SecurityError, match="Workspace ID mismatch"):
        verify_jwt_token("token", expected_addon_key="addon", expected_workspace_id="ws-expected")


def test_verify_jwt_token_success(monkeypatch):
    payload = {"iss": "clockify", "sub": "addon", "type": "addon", "workspaceId": "ws-1"}
    monkeypatch.setattr("clockify_core.security.jwt.decode", lambda *args, **kwargs: payload)

    assert verify_jwt_token("token", expected_addon_key="addon", expected_workspace_id="ws-1") == payload


def test_verify_webhook_signature_valid(monkeypatch):
    payload = {"iss": "clockify", "sub": "addon", "type": "addon", "workspaceId": "ws-1"}
    monkeypatch.setattr("clockify_core.security.jwt.decode", lambda *args, **kwargs: payload)

    assert verify_webhook_signature("token", expected_addon_key="addon", expected_workspace_id="ws-1") == payload


def test_verify_lifecycle_signature_invalid(monkeypatch):
    payload = {"iss": "clockify", "sub": "addon", "type": "addon", "workspaceId": "ws-1"}
    monkeypatch.setattr("clockify_core.security.jwt.decode", lambda *args, **kwargs: payload)

    with pytest.raises(SecurityError):
        verify_lifecycle_signature("token", expected_addon_key="addon", expected_workspace_id="ws-2")
