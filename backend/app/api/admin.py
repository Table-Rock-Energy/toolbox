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
    require_auth,
    set_user_password,
)
from app.services.shared.encryption import encrypt_value, decrypt_value
from app.services.storage_service import profile_storage, storage_service

logger = logging.getLogger(__name__)
router = APIRouter()

# App settings file (local cache, source of truth is PostgreSQL)
APP_SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "app_settings.json"

# Fields to encrypt before persistence. Each tuple is (top-level-key, field-name).
_SENSITIVE_FIELDS: list[tuple[str, str]] = [
    ("google_cloud", "api_key"),
    ("google_maps", "api_key"),
    ("pdl", "api_key"),
    ("searchbug", "api_key"),
]


def _encrypt_settings(settings_data: dict) -> dict:
    """Return a copy with sensitive fields encrypted for persistence."""
    import copy
    encrypted = copy.deepcopy(settings_data)
    for section, field in _SENSITIVE_FIELDS:
        value = encrypted.get(section, {}).get(field)
        if value and not value.startswith("enc:"):
            encrypted.setdefault(section, {})[field] = encrypt_value(value)
    return encrypted


def _decrypt_settings(settings_data: dict) -> dict:
    """Return a copy with sensitive fields decrypted for runtime use."""
    import copy
    decrypted = copy.deepcopy(settings_data)
    for section, field in _SENSITIVE_FIELDS:
        value = decrypted.get(section, {}).get(field)
        if value:
            result = decrypt_value(value)
            decrypted.setdefault(section, {})[field] = result
    return decrypted


def load_app_settings() -> dict:
    """Load app settings from local file cache."""
    if APP_SETTINGS_FILE.exists():
        try:
            with open(APP_SETTINGS_FILE, "r") as f:
                raw = json.load(f)
            return _decrypt_settings(raw)
        except Exception as e:
            logger.error(f"Error loading app settings: {e}")
    return {}


def save_app_settings(settings_data: dict) -> None:
    """Save app settings to local file and schedule database persist."""
    encrypted = _encrypt_settings(settings_data)
    APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_SETTINGS_FILE, "w") as f:
        json.dump(encrypted, f, indent=2)

    # Fire-and-forget database persist
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_app_settings_to_db(encrypted))
    except RuntimeError:
        pass  # No event loop running


async def _persist_app_settings_to_db(settings_data: dict) -> None:
    """Async: save app settings to PostgreSQL."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        async with async_session_maker() as session:
            await db_service.set_config_doc(session, "app_settings", settings_data)
            await session.commit()
        logger.info("Persisted app settings to database")
    except Exception as e:
        logger.warning(f"Failed to persist app settings to database: {e}")


async def init_app_settings_from_db() -> None:
    """Load app settings from database on startup. Seeds database if empty."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        async with async_session_maker() as session:
            data = await db_service.get_config_doc(session, "app_settings")
            if data:
                # Remove internal fields before saving locally
                clean = {k: v for k, v in data.items() if not k.startswith("_")}
                # Write encrypted data to local cache (preserve ciphertext on disk)
                APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(APP_SETTINGS_FILE, "w") as f:
                    json.dump(clean, f, indent=2)

                # Decrypt before applying to runtime
                decrypted = _decrypt_settings(clean)
                _apply_settings_to_runtime(decrypted)
                logger.info("Loaded app settings from database")
            else:
                # Seed database from local file
                local = load_app_settings()
                if local:
                    encrypted_local = _encrypt_settings(local)
                    await db_service.set_config_doc(session, "app_settings", encrypted_local)
                    await session.commit()
                    logger.info("Seeded database with local app settings")
    except Exception as e:
        logger.warning(f"Could not load app settings from database: {e}")


