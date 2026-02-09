"""Gemini AI service for data validation suggestions."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.ai_validation import (
    AiStatusResponse,
    AiSuggestion,
    AiValidationResult,
    ConfidenceLevel,
)

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)

# Rate limiting constants (Gemini free tier)
MAX_RPM = 10
MAX_RPD = 250
BATCH_SIZE = 25
BATCH_DELAY_SECONDS = 6

# Gemini 2.5 Flash pricing (per 1M tokens)
# Input: $0.15/1M tokens, Output: $0.60/1M tokens (standard pricing)
COST_PER_INPUT_TOKEN = 0.15 / 1_000_000
COST_PER_OUTPUT_TOKEN = 0.60 / 1_000_000

# Singleton client
_client: Client | None = None
_rpm_timestamps: list[float] = []
_daily_count: int = 0
_daily_reset_time: float = 0.0

# Monthly spend tracking
_monthly_spend: float = 0.0
_monthly_reset_time: float = 0.0


def _get_client() -> Client:
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _check_rate_limit() -> tuple[bool, int, int]:
    """Check if we can make a request. Returns (allowed, remaining_minute, remaining_day)."""
    global _daily_count, _daily_reset_time, _monthly_spend, _monthly_reset_time

    now = time.time()

    # Reset daily counter every 24 hours
    if now - _daily_reset_time > 86400:
        _daily_count = 0
        _daily_reset_time = now

    # Reset monthly spend every 30 days
    if now - _monthly_reset_time > 30 * 86400:
        _monthly_spend = 0.0
        _monthly_reset_time = now

    # Clean old minute timestamps
    cutoff = now - 60
    while _rpm_timestamps and _rpm_timestamps[0] < cutoff:
        _rpm_timestamps.pop(0)

    remaining_minute = MAX_RPM - len(_rpm_timestamps)
    remaining_day = MAX_RPD - _daily_count

    # Check monthly budget
    budget_remaining = settings.gemini_monthly_budget - _monthly_spend
    within_budget = budget_remaining > 0

    allowed = remaining_minute > 0 and remaining_day > 0 and within_budget
    return allowed, remaining_minute, remaining_day


def _record_request() -> None:
    """Record a request for rate limiting."""
    global _daily_count
    _rpm_timestamps.append(time.time())
    _daily_count += 1


def _record_spend(input_tokens: int, output_tokens: int) -> None:
    """Record token spend for monthly budget tracking."""
    global _monthly_spend
    cost = (input_tokens * COST_PER_INPUT_TOKEN) + (output_tokens * COST_PER_OUTPUT_TOKEN)
    _monthly_spend += cost
    logger.debug(
        f"AI spend: {cost:.4f} USD ({input_tokens} in, {output_tokens} out). "
        f"Monthly total: ${_monthly_spend:.4f} / ${settings.gemini_monthly_budget:.2f}"
    )


def get_ai_status() -> AiStatusResponse:
    """Get the current status of the AI validation service."""
    if not settings.use_gemini:
        return AiStatusResponse(enabled=False)

    _, remaining_minute, remaining_day = _check_rate_limit()
    budget_remaining = max(0, settings.gemini_monthly_budget - _monthly_spend)
    return AiStatusResponse(
        enabled=True,
        model=settings.gemini_model,
        requests_remaining_minute=remaining_minute,
        requests_remaining_day=remaining_day,
        monthly_budget=settings.gemini_monthly_budget,
        monthly_spend=round(_monthly_spend, 4),
        monthly_budget_remaining=round(budget_remaining, 4),
    )


TOOL_PROMPTS = {
    "extract": """You are a data quality reviewer for oil and gas party extraction data from OCC Exhibit A PDFs.
Review each entry and suggest corrections for:
- Name casing: Convert ALL CAPS names to proper Title Case (e.g., "JOHN SMITH" → "John Smith"). Keep entity abbreviations uppercase (LLC, LP, INC, CO).
- Entity type vs name mismatch: If the name contains "Trust", "Estate", "LLC", "Corp", "Inc", "Foundation" etc. but the entity_type doesn't match, suggest the correct entity_type.
- Address completeness: Flag entries missing city, state, or zip_code when a mailing_address is present.
- State abbreviation: Ensure state is a valid 2-letter US state code.
- ZIP code format: Should be 5 digits or 5+4 format (XXXXX or XXXXX-XXXX).

