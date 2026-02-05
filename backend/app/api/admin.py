"""Admin API endpoints for user management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.auth import (
    get_full_allowlist,
    add_allowed_user,
    remove_allowed_user,
    is_user_allowed,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class AddUserRequest(BaseModel):
    """Request to add a user to the allowlist."""
    email: EmailStr
    name: Optional[str] = None


class RemoveUserRequest(BaseModel):
    """Request to remove a user from the allowlist."""
    email: EmailStr


class UserResponse(BaseModel):
    """User in the allowlist."""
    email: str
    name: Optional[str] = None
    added_by: Optional[str] = None


class AllowlistResponse(BaseModel):
    """Response containing the full allowlist."""
    users: list[UserResponse]
    count: int


@router.get("/users", response_model=AllowlistResponse)
async def list_allowed_users():
    """List all users in the allowlist."""
    users = get_full_allowlist()
    return AllowlistResponse(
        users=[UserResponse(**u) for u in users],
        count=len(users)
    )


@router.post("/users", response_model=UserResponse)
async def add_user(request: AddUserRequest):
    """Add a user to the allowlist."""
    success = add_allowed_user(
        email=request.email,
        name=request.name,
        added_by="admin"  # In production, get from auth context
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"User {request.email} already in allowlist"
        )

    logger.info(f"Added user to allowlist: {request.email}")
    return UserResponse(
        email=request.email.lower(),
        name=request.name,
        added_by="admin"
    )


@router.delete("/users/{email}")
async def remove_user(email: str):
    """Remove a user from the allowlist."""
    # Prevent removing the primary admin
    if email.lower() == "james@tablerocktx.com":
        raise HTTPException(
            status_code=400,
            detail="Cannot remove primary admin user"
        )

    success = remove_allowed_user(email)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"User {email} not found in allowlist"
        )

    logger.info(f"Removed user from allowlist: {email}")
    return {"message": f"User {email} removed from allowlist"}


@router.get("/users/{email}/check")
async def check_user(email: str):
    """Check if a user is in the allowlist."""
    allowed = is_user_allowed(email)
    return {
        "email": email,
        "allowed": allowed
    }
