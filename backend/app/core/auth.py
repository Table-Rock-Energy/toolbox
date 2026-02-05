"""Firebase Authentication and Authorization for Table Rock Tools.

This module provides:
- Firebase token verification
- User allowlist management
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

logger = logging.getLogger(__name__)

# Path to allowlist file
ALLOWLIST_FILE = Path(__file__).parent.parent.parent / "data" / "allowed_users.json"

# Default allowed users
DEFAULT_ALLOWED_USERS = [
    "james@tablerocktx.com",
]

security = HTTPBearer(auto_error=False)


class AllowedUser(BaseModel):
    """Allowed user entry."""
    email: str
    name: Optional[str] = None
    added_by: Optional[str] = None


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
    """Save allowed users to file."""
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLOWLIST_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_full_allowlist() -> list[dict]:
    """Get full allowlist with metadata."""
    if ALLOWLIST_FILE.exists():
        try:
            with open(ALLOWLIST_FILE, "r") as f:
                data = json.load(f)
                # Normalize to dict format
                return [
                    u if isinstance(u, dict) else {"email": u}
                    for u in data
                ]
        except Exception as e:
            logger.error(f"Error loading allowlist: {e}")
    return [{"email": e} for e in DEFAULT_ALLOWED_USERS]


def add_allowed_user(email: str, name: Optional[str] = None, added_by: Optional[str] = None) -> bool:
    """Add a user to the allowlist."""
    users = get_full_allowlist()
    emails = [u.get("email", "").lower() for u in users]

    if email.lower() in emails:
        return False  # Already exists

    users.append({
        "email": email.lower(),
        "name": name,
        "added_by": added_by,
    })
    save_allowlist(users)
    return True


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
