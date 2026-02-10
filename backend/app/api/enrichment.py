"""API routes for data enrichment (People Data Labs + SearchBug)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_admin, require_auth

from app.models.enrichment import (
    EnrichmentConfigUpdateRequest,
    EnrichmentRequest,
    EnrichmentResponse,
    EnrichmentStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=EnrichmentStatusResponse)
async def enrichment_status() -> EnrichmentStatusResponse:
    """Check enrichment service configuration status."""
    from app.services.enrichment.enrichment_service import get_enrichment_status

    return get_enrichment_status()


@router.post("/config")
async def update_enrichment_config(request: EnrichmentConfigUpdateRequest, user: dict = Depends(require_admin)) -> dict:
    """
    Update enrichment API keys and enabled state.

    Keys are stored in Firestore so they persist across restarts.
    """
    from app.services.enrichment.enrichment_service import (
        get_enrichment_status,
        set_runtime_config,
    )

    set_runtime_config(
        pdl_api_key=request.pdl_api_key,
        searchbug_api_key=request.searchbug_api_key,
        enabled=request.enabled,
    )

    # Persist to Firestore
    try:
        await _save_enrichment_config(request)
    except Exception as e:
        logger.warning(f"Failed to persist enrichment config to Firestore: {e}")

    status = get_enrichment_status()
    logger.info(f"Enrichment config updated: enabled={status.enabled}, pdl={status.pdl_configured}, searchbug={status.searchbug_configured}")

    return {
        "success": True,
        "message": "Enrichment configuration updated",
        "status": status.model_dump(),
    }


@router.get("/config")
async def get_enrichment_config() -> dict:
    """Get current enrichment config (masks API keys)."""
    from app.services.enrichment.enrichment_service import (
        get_pdl_key,
        get_searchbug_key,
        is_enrichment_enabled,
    )

    pdl_key = get_pdl_key()
    sb_key = get_searchbug_key()

    return {
        "enabled": is_enrichment_enabled(),
        "pdl_api_key": _mask_key(pdl_key) if pdl_key else None,
        "searchbug_api_key": _mask_key(sb_key) if sb_key else None,
    }


@router.post("/lookup", response_model=EnrichmentResponse)
async def enrichment_lookup(request: EnrichmentRequest) -> EnrichmentResponse:
    """
    Enrich a list of persons with contact data and public records.

    Each person should have at minimum a `name` field. Optional fields:
    `address`, `city`, `state`, `zip_code`.
    """
    from app.services.enrichment.enrichment_service import enrich_persons

    if not request.persons:
        raise HTTPException(status_code=400, detail="No persons provided")

    if len(request.persons) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 persons per request")

    result = await enrich_persons(request.persons)
    return result


def _mask_key(key: str) -> str:
    """Mask an API key for display, showing only last 4 chars."""
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


async def _save_enrichment_config(request: EnrichmentConfigUpdateRequest) -> None:
    """Persist enrichment config to Firestore."""
    from app.core.config import settings

    if not settings.firestore_enabled:
        return

    try:
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()
        doc_ref = db.collection("app_config").document("enrichment")

        from app.services.shared.encryption import encrypt_value

        update_data: dict = {}
        if request.pdl_api_key is not None:
            update_data["pdl_api_key"] = encrypt_value(request.pdl_api_key)
        if request.searchbug_api_key is not None:
            update_data["searchbug_api_key"] = encrypt_value(request.searchbug_api_key)
        if request.enabled is not None:
            update_data["enabled"] = request.enabled

        if update_data:
            from datetime import datetime, timezone
            update_data["updated_at"] = datetime.now(timezone.utc)
            await doc_ref.set(update_data, merge=True)
            logger.info("Enrichment config persisted to Firestore")
    except Exception as e:
        logger.warning(f"Could not persist enrichment config: {e}")


async def load_enrichment_config_from_firestore() -> None:
    """Load enrichment config from Firestore on startup."""
    from app.core.config import settings

    if not settings.firestore_enabled:
        return

    try:
        from app.services.enrichment.enrichment_service import set_runtime_config
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()
        doc = await db.collection("app_config").document("enrichment").get()

        if doc.exists:
            from app.services.shared.encryption import decrypt_value

            data = doc.to_dict()
            pdl_key = data.get("pdl_api_key")
            sb_key = data.get("searchbug_api_key")
            set_runtime_config(
                pdl_api_key=decrypt_value(pdl_key) if pdl_key else None,
                searchbug_api_key=decrypt_value(sb_key) if sb_key else None,
                enabled=data.get("enabled"),
            )
            logger.info("Loaded enrichment config from Firestore")
    except Exception as e:
        logger.warning(f"Could not load enrichment config from Firestore: {e}")
