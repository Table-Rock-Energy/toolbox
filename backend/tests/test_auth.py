"""Tests for auth API endpoints, JWT fail-fast, and seed script."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.db_models import User


# ---------------------------------------------------------------------------
# Helpers: mock DB session returning a pre-configured User
# ---------------------------------------------------------------------------


def _make_mock_user(
    email: str = "test@example.com",
    password: str = "testpass123",
    is_active: bool = True,
    role: str = "user",
    is_admin: bool = False,
) -> User:
    """Create a mock User ORM object with a real bcrypt hash."""
    user = MagicMock(spec=User)
    user.email = email
    user.password_hash = get_password_hash(password)
    user.is_active = is_active
    user.role = role
    user.is_admin = is_admin
    user.scope = "all"
    user.tools = ["extract", "title", "proration", "revenue"]
    user.display_name = "Test"
    user.last_login_at = None
    return user


def _mock_db_session(user_to_return):
    """Create an async generator that yields a mock AsyncSession.

    The session's execute().scalar_one_or_none() returns `user_to_return`.
    """

    async def _override_get_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user_to_return

        session = AsyncMock()
        session.execute.return_value = mock_result
        session.commit = AsyncMock()
        yield session

    return _override_get_db


# ---------------------------------------------------------------------------
# Login endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success():
    """POST /api/auth/login with valid credentials returns JWT + profile."""
    mock_user = _make_mock_user()
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "testpass123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "user"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_wrong_password():
    """POST /api/auth/login with wrong password returns 401."""
    mock_user = _make_mock_user()
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_unknown_email():
    """POST /api/auth/login with unknown email returns 401."""
    app.dependency_overrides[get_db] = _mock_db_session(None)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": "nobody@example.com", "password": "testpass123"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_inactive_user():
    """POST /api/auth/login with inactive user returns 403."""
    mock_user = _make_mock_user(is_active=False)
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "testpass123"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# /me endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_returns_profile(authenticated_client: AsyncClient):
    """GET /api/auth/me with valid token returns user profile."""
    response = await authenticated_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"
    assert data["scope"] == "all"
    assert "tools" in data


@pytest.mark.asyncio
async def test_me_no_token_401(unauthenticated_client: AsyncClient):
    """GET /api/auth/me without token returns 401."""
    response = await unauthenticated_client.get("/api/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# JWT fail-fast startup check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwt_secret_required_in_prod():
    """App raises SystemExit if JWT_SECRET_KEY is default in production."""
    from app.core.config import settings
    from app.main import startup_event

    with patch.object(settings, "environment", "production"), \
         patch.object(settings, "encryption_key", "some-key"), \
         patch.object(settings, "jwt_secret_key", "dev-only-change-in-production"):
        with pytest.raises(SystemExit):
            await startup_event()


# ---------------------------------------------------------------------------
# Seed script tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_admin_create():
    """Seed script creates admin user when none exists."""
    from scripts.create_admin import main

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.create_admin.getpass", side_effect=["adminpass123", "adminpass123"]), \
         patch("app.core.database.async_session_maker", mock_session_maker):
        await main()

    mock_session.add.assert_called_once()
    added_user = mock_session.add.call_args[0][0]
    assert added_user.email == "james@tablerocktx.com"
    assert added_user.password_hash is not None
    assert added_user.is_admin is True
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_seed_admin_update():
    """Seed script updates existing admin user's password."""
    from scripts.create_admin import main

    existing_user = MagicMock(spec=User)
    existing_user.email = "james@tablerocktx.com"
    existing_user.password_hash = "old-hash"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.create_admin.getpass", side_effect=["newpass12345", "newpass12345"]), \
         patch("app.core.database.async_session_maker", mock_session_maker):
        await main()

    assert existing_user.password_hash != "old-hash"
    assert existing_user.role == "admin"
    assert existing_user.is_admin is True
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Change password endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_success(authenticated_client: AsyncClient):
    """POST /api/auth/change-password with valid current password succeeds."""
    mock_user = _make_mock_user(password="oldpass123")
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        response = await authenticated_client.post(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "newpass456"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password updated"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_change_password_wrong_current(authenticated_client: AsyncClient):
    """POST /api/auth/change-password with wrong current password returns 401."""
    mock_user = _make_mock_user(password="oldpass123")
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        response = await authenticated_client.post(
            "/api/auth/change-password",
            json={"current_password": "wrongpass", "new_password": "newpass456"},
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_change_password_too_short(authenticated_client: AsyncClient):
    """POST /api/auth/change-password with short new password returns 422."""
    mock_user = _make_mock_user(password="oldpass123")
    app.dependency_overrides[get_db] = _mock_db_session(mock_user)

    try:
        response = await authenticated_client.post(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "short"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Seed script tests
# ---------------------------------------------------------------------------


def test_seed_admin_short_password():
    """Seed script rejects passwords shorter than 8 characters."""
    import asyncio
    from scripts.create_admin import main

    with patch("scripts.create_admin.getpass", return_value="short"):
        with pytest.raises(SystemExit) as exc_info:
            asyncio.run(main())
        assert exc_info.value.code == 1
