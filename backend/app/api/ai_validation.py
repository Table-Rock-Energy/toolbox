"""API routes for AI-powered data validation."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models.ai_validation import (
    AiStatusResponse,
    AiValidationRequest,
    AiValidationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=AiStatusResponse)
async def ai_status() -> AiStatusResponse:
    """Check if AI validation is enabled and return rate limit info."""
    from app.services.gemini_service import get_ai_status

    return get_ai_status()


@router.post("/validate", response_model=AiValidationResult)
async def ai_validate(request: AiValidationRequest) -> AiValidationResult:
    """Validate entries using Gemini AI and return suggestions."""
    valid_tools = {"extract", "title", "proration", "revenue"}
    if request.tool not in valid_tools:
        return AiValidationResult(
            success=False,
            error_message=f"Invalid tool: {request.tool}. Must be one of: {', '.join(valid_tools)}",
        )

    if len(request.entries) == 0:
        return AiValidationResult(
            success=False,
            error_message="No entries to validate.",
        )

    if len(request.entries) > 500:
        return AiValidationResult(
            success=False,
            error_message="Too many entries. Maximum is 500 per request.",
        )

    try:
        from app.services.gemini_service import validate_entries

        result = await validate_entries(request.tool, request.entries)
        return result
    except Exception as e:
        logger.exception(f"AI validation error: {e}")
        return AiValidationResult(
            success=False,
            error_message=f"AI validation failed: {str(e)}",
        )