Only suggest changes where you are confident there is an actual error. Do NOT suggest changes for entries that look correct.""",

    "title": """You are a data quality reviewer for title opinion owner data from Oklahoma county records.
Review each entry and suggest corrections for:
- Name casing: Convert ALL CAPS names to proper Title Case. Keep entity abbreviations uppercase (LLC, LP, INC, CO).
- Entity type accuracy: Check if entity_type matches the name (e.g., name with "Trust" should be entity_type "TRUST", "Estate" should be "ESTATE").
- Duplicate detection: Flag entries with very similar names that may be duplicates (same person, different formatting).
- First/last name parsing: If full_name is present, verify first_name and last_name are correctly split.
- Address completeness: Flag entries with partial addresses.
- State abbreviation: Ensure state is a valid 2-letter US state code.

Only suggest changes where you are confident there is an actual error.""",

    "proration": """You are a data quality reviewer for mineral holder proration data used in NRA calculations with Texas RRC data.
Review each entry and suggest corrections for:
- County spelling: Verify Texas county names are spelled correctly.
- Interest range: Interest values should be between 0 and 1 (decimal format). Flag values that seem unreasonably high or zero.
- Legal description format: Should follow standard Texas format (e.g., "A-123" for abstracts, block/section notation).
- Owner name formatting: Convert ALL CAPS to Title Case. Keep entity abbreviations uppercase.
- RRC lease number: If present, should be numeric.
- Well type: Should be "oil", "gas", or "both" if specified.

Only suggest changes where you are confident there is an actual error.""",

    "revenue": """You are a data quality reviewer for revenue statement data extracted from EnergyLink and Energy Transfer PDFs.
Review each entry and suggest corrections for:
- Product code validity: Common codes include OIL, GAS, NGL, COND. Flag unusual or empty product codes.
- Interest sanity: decimal_interest should be between 0 and 1. Flag values outside this range.
- Financial math: owner_value should approximately equal owner_volume × avg_price. Flag large discrepancies.
- Date consistency: sales_date should be a valid date format (MM/YYYY or similar).
- Net revenue check: owner_net_revenue should approximately equal owner_value - owner_tax_amount - owner_deduct_amount.

Only suggest changes where you are confident there is an actual error.""",
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entry_index": {"type": "integer"},
                    "field": {"type": "string"},
                    "current_value": {"type": "string"},
                    "suggested_value": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "entry_index",
                    "field",
                    "current_value",
                    "suggested_value",
                    "reason",
                    "confidence",
                ],
            },
        }
    },
    "required": ["suggestions"],
}


def _validate_batch_sync(
    client: Client, tool: str, entries: list[dict], batch_offset: int
) -> list[AiSuggestion]:
    """Validate a batch of entries synchronously. Returns suggestions."""
    from google.genai import types

    system_prompt = TOOL_PROMPTS.get(tool, TOOL_PROMPTS["extract"])

    entries_text = json.dumps(
        [{"index": batch_offset + i, **e} for i, e in enumerate(entries)],
        indent=2,
        default=str,
    )

    user_prompt = f"""Review the following {len(entries)} data entries (indices {batch_offset}-{batch_offset + len(entries) - 1}) and provide correction suggestions.

Return a JSON object with a "suggestions" array. Each suggestion must have: entry_index (matching the index field), field, current_value, suggested_value, reason, and confidence (high/medium/low).

If all entries look correct, return {{"suggestions": []}}.

