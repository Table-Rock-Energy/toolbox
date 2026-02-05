"""Admin API endpoints for user management."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr

from app.core.auth import (
    get_full_allowlist,
    add_allowed_user,
    remove_allowed_user,
    is_user_allowed,
)
from app.services.storage_service import profile_storage

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


@router.post("/upload-profile-image")
async def upload_profile_image(
    file: Annotated[UploadFile, File(description="Profile image file")],
    user_id: Annotated[str, Form(description="Firebase user ID")],
):
    """
    Upload a profile image for a user.

    Args:
        file: Image file (JPG, PNG, etc.)
        user_id: Firebase user ID

    Returns:
        URL to the uploaded image
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file."
        )

    # Validate file size (max 5MB)
    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 5MB."
        )

    try:
        # Save to storage
        path = profile_storage.save_profile_image(
            content=file_bytes,
            user_id=user_id,
            filename=file.filename
        )

        logger.info(f"Uploaded profile image for user {user_id}: {path}")

        # For now, return a placeholder URL
        # In production with GCS, this would be a signed URL
        photo_url = profile_storage.get_profile_image_url(user_id)

        return {
            "success": True,
            "path": path,
            "photo_url": photo_url,
        }

    except Exception as e:
        logger.exception(f"Error uploading profile image: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload image: {str(e)}"
        ) from e
