"""Admin API endpoints for user management and app settings."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from app.core.auth import (
    AVAILABLE_TOOLS,
    AVAILABLE_ROLES,
    AVAILABLE_SCOPES,
    get_full_allowlist,
    add_allowed_user,
    update_allowed_user,
    remove_allowed_user,
    is_user_allowed,
    is_user_admin,
    get_user_by_email,
    require_admin,
    set_user_password,
)
from app.services.storage_service import profile_storage, storage_service

logger = logging.getLogger(__name__)
router = APIRouter()

# App settings file (local cache, source of truth is Firestore)
APP_SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "app_settings.json"


def load_app_settings() -> dict:
    """Load app settings from local file cache."""
    if APP_SETTINGS_FILE.exists():
        try:
            with open(APP_SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading app settings: {e}")
    return {}


def save_app_settings(settings_data: dict) -> None:
    """Save app settings to local file and schedule Firestore persist."""
    APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_SETTINGS_FILE, "w") as f:
        json.dump(settings_data, f, indent=2)

    # Fire-and-forget Firestore persist
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_app_settings_to_firestore(settings_data))
    except RuntimeError:
        pass  # No event loop running


async def _persist_app_settings_to_firestore(settings_data: dict) -> None:
    """Async: save app settings to Firestore."""
    try:
        from app.services.firestore_service import set_config_doc
        await set_config_doc("app_settings", settings_data)
        logger.info("Persisted app settings to Firestore")
    except Exception as e:
        logger.warning(f"Failed to persist app settings to Firestore: {e}")


async def init_app_settings_from_firestore() -> None:
    """Load app settings from Firestore on startup. Seeds Firestore if empty."""
    try:
        from app.services.firestore_service import get_config_doc, set_config_doc
        data = await get_config_doc("app_settings")
        if data:
            # Remove internal Firestore fields before saving locally
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            # Write to local file cache
            APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(APP_SETTINGS_FILE, "w") as f:
                json.dump(clean, f, indent=2)

            # Update runtime config
            _apply_settings_to_runtime(clean)
            logger.info("Loaded app settings from Firestore")
        else:
            # Seed Firestore from local file
            local = load_app_settings()
            if local:
                await set_config_doc("app_settings", local)
                logger.info("Seeded Firestore with local app settings")
    except Exception as e:
        logger.warning(f"Could not load app settings from Firestore: {e}")


def _apply_settings_to_runtime(settings_data: dict) -> None:
    """Apply loaded settings to the runtime config object."""
    from app.core.config import settings as runtime_settings

    gemini = settings_data.get("gemini", {})
    if gemini.get("api_key"):
        runtime_settings.gemini_api_key = gemini["api_key"]
    if "enabled" in gemini:
        runtime_settings.gemini_enabled = gemini["enabled"]
    if "model" in gemini:
        runtime_settings.gemini_model = gemini["model"]
    if "monthly_budget" in gemini:
        runtime_settings.gemini_monthly_budget = gemini["monthly_budget"]

    gmaps = settings_data.get("google_maps", {})
    if gmaps.get("api_key"):
        runtime_settings.google_maps_api_key = gmaps["api_key"]
    if "enabled" in gmaps:
        runtime_settings.google_maps_enabled = gmaps["enabled"]


class AddUserRequest(BaseModel):
    """Request to add a user to the allowlist."""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "user"
    scope: str = "all"
    tools: list[str] = AVAILABLE_TOOLS.copy()
    password: Optional[str] = None


class UpdateUserRequest(BaseModel):
    """Request to update a user in the allowlist."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    scope: Optional[str] = None
    tools: Optional[list[str]] = None
    password: Optional[str] = None


class RemoveUserRequest(BaseModel):
    """Request to remove a user from the allowlist."""
    email: EmailStr


class UserResponse(BaseModel):
    """User in the allowlist."""
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    added_by: Optional[str] = None
    role: str = "user"
    scope: str = "all"
    tools: list[str] = AVAILABLE_TOOLS.copy()


class AllowlistResponse(BaseModel):
    """Response containing the full allowlist."""
    users: list[UserResponse]
    count: int


class GeminiSettingsRequest(BaseModel):
    """Request to update Gemini API key settings."""
    api_key: Optional[str] = None
    enabled: bool = False
    model: str = "gemini-2.5-flash"
    monthly_budget: float = 15.00


class GeminiSettingsResponse(BaseModel):
    """Response with Gemini settings (key masked)."""
    has_key: bool
    enabled: bool
    model: str
    monthly_budget: float


class GoogleMapsSettingsRequest(BaseModel):
    """Request to update Google Maps API settings."""
    api_key: Optional[str] = None
    enabled: bool = False


class GoogleMapsSettingsResponse(BaseModel):
    """Response with Google Maps settings (key masked)."""
    has_key: bool
    enabled: bool


class OptionsResponse(BaseModel):
    """Available options for user management."""
    roles: list[str]
    scopes: list[str]
    tools: list[str]


@router.get("/options", response_model=OptionsResponse)
async def get_options():
    """Get available roles, scopes, and tools for user management."""
    return OptionsResponse(
        roles=AVAILABLE_ROLES,
        scopes=AVAILABLE_SCOPES,
        tools=AVAILABLE_TOOLS,
    )


@router.get("/users", response_model=AllowlistResponse)
async def list_allowed_users():
    """List all users in the allowlist."""
    users = get_full_allowlist()
    return AllowlistResponse(
        users=[UserResponse(**u) for u in users],
        count=len(users)
    )


