import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.models import Base
from app.config import get_settings


# Remove custom event_loop fixture - use pytest-asyncio's default


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session."""
    
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
def sample_workspace_id() -> str:
    """Return sample workspace ID for tests."""
    return "test-workspace-123"


@pytest.fixture
def sample_addon_id() -> str:
    """Return sample addon ID for tests."""
    return "clockify-python-addon"


@pytest.fixture
def sample_addon_token() -> str:
    """Return sample addon token for tests."""
    return "test-addon-token-abc123"


@pytest.fixture
def sample_lifecycle_install_payload(sample_workspace_id, sample_addon_id, sample_addon_token):
    """Return sample lifecycle install payload."""
    return {
        "workspaceId": sample_workspace_id,
        "addonId": sample_addon_id,
        "apiUrl": "https://api.clockify.me/api/v1",
        "addonToken": sample_addon_token,
        "userId": "test-user-123",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_webhook_payload(sample_workspace_id):
    """Return sample webhook payload."""
    return {
        "workspaceId": sample_workspace_id,
        "id": "webhook-event-123",
        "userId": "test-user-123",
        "projectId": "test-project-123",
        "timestamp": "2024-01-01T00:00:00Z"
    }