def _apply_settings_to_runtime(settings_data: dict) -> None:
    """Apply loaded settings to the runtime config object."""
    from app.core.config import settings as runtime_settings

    # --- Maps/Places API key (stored under "google_cloud" key for backward compat) ---
    gc = settings_data.get("google_cloud", {})
    if gc.get("api_key"):
        runtime_settings.google_api_key = gc["api_key"]
        runtime_settings.google_maps_api_key = gc["api_key"]
    if "maps_enabled" in gc:
        runtime_settings.google_maps_enabled = gc["maps_enabled"]
    if "places_enabled" in gc:
        runtime_settings.places_enabled = gc["places_enabled"]

    # --- AI provider section ---
    ai = settings_data.get("ai", {})
    if ai.get("enabled"):
        runtime_settings.ai_provider = "lmstudio"
    elif "enabled" in ai:
        runtime_settings.ai_provider = "none"
    if "model" in ai:
        runtime_settings.llm_model = ai["model"]

    # Batch config
    bc = settings_data.get("batch_config", {})
    if "batch_size" in bc:
        runtime_settings.batch_size = max(5, min(100, bc["batch_size"]))
    if "max_concurrency" in bc:
        runtime_settings.batch_max_concurrency = max(1, min(5, bc["max_concurrency"]))
    if "max_retries" in bc:
        runtime_settings.batch_max_retries = max(0, min(3, bc["max_retries"]))


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


class ApiSettingsRequest(BaseModel):
    """Request to update unified API settings (AI, Maps, batch config)."""
    api_key: Optional[str] = None
    ai_enabled: bool = False
    ai_model: str = "qwen3.5-35b-a3b"
    maps_enabled: bool = False
    places_enabled: bool = False
    batch_size: int = 25
    batch_max_concurrency: int = 2
    batch_max_retries: int = 1


class ApiSettingsResponse(BaseModel):
    """Response with API settings (key masked)."""
    has_key: bool
    ai_enabled: bool
    ai_model: str
    maps_enabled: bool
    places_enabled: bool
    batch_size: int = 25
    batch_max_concurrency: int = 2
    batch_max_retries: int = 1


class AiSettingsRequest(BaseModel):
    """Request to update AI provider settings."""
    enabled: bool = False
    model: str = "qwen3.5-35b-a3b"


class AiSettingsResponse(BaseModel):
    """Response with AI provider settings."""
    enabled: bool
    model: str


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
async def get_options(user: dict = Depends(require_admin)):
    """Get available roles, scopes, and tools for user management."""
    return OptionsResponse(
        roles=AVAILABLE_ROLES,
        scopes=AVAILABLE_SCOPES,
        tools=AVAILABLE_TOOLS,
    )


@router.get("/users", response_model=AllowlistResponse)
async def list_allowed_users(user: dict = Depends(require_admin)):
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

    # Create user in PostgreSQL and set password
    try:
        from app.core.database import async_session_maker
        from app.models.db_models import User as UserModel
        from app.core.security import hash_password
        from sqlalchemy import select as sa_select

        async with async_session_maker() as session:
            # Check if user already exists in DB
            result = await session.execute(
                sa_select(UserModel).where(UserModel.email == request.email.lower())
            )
            db_user = result.scalar_one_or_none()

            if db_user is None:
                # Create new DB user
                db_user = UserModel(
                    email=request.email.lower(),
                    display_name=f"{request.first_name} {request.last_name}".strip() or None,
                    role=request.role or "user",
                    scope=request.scope,
                    tools=request.tools,
                    is_active=True,
                    added_by="admin",
                )
                session.add(db_user)

            # Set password if provided
            if request.password:
                db_user.password_hash = hash_password(request.password)

            await session.commit()
    except Exception as e:
        logger.warning(f"Added user to allowlist but failed to create DB record: {e}")

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

    # Set password in DB if provided
    if request.password:
        try:
            await set_user_password(email, request.password)
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
        "first_name": user_data.get("first_name") if user_data else None,
        "last_name": user_data.get("last_name") if user_data else None,
    }


@router.get("/settings/ai", response_model=AiSettingsResponse)
async def get_ai_settings(user: dict = Depends(require_admin)):
    """Get current AI provider settings."""
    from app.core.config import settings as runtime_settings

    app_settings = load_app_settings()
    ai = app_settings.get("ai", {})

    return AiSettingsResponse(
        enabled=runtime_settings.use_ai,
        model=ai.get("model", runtime_settings.llm_model),
    )


@router.put("/settings/ai", response_model=AiSettingsResponse)
async def update_ai_settings(request: AiSettingsRequest, user: dict = Depends(require_admin)):
    """Update AI provider settings."""
    app_settings = load_app_settings()

    app_settings["ai"] = {
        "enabled": request.enabled,
        "model": request.model,
    }

    save_app_settings(app_settings)

    # Update runtime config
    from app.core.config import settings as runtime_settings
    runtime_settings.ai_provider = "lmstudio" if request.enabled else "none"
    runtime_settings.llm_model = request.model

    logger.info("AI provider settings updated")

    return AiSettingsResponse(
        enabled=request.enabled,
        model=request.model,
    )


@router.get("/settings/api-config", response_model=ApiSettingsResponse)
async def get_api_config_settings(user: dict = Depends(require_admin)):
    """Get current API settings (AI, Maps, batch config)."""
    from app.core.config import settings as runtime_settings

    app_settings = load_app_settings()
    gc = app_settings.get("google_cloud", {})
    bc = app_settings.get("batch_config", {})

    return ApiSettingsResponse(
        has_key=bool(gc.get("api_key")),
        ai_enabled=runtime_settings.use_ai,
        ai_model=runtime_settings.llm_model,
        maps_enabled=gc.get("maps_enabled", False),
        places_enabled=gc.get("places_enabled", False),
        batch_size=bc.get("batch_size", 25),
        batch_max_concurrency=bc.get("max_concurrency", 2),
        batch_max_retries=bc.get("max_retries", 1),
    )


@router.put("/settings/api-config", response_model=ApiSettingsResponse)
async def update_api_settings(
    request: ApiSettingsRequest,
    user: dict = Depends(require_admin),
):
    """Update API settings (AI, Maps, batch config)."""
    app_settings = load_app_settings()

    gc = app_settings.get("google_cloud", {})
    if request.api_key is not None:
        gc["api_key"] = request.api_key
    gc["maps_enabled"] = request.maps_enabled
    gc["places_enabled"] = request.places_enabled
    app_settings["google_cloud"] = gc

    # AI provider settings
    app_settings["ai"] = {
        "enabled": request.ai_enabled,
        "model": request.ai_model,
    }

    # Persist batch config
    app_settings["batch_config"] = {
        "batch_size": max(5, min(100, request.batch_size)),
        "max_concurrency": max(1, min(5, request.batch_max_concurrency)),
        "max_retries": max(0, min(3, request.batch_max_retries)),
    }

    save_app_settings(app_settings)

    # Update runtime config
    from app.core.config import settings as runtime_settings
    if request.api_key is not None:
        runtime_settings.google_api_key = request.api_key
        runtime_settings.google_maps_api_key = request.api_key
    runtime_settings.ai_provider = "lmstudio" if request.ai_enabled else "none"
    runtime_settings.llm_model = request.ai_model
    runtime_settings.google_maps_enabled = request.maps_enabled
    runtime_settings.places_enabled = request.places_enabled
    runtime_settings.batch_size = max(5, min(100, request.batch_size))
    runtime_settings.batch_max_concurrency = max(1, min(5, request.batch_max_concurrency))
    runtime_settings.batch_max_retries = max(0, min(3, request.batch_max_retries))

    logger.info("API settings updated")

    return ApiSettingsResponse(
        has_key=bool(gc.get("api_key")),
        ai_enabled=request.ai_enabled,
        ai_model=request.ai_model,
        maps_enabled=request.maps_enabled,
        places_enabled=request.places_enabled,
        batch_size=runtime_settings.batch_size,
        batch_max_concurrency=runtime_settings.batch_max_concurrency,
        batch_max_retries=runtime_settings.batch_max_retries,
    )


@router.get("/settings/google-maps", response_model=GoogleMapsSettingsResponse)
async def get_google_maps_settings(user: dict = Depends(require_admin)):
    """Get current Google Maps API settings (key masked).

    Reads from the unified ``google_cloud`` section when present; falls back
    to the legacy ``google_maps`` section for backward compatibility.
    """
    app_settings = load_app_settings()
    gc = app_settings.get("google_cloud", {})
    if gc:
        return GoogleMapsSettingsResponse(
            has_key=bool(gc.get("api_key")),
            enabled=gc.get("maps_enabled", False),
        )

    gmaps = app_settings.get("google_maps", {})
    return GoogleMapsSettingsResponse(
        has_key=bool(gmaps.get("api_key")),
        enabled=gmaps.get("enabled", False),
    )


