"""Auth API endpoints: login, user profile, and password management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_auth
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.db_models import User

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class UserProfile(BaseModel):
    """User profile returned by /me and login."""

    email: str
    role: str
    scope: str
    tools: list[str]
    first_name: str | None = None
    last_name: str | None = None
    is_admin: bool = False


class LoginResponse(BaseModel):
    """Login response with JWT token and user profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserProfile


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email/password, return JWT access token."""
    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    user = result.scalar_one_or_none()

    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role})

    return LoginResponse(
        access_token=token,
        user=UserProfile(
            email=user.email,
            role=user.role,
            scope=user.scope,
            tools=user.tools or [],
            first_name=user.display_name,
            is_admin=user.is_admin,
        ),
    )


@router.get("/me", response_model=UserProfile)
async def me(user: dict = Depends(require_auth)):
    """Return the current user's profile."""
    return UserProfile(
        email=user["email"],
        role=user.get("role", "user"),
        scope=user.get("scope", "all"),
        tools=user.get("tools", []),
        first_name=user.get("first_name"),
        is_admin=user.get("role") == "admin",
    )


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    result = await db.execute(
        select(User).where(User.email == user["email"])
    )
    db_user = result.scalar_one_or_none()

    if db_user is None or not db_user.password_hash:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    db_user.password_hash = get_password_hash(body.new_password)
    await db.commit()

    return {"message": "Password updated"}
