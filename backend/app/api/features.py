"""Feature status endpoint -- exposes which optional features are configured."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/status")
async def feature_status() -> dict:
    """Return which optional enrichment features are enabled."""
    return {
        "cleanup_enabled": settings.use_ai,
        "validate_enabled": settings.use_google_maps,
        "enrich_enabled": settings.use_enrichment,
    }
