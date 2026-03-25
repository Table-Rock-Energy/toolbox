"""Authentication and Authorization for Table Rock Tools.

This module provides:
- JWT token verification (replacing Firebase)
- User allowlist management (JSON file -- still used by admin.py during migration)
- Protected route middleware
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings

logger = logging.getLogger(__name__)

# Path to allowlist file (local cache, still used by admin.py during migration)
ALLOWLIST_FILE = Path(__file__).parent.parent.parent / "data" / "allowed_users.json"

# Default allowed users
DEFAULT_ALLOWED_USERS = [
    "james@tablerocktx.com",
]

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
# Allowlist functions (still used by admin.py -- Phase 25 will replace)
# ============================================================================


def load_allowlist() -> list[str]:
    """Load allowed users from file, or return defaults."""
    if ALLOWLIST_FILE.exists():
        try:
            with open(ALLOWLIST_FILE, "r") as f:
                data = json.load(f)
                return [u.get("email", u) if isinstance(u, dict) else u for u in data]
        except Exception as e:
            logger.error(f"Error loading allowlist: {e}")
    return DEFAULT_ALLOWED_USERS.copy()


def save_allowlist(users: list[dict]) -> None:
    """Save allowed users to local file."""
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLOWLIST_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_full_allowlist() -> list[dict]:
    """Get full allowlist with metadata."""
    if ALLOWLIST_FILE.exists():
        try:
            with open(ALLOWLIST_FILE, "r") as f:
                data = json.load(f)
                result = []
                for u in data:
                    if isinstance(u, dict):
                        # Migrate old 'name' field if present
                        if "name" in u and "first_name" not in u:
                            old_name = u.pop("name", None) or ""
                            parts = old_name.strip().split(" ", 1)
                            u["first_name"] = parts[0] if parts[0] else None
                            u["last_name"] = parts[1] if len(parts) > 1 else None
                        result.append(u)
                    else:
                        result.append({"email": u})
                return result
        except Exception as e:
            logger.error(f"Error loading allowlist: {e}")
    return [{"email": e} for e in DEFAULT_ALLOWED_USERS]


def add_allowed_user(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    added_by: Optional[str] = None,
    role: str = "user",
    scope: str = "all",
    tools: Optional[list[str]] = None,
) -> bool:
    """Add a user to the allowlist."""
    users = get_full_allowlist()
    emails = [u.get("email", "").lower() for u in users]

    if email.lower() in emails:
        return False  # Already exists

    users.append({
        "email": email.lower(),
        "first_name": first_name,
        "last_name": last_name,
        "added_by": added_by,
        "role": role,
        "scope": scope,
        "tools": tools if tools is not None else AVAILABLE_TOOLS.copy(),
    })
    save_allowlist(users)
    return True


def update_allowed_user(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    role: Optional[str] = None,
    scope: Optional[str] = None,
    tools: Optional[list[str]] = None,
) -> bool:
    """Update a user in the allowlist."""
    users = get_full_allowlist()
    found = False

    for u in users:
        if u.get("email", "").lower() == email.lower():
            if first_name is not None:
                u["first_name"] = first_name
            if last_name is not None:
                u["last_name"] = last_name
            if role is not None:
                u["role"] = role
            if scope is not None:
                u["scope"] = scope
            if tools is not None:
                u["tools"] = tools
            found = True
            break

    if found:
        save_allowlist(users)
    return found


def get_user_by_email(email: str) -> Optional[dict]:
    """Get a single user from the allowlist by email."""
    users = get_full_allowlist()
    for u in users:
        if u.get("email", "").lower() == email.lower():
            return u
    return None


def is_user_admin(email: str) -> bool:
    """Check if a user has admin role.

    Uses JSON allowlist (intentional dual-path during migration).
    Phase 25 will unify this with DB-based role check in require_admin.
    """
    user = get_user_by_email(email)
    if user is None:
        return email.lower() == "james@tablerocktx.com"
    return user.get("role", "user") == "admin"


def remove_allowed_user(email: str) -> bool:
    """Remove a user from the allowlist."""
    users = get_full_allowlist()
    original_count = len(users)
    users = [u for u in users if u.get("email", "").lower() != email.lower()]

    if len(users) < original_count:
        save_allowlist(users)
        return True
    return False


def is_user_allowed(email: str) -> bool:
    """Check if a user is in the allowlist."""
    allowed = load_allowlist()
    return email.lower() in [e.lower() for e in allowed]


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
