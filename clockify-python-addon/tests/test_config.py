import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_validate_base_url():
    with pytest.raises(ValidationError):
        Settings(base_url="ftp://invalid", addon_key="demo", database_url="sqlite+aiosqlite:///./demo.db")


def test_settings_validate_domains():
    with pytest.raises(ValidationError):
        Settings(
            base_url="https://example.com",
            addon_key="demo",
            database_url="sqlite+aiosqlite:///./demo.db",
            allowed_api_domains=[],
        )
