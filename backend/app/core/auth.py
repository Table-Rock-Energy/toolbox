"""Authentication and Authorization for Table Rock Tools.

This module provides:
- JWT token verification (replacing Firebase)
- User allowlist management (JSON file -- still used by admin.py during migration)
- Protected route middleware
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default admin email (fallback when DB has no admin user yet)
DEFAULT_ADMIN_EMAIL = "james@tablerocktx.com"

security = HTTPBearer(auto_error=False)


AVAILABLE_TOOLS = ["extract", "title", "proration", "revenue"]
AVAILABLE_ROLES = ["admin", "user", "viewer"]
AVAILABLE_SCOPES = ["all", "land", "revenue", "operations"]


class AllowedUser(BaseModel):
    """Allowed user entry."""
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    added_by: Optional[str] = None
    role: str = "user"
    scope: str = "all"
    tools: list[str] = AVAILABLE_TOOLS.copy()


# ============================================================================
# User management functions (DB-based, replaces JSON allowlist)
# ============================================================================


def _get_sync_session():
    """Get a sync session for non-async contexts."""
    from app.core.database import get_sync_session
    return get_sync_session()


def get_full_allowlist() -> list[dict]:
    """Get all users from PostgreSQL as dicts."""
    from app.models.db_models import User
    session = _get_sync_session()
    try:
        users = session.execute(select(User)).scalars().all()
        return [
            {
                "email": u.email,
                "first_name": u.display_name.split(" ", 1)[0] if u.display_name else None,
                "last_name": u.display_name.split(" ", 1)[1] if u.display_name and " " in u.display_name else None,
                "added_by": u.added_by,
                "role": u.role or "user",
                "scope": u.scope or "all",
                "tools": u.tools or AVAILABLE_TOOLS.copy(),
                "is_active": u.is_active,
            }
            for u in users
        ]
    finally:
        session.close()


def add_allowed_user(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    added_by: Optional[str] = None,
    role: str = "user",
    scope: str = "all",
    tools: Optional[list[str]] = None,
) -> bool:
    """Add a user to PostgreSQL. Returns False if already exists."""
    from app.models.db_models import User
    session = _get_sync_session()
    try:
        existing = session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()
        if existing:
            return False

        display_name = f"{first_name or ''} {last_name or ''}".strip() or None
        user = User(
            email=email.lower(),
            display_name=display_name,
            added_by=added_by,
            role=role,
            scope=scope,
            tools=tools if tools is not None else AVAILABLE_TOOLS.copy(),
            is_active=True,
        )
        session.add(user)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_allowed_user(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    role: Optional[str] = None,
    scope: Optional[str] = None,
    tools: Optional[list[str]] = None,
) -> bool:
    """Update a user in PostgreSQL."""
    from app.models.db_models import User
    session = _get_sync_session()
    try:
        user = session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()
        if user is None:
            return False

        if first_name is not None or last_name is not None:
            parts = []
            if first_name is not None:
                parts.append(first_name)
            elif user.display_name:
                parts.append(user.display_name.split(" ", 1)[0])
            if last_name is not None:
                parts.append(last_name)
            elif user.display_name and " " in user.display_name:
                parts.append(user.display_name.split(" ", 1)[1])
            user.display_name = " ".join(parts).strip() or None
        if role is not None:
            user.role = role
        if scope is not None:
            user.scope = scope
        if tools is not None:
            user.tools = tools

        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_by_email(email: str) -> Optional[dict]:
    """Get a user from PostgreSQL by email."""
    from app.models.db_models import User
    session = _get_sync_session()
    try:
        user = session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()
        if user is None:
            return None
        return {
            "email": user.email,
            "first_name": user.display_name.split(" ", 1)[0] if user.display_name else None,
            "last_name": user.display_name.split(" ", 1)[1] if user.display_name and " " in user.display_name else None,
            "added_by": user.added_by,
            "role": user.role or "user",
            "scope": user.scope or "all",
            "tools": user.tools or AVAILABLE_TOOLS.copy(),
            "is_active": user.is_active,
        }
    finally:
        session.close()


def is_user_admin(email: str) -> bool:
    """Check if a user has admin role via PostgreSQL."""
    user = get_user_by_email(email)
    if user is None:
        return email.lower() == DEFAULT_ADMIN_EMAIL
    return user.get("role", "user") == "admin"


def remove_allowed_user(email: str) -> bool:
    """Deactivate a user in PostgreSQL."""
    from app.models.db_models import User
    session = _get_sync_session()
    try:
        user = session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()
        if user is None:
            return False
        user.is_active = False
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_user_allowed(email: str) -> bool:
    """Check if a user exists and is active in PostgreSQL."""
    user = get_user_by_email(email)
    return user is not None and user.get("is_active", True)


# ============================================================================
# Password management (DB-based, replaces Firebase set_user_password)
# ============================================================================


async def set_user_password(email: str, password: str) -> dict:
    """Set or update a user's password hash in PostgreSQL.

    Replaces the old Firebase-based set_user_password.
    """
    from app.core.database import async_session_maker
    from app.core.security import get_password_hash
    from app.models.db_models import User

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User {email} not found in database")

        user.password_hash = get_password_hash(password)
        await session.commit()

    logger.info(f"Updated password for user: {email}")
    return {"action": "updated", "email": email}


# ============================================================================
# JWT-based authentication (replaces Firebase token verification)
# ============================================================================


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get the current authenticated user from the request.

    Returns user info if authenticated and authorized, None otherwise.
    Accepts a valid JWT access token or a CRON_SECRET for CI/cron jobs.
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # Check for cron secret (CI/scheduled jobs)
    if settings.cron_secret and token == settings.cron_secret:
        return {"email": "cron@tablerocktx.com", "uid": "cron", "cron": True}

    # Decode JWT token
    try:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        email = payload.get("sub")
        if email is None:
            return None
    except Exception:
        return None

    # DB lookup for active user
    from app.core.database import async_session_maker
    from app.models.db_models import User

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email, User.is_active == True)  # noqa: E712
        )
        user = result.scalar_one_or_none()

    if user is None:
        return None

    return {
        "email": user.email,
        "uid": str(user.id),
        "role": user.role,
        "scope": user.scope,
        "tools": user.tools or [],
        "first_name": user.display_name,
    }


async def require_auth(
    user: Optional[dict] = Depends(get_current_user)
) -> dict:
    """Require authentication for a route.

    Use this as a dependency for routes that require auth.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: dict = Depends(require_auth),
) -> dict:
    """Require admin role for a route.

    Chains on require_auth, then checks if the user has admin role.
    Uses DB-based role from JWT-decoded user dict, with james@ fallback.
    """
    if user.get("role") == "admin" or user.get("email", "").lower() == "james@tablerocktx.com":
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )
