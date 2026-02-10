"""Firebase Authentication and Authorization for Table Rock Tools.

This module provides:
- Firebase token verification
- User allowlist management (persisted to Firestore)
- Protected route middleware
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Path to allowlist file (local cache, source of truth is Firestore)
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
    """Save allowed users to local file and schedule Firestore persist."""
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLOWLIST_FILE, "w") as f:
        json.dump(users, f, indent=2)

    # Fire-and-forget Firestore persist
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_allowlist_to_firestore(users))
    except RuntimeError:
        pass  # No event loop running


async def _persist_allowlist_to_firestore(users: list[dict]) -> None:
    """Async: save allowlist to Firestore."""
    try:
        from app.services.firestore_service import set_config_doc
        await set_config_doc("allowed_users", {"users": users})
        logger.info(f"Persisted {len(users)} users to Firestore")
    except Exception as e:
        logger.warning(f"Failed to persist allowlist to Firestore: {e}")


async def init_allowlist_from_firestore() -> None:
    """Load allowlist from Firestore on startup. Seeds Firestore if empty."""
    try:
        from app.services.firestore_service import get_config_doc, set_config_doc
        data = await get_config_doc("allowed_users")
        if data and "users" in data:
            users = data["users"]
            # Migrate old 'name' field to first_name/last_name
            for u in users:
                if "name" in u and "first_name" not in u:
                    old_name = u.pop("name", None) or ""
                    parts = old_name.strip().split(" ", 1)
                    u["first_name"] = parts[0] if parts[0] else None
                    u["last_name"] = parts[1] if len(parts) > 1 else None
            save_allowlist(users)
            logger.info(f"Loaded {len(users)} users from Firestore")
        else:
            # Seed Firestore from local file
            users = get_full_allowlist()
            await set_config_doc("allowed_users", {"users": users})
            logger.info(f"Seeded Firestore with {len(users)} users from local file")
    except Exception as e:
        logger.warning(f"Could not load allowlist from Firestore: {e}")


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
    """Check if a user has admin role."""
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


# Firebase Admin SDK initialization (lazy)
_firebase_app = None


def get_firebase_app():
    """Get or initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is None:
        try:
            import firebase_admin
            from firebase_admin import credentials

            # Try to initialize with default credentials (for Cloud Run)
            # or with a service account file
            try:
                _firebase_app = firebase_admin.get_app()
            except ValueError:
                # App not initialized, try to initialize
                try:
                    # First try Application Default Credentials
                    _firebase_app = firebase_admin.initialize_app()
                except Exception:
                    # Log but don't fail - we'll handle auth differently
                    logger.warning("Firebase Admin SDK not initialized - running without server-side auth")
                    return None
        except ImportError:
            logger.warning("firebase-admin not installed")
            return None
    return _firebase_app


def set_user_password(email: str, password: str) -> dict:
    """Set or update a Firebase user's password.

    If the user doesn't exist in Firebase Auth, creates a new account.
    Returns a dict with status info.
    """
    app = get_firebase_app()
    if app is None:
        raise RuntimeError("Firebase Admin SDK not initialized")

    from firebase_admin import auth as fb_auth

    try:
        # Try to find existing user
        user = fb_auth.get_user_by_email(email)
        fb_auth.update_user(user.uid, password=password)
        logger.info(f"Updated password for Firebase user: {email}")
        return {"action": "updated", "email": email}
    except fb_auth.UserNotFoundError:
        # Create new Firebase Auth user with this email/password
        fb_auth.create_user(email=email, password=password)
        logger.info(f"Created Firebase user with password: {email}")
        return {"action": "created", "email": email}
    except Exception as e:
        logger.error(f"Failed to set password for {email}: {e}")
        raise


async def verify_firebase_token(token: str) -> Optional[dict]:
    """Verify a Firebase ID token and return the decoded token."""
    app = get_firebase_app()
    if app is None:
        # Fall back to client-side only auth
        # In production, you'd want to verify the token properly
        logger.warning("Firebase not configured - skipping server-side verification")
        return None

    try:
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get the current authenticated user from the request.

    Returns user info if authenticated and authorized, None otherwise.
    For now, returns None to allow unauthenticated access during development.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    decoded = await verify_firebase_token(token)

    if decoded is None:
        # During development, we might not have Firebase Admin configured
        # Just check the Authorization header exists
        return None

    # Check if user is in allowlist
    email = decoded.get("email")
    if email and not is_user_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to access this application"
        )

    return decoded


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
    """
    email = user.get("email", "")
    if not is_user_admin(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