@router.put("/settings/google-maps", response_model=GoogleMapsSettingsResponse)
async def update_google_maps_settings(request: GoogleMapsSettingsRequest, user: dict = Depends(require_admin)):
    """Update Google Maps API settings.

    Writes into the unified ``google_cloud`` section. The legacy
    ``google_maps`` section is preserved unchanged for backward compatibility.
    """
    app_settings = load_app_settings()

    gc = app_settings.get("google_cloud", {})
    if request.api_key is not None:
        gc["api_key"] = request.api_key
    gc["maps_enabled"] = request.enabled
    app_settings["google_cloud"] = gc

    save_app_settings(app_settings)

    # Update runtime config
    from app.core.config import settings as runtime_settings
    if request.api_key is not None:
        runtime_settings.google_api_key = request.api_key
        runtime_settings.google_maps_api_key = request.api_key
    runtime_settings.google_maps_enabled = request.enabled

    logger.info("Google Maps API settings updated")

    return GoogleMapsSettingsResponse(
        has_key=bool(gc.get("api_key")),
        enabled=request.enabled,
    )


@router.post("/upload-profile-image")
async def upload_profile_image(
    file: Annotated[UploadFile, File(description="Profile image file")],
    user_id: Annotated[str, Form(description="Firebase user ID")],
    user: dict = Depends(require_auth),
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
async def get_profile_image(user_id: str, user: dict = Depends(require_auth)):
    """
    Serve a profile image from storage (GCS or local).

    This endpoint proxies the image from wherever it's stored,
    avoiding the need for GCS signed URLs (which require special IAM permissions).
    """
    from app.core.config import settings

    # Try each extension
    for ext in ["jpg", "jpeg", "png", "gif"]:
        path = f"{settings.storage_profiles_folder}/{user_id}/avatar.{ext}"
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


# --- User Preferences ---

class UserPreferencesRequest(BaseModel):
    """Request to update notification preferences."""
    email_notifications: bool = True
    browser_notifications: bool = False
    job_complete_alerts: bool = True
    weekly_report: bool = True


class UserPreferencesResponse(BaseModel):
    """Response with user notification preferences."""
    email_notifications: bool = True
    browser_notifications: bool = False
    job_complete_alerts: bool = True
    weekly_report: bool = True


@router.get("/preferences/{email}", response_model=UserPreferencesResponse)
async def get_preferences(email: str, user: dict = Depends(require_auth)):
    """Get notification preferences for a user."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        async with async_session_maker() as session:
            prefs = await db_service.get_user_preferences(session, email)
        if prefs:
            return UserPreferencesResponse(
                email_notifications=prefs.get("email_notifications", True),
                browser_notifications=prefs.get("browser_notifications", False),
                job_complete_alerts=prefs.get("job_complete_alerts", True),
                weekly_report=prefs.get("weekly_report", True),
            )
    except Exception as e:
        logger.warning(f"Could not load preferences for {email}: {e}")

    # Return defaults if no saved preferences
    return UserPreferencesResponse()


@router.put("/preferences/{email}", response_model=UserPreferencesResponse)
async def update_preferences(email: str, request: UserPreferencesRequest, user: dict = Depends(require_auth)):
    """Update notification preferences for a user."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        prefs = {
            "email_notifications": request.email_notifications,
            "browser_notifications": request.browser_notifications,
            "job_complete_alerts": request.job_complete_alerts,
            "weekly_report": request.weekly_report,
        }
        async with async_session_maker() as session:
            await db_service.set_user_preferences(session, email, prefs)
            await session.commit()
        logger.info(f"Updated preferences for {email}")
        return UserPreferencesResponse(**prefs)
    except Exception as e:
        logger.warning(f"Failed to save preferences for {email}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save preferences: {str(e)}"
        ) from e