@router.post("/users", response_model=UserResponse)
async def add_user(request: AddUserRequest, user: dict = Depends(require_admin)):
    """Add a user to the allowlist."""
    success = add_allowed_user(
        email=request.email,
        first_name=request.first_name,
        last_name=request.last_name,
        added_by="admin",
        role=request.role,
        scope=request.scope,
        tools=request.tools,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"User {request.email} already in allowlist"
        )

    # Set password in Firebase Auth if provided
    if request.password:
        try:
            set_user_password(request.email, request.password)
        except Exception as e:
            logger.warning(f"Added user to allowlist but failed to set password: {e}")

    logger.info(f"Added user to allowlist: {request.email}")
    return UserResponse(
        email=request.email.lower(),
        first_name=request.first_name,
        last_name=request.last_name,
        added_by="admin",
        role=request.role,
        scope=request.scope,
        tools=request.tools,
    )


@router.put("/users/{email}", response_model=UserResponse)
async def update_user(email: str, request: UpdateUserRequest, user: dict = Depends(require_admin)):
    """Update a user in the allowlist."""
    success = update_allowed_user(
        email=email,
        first_name=request.first_name,
        last_name=request.last_name,
        role=request.role,
        scope=request.scope,
        tools=request.tools,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"User {email} not found in allowlist"
        )

    # Set password in Firebase Auth if provided
    if request.password:
        try:
            set_user_password(email, request.password)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"User updated but failed to set password: {e}"
            ) from e

    logger.info(f"Updated user in allowlist: {email}")
    user = get_user_by_email(email)
    return UserResponse(**user)


@router.delete("/users/{email}")
async def remove_user(email: str, user: dict = Depends(require_admin)):
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
    admin = is_user_admin(email) if allowed else False
    user_data = get_user_by_email(email)
    return {
        "email": email,
        "allowed": allowed,
        "is_admin": admin,
        "role": user_data.get("role", "user") if user_data else None,
        "scope": user_data.get("scope", "all") if user_data else None,
        "tools": user_data.get("tools", AVAILABLE_TOOLS) if user_data else None,
    }


@router.get("/settings/gemini", response_model=GeminiSettingsResponse)
async def get_gemini_settings():
    """Get current Gemini AI settings (API key masked)."""
    app_settings = load_app_settings()
    gemini = app_settings.get("gemini", {})

    return GeminiSettingsResponse(
        has_key=bool(gemini.get("api_key")),
        enabled=gemini.get("enabled", False),
        model=gemini.get("model", "gemini-2.5-flash"),
        monthly_budget=gemini.get("monthly_budget", 15.00),
    )


@router.put("/settings/gemini", response_model=GeminiSettingsResponse)
async def update_gemini_settings(request: GeminiSettingsRequest, user: dict = Depends(require_admin)):
    """Update Gemini AI settings including API key."""
    app_settings = load_app_settings()

    gemini = app_settings.get("gemini", {})
    if request.api_key is not None:
        gemini["api_key"] = request.api_key
    gemini["enabled"] = request.enabled
    gemini["model"] = request.model
    gemini["monthly_budget"] = request.monthly_budget
    app_settings["gemini"] = gemini

    save_app_settings(app_settings)

    # Update runtime config
    from app.core.config import settings as runtime_settings
    if request.api_key is not None:
        runtime_settings.gemini_api_key = request.api_key
    runtime_settings.gemini_enabled = request.enabled
    runtime_settings.gemini_model = request.model
    runtime_settings.gemini_monthly_budget = request.monthly_budget

    logger.info("Gemini AI settings updated")

    return GeminiSettingsResponse(
        has_key=bool(gemini.get("api_key")),
        enabled=request.enabled,
        model=request.model,
        monthly_budget=request.monthly_budget,
    )


@router.get("/settings/google-maps", response_model=GoogleMapsSettingsResponse)
async def get_google_maps_settings():
    """Get current Google Maps API settings (key masked)."""
    app_settings = load_app_settings()
    gmaps = app_settings.get("google_maps", {})

    return GoogleMapsSettingsResponse(
        has_key=bool(gmaps.get("api_key")),
        enabled=gmaps.get("enabled", False),
    )


@router.put("/settings/google-maps", response_model=GoogleMapsSettingsResponse)
async def update_google_maps_settings(request: GoogleMapsSettingsRequest, user: dict = Depends(require_admin)):
    """Update Google Maps API settings."""
    app_settings = load_app_settings()

    gmaps = app_settings.get("google_maps", {})
    if request.api_key is not None:
        gmaps["api_key"] = request.api_key
    gmaps["enabled"] = request.enabled
    app_settings["google_maps"] = gmaps

    save_app_settings(app_settings)

    # Update runtime config
    from app.core.config import settings as runtime_settings
    if request.api_key is not None:
        runtime_settings.google_maps_api_key = request.api_key
    runtime_settings.google_maps_enabled = request.enabled

    logger.info("Google Maps API settings updated")

    return GoogleMapsSettingsResponse(
        has_key=bool(gmaps.get("api_key")),
        enabled=request.enabled,
    )


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


@router.get("/profile-image/{user_id}")
async def get_profile_image(user_id: str):
    """
    Serve a profile image from storage (GCS or local).

    This endpoint proxies the image from wherever it's stored,
    avoiding the need for GCS signed URLs (which require special IAM permissions).
    """
    from app.core.config import settings

    # Try each extension
    for ext in ["jpg", "jpeg", "png", "gif"]:
        path = f"{settings.gcs_profiles_folder}/{user_id}/avatar.{ext}"
        content = storage_service.download_file(path)
        if content:
            media_types = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
            }
            return Response(
                content=content,
                media_type=media_types.get(ext, "image/jpeg"),
                headers={"Cache-Control": "public, max-age=3600"},
            )

    raise HTTPException(status_code=404, detail="Profile image not found")
