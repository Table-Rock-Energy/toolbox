"""Shared test fixtures for auth mocking and HTTP clients."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import require_auth
from app.main import app


@pytest.fixture
def mock_user() -> dict:
    """Return a synthetic authenticated user."""
    return {"email": "test@example.com", "uid": "test-uid"}


@pytest_asyncio.fixture
async def authenticated_client(mock_user: dict):
    """HTTP client with auth dependency overridden to return mock_user."""
    async def _override_auth():
        return mock_user

    app.dependency_overrides[require_auth] = _override_auth
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_admin_user() -> dict:
    """Return a synthetic authenticated admin user."""
    return {"email": "james@tablerocktx.com", "uid": "admin-uid"}


@pytest_asyncio.fixture
async def admin_client(mock_admin_user: dict):
    """HTTP client with auth dependency overridden to return mock admin user."""
    async def _override_auth():
        return mock_admin_user

    app.dependency_overrides[require_auth] = _override_auth
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
