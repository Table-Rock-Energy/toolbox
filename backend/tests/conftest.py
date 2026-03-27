"""Shared test fixtures for auth mocking and HTTP clients."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import require_auth
from app.core.database import get_db
from app.main import app


async def _mock_db_session():
    """Yield a mock AsyncSession so tests never hit PostgreSQL."""
    yield MagicMock()


def _mock_sync_session():
    """Return a mock sync session whose queries return None."""
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalars.return_value.all.return_value = []
    return session


@pytest.fixture(autouse=True)
def _patch_sync_db():
    """Prevent all sync PostgreSQL access (used by auth helpers like is_user_admin)."""
    with patch("app.core.auth._get_sync_session", _mock_sync_session):
        yield


@pytest.fixture
def mock_user() -> dict:
    """Return a synthetic authenticated user."""
    return {"email": "test@example.com", "uid": "test-uid", "role": "user", "scope": "all", "tools": ["extract", "title", "proration", "revenue"]}


@pytest_asyncio.fixture
async def authenticated_client(mock_user: dict):
    """HTTP client with auth dependency overridden to return mock_user."""
    async def _override_auth():
        return mock_user

    app.dependency_overrides[require_auth] = _override_auth
    app.dependency_overrides[get_db] = _mock_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_admin_user() -> dict:
    """Return a synthetic authenticated admin user."""
    return {"email": "james@tablerocktx.com", "uid": "admin-uid", "role": "admin", "scope": "all", "tools": ["extract", "title", "proration", "revenue"]}


@pytest_asyncio.fixture
async def admin_client(mock_admin_user: dict):
    """HTTP client with auth dependency overridden to return mock admin user."""
    async def _override_auth():
        return mock_admin_user

    app.dependency_overrides[require_auth] = _override_auth
    app.dependency_overrides[get_db] = _mock_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client():
    """HTTP client with no auth overrides (requests will be unauthenticated)."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _mock_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