Entries:
{entries_text}"""

    try:
        _record_request()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_json_schema=RESPONSE_SCHEMA,
                temperature=0.1,
            ),
        )

        # Track token spend for monthly budget
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            _record_spend(
                response.usage_metadata.prompt_token_count or 0,
                response.usage_metadata.candidates_token_count or 0,
            )

        data = json.loads(response.text)
        suggestions = []
        for s in data.get("suggestions", []):
            try:
                suggestions.append(
                    AiSuggestion(
                        entry_index=s["entry_index"],
                        field=s["field"],
                        current_value=str(s.get("current_value", "")),
                        suggested_value=str(s.get("suggested_value", "")),
                        reason=s.get("reason", ""),
                        confidence=ConfidenceLevel(
                            s.get("confidence", "medium")
                        ),
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping malformed suggestion: {e}")
                continue

        return suggestions

    except Exception as e:
        logger.error(f"Gemini API error for batch at offset {batch_offset}: {e}")
        # Retry once on failure
        try:
            allowed, _, _ = _check_rate_limit()
            if allowed:
                time.sleep(2)
                _record_request()
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_json_schema=RESPONSE_SCHEMA,
                        temperature=0.1,
                    ),
                )
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    _record_spend(
                        response.usage_metadata.prompt_token_count or 0,
                        response.usage_metadata.candidates_token_count or 0,
                    )
                data = json.loads(response.text)
                return [
                    AiSuggestion(
                        entry_index=s["entry_index"],
                        field=s["field"],
                        current_value=str(s.get("current_value", "")),
                        suggested_value=str(s.get("suggested_value", "")),
                        reason=s.get("reason", ""),
                        confidence=ConfidenceLevel(
                            s.get("confidence", "medium")
                        ),
                    )
                    for s in data.get("suggestions", [])
                ]
        except Exception as retry_err:
            logger.error(f"Gemini retry also failed: {retry_err}")

        return []


async def validate_entries(tool: str, entries: list[dict]) -> AiValidationResult:
    """Validate entries using Gemini AI. Batches entries and returns suggestions."""
    if not settings.use_gemini:
        return AiValidationResult(
            success=False,
            error_message="AI validation is not enabled. Set GEMINI_ENABLED=true and provide GEMINI_API_KEY.",
        )

    client = _get_client()
    all_suggestions: list[AiSuggestion] = []
    total_batches = (len(entries) + BATCH_SIZE - 1) // BATCH_SIZE
    batches_completed = 0

    for batch_idx in range(total_batches):
        # Check rate limit before each batch
        allowed, remaining_minute, remaining_day = _check_rate_limit()
        if not allowed:
            budget_remaining = settings.gemini_monthly_budget - _monthly_spend
            budget_exceeded = budget_remaining <= 0
            reason = "Monthly budget exceeded" if budget_exceeded else "Rate limited"
            logger.warning(
                f"{reason} after {batches_completed} batches. "
                f"RPM remaining: {remaining_minute}, RPD remaining: {remaining_day}, "
                f"Budget remaining: ${budget_remaining:.4f}"
            )
            return AiValidationResult(
                success=True,
                suggestions=all_suggestions,
                summary=f"Partially reviewed ({batches_completed}/{total_batches} batches). {reason}.",
                entries_reviewed=batches_completed * BATCH_SIZE,
                issues_found=len(all_suggestions),
                error_message=f"{reason} after {batches_completed} batches. Try again later.",
            )

        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(entries))
        batch = entries[start:end]

        # Run the sync Gemini call in a thread to avoid blocking the event loop
        batch_suggestions = await asyncio.to_thread(
            _validate_batch_sync, client, tool, batch, start
        )
        all_suggestions.extend(batch_suggestions)
        batches_completed += 1

        # Delay between batches to respect rate limits
        if batch_idx < total_batches - 1:
            await asyncio.sleep(BATCH_DELAY_SECONDS)

    entries_reviewed = len(entries)
    issues_found = len(all_suggestions)

    if issues_found == 0:
        summary = f"Reviewed {entries_reviewed} entries. No issues found."
    else:
        summary = f"Reviewed {entries_reviewed} entries. Found {issues_found} potential issues."

    return AiValidationResult(
        success=True,
        suggestions=all_suggestions,
        summary=summary,
        entries_reviewed=entries_reviewed,
        issues_found=issues_found,
    )
