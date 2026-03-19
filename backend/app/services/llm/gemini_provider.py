"""Gemini implementation of the LLMProvider protocol."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.ai_validation import AiSuggestion, ConfidenceLevel
from app.models.pipeline import ProposedChange
from app.services.llm.prompts import CLEANUP_PROMPTS, CLEANUP_RESPONSE_SCHEMA

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)


def _cleanup_batch_sync(
    client: Client, tool: str, entries: list[dict], batch_offset: int,
    source_data: list[dict] | None = None,
) -> list[AiSuggestion]:
    """Run cleanup on a batch of entries synchronously.

    Mirrors _validate_batch_sync from gemini_service.py but uses
    CLEANUP_PROMPTS instead of TOOL_PROMPTS.
    """
    from google.genai import types

    # Reuse rate-limiting infrastructure from gemini_service
    from app.services.gemini_service import (
        _check_rate_limit,
        _record_request,
        _record_spend,
    )

    system_prompt = CLEANUP_PROMPTS.get(tool, CLEANUP_PROMPTS["extract"])

    entries_text = json.dumps(
        [{"index": batch_offset + i, **e} for i, e in enumerate(entries)],
        indent=2,
        default=str,
    )

    user_prompt = (
        f"Clean up the following {len(entries)} data entries "
        f"(indices {batch_offset}-{batch_offset + len(entries) - 1}) "
        f"and provide correction suggestions.\n\n"
        f'Return a JSON object with a "suggestions" array. Each suggestion must have: '
        f"entry_index (matching the index field), field, current_value, suggested_value, "
        f"reason, and confidence (high/medium/low).\n\n"
        f'If all entries look correct, return {{"suggestions": []}}.\n\n'
        f"Entries:\n{entries_text}"
    )

    if source_data is not None:
        source_text = json.dumps(source_data, indent=2, default=str)
        user_prompt += (
            f"\n\nOriginal CSV source data for cross-file comparison:\n{source_text}"
        )

    allowed, _, _ = _check_rate_limit()
    if not allowed:
        logger.warning("Rate limited during cleanup batch at offset %d", batch_offset)
        raise RuntimeError("Gemini rate limit reached. Please wait a minute and try again.")

    _record_request()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=CLEANUP_RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )

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
                    confidence=ConfidenceLevel(s.get("confidence", "medium")),
                )
            )
        except (ValueError, KeyError) as e:
            logger.warning("Skipping malformed cleanup suggestion: %s", e)
            continue

    return suggestions


class GeminiProvider:
    """LLM provider backed by Google Gemini.

    Satisfies the LLMProvider protocol. Uses the existing gemini_service
    infrastructure for rate limiting and client management.
    """

    async def cleanup_entries(
        self, tool: str, entries: list[dict],
        *, source_data: list[dict] | None = None,
    ) -> list[ProposedChange]:
        """Send entries to Gemini for cleanup suggestions.

        Returns a list of ProposedChange objects (source='ai_cleanup', authoritative=False).
        """
        from app.services.gemini_service import _get_client, BATCH_SIZE, BATCH_DELAY_SECONDS

        client = _get_client()
        all_suggestions: list[AiSuggestion] = []
        total_batches = (len(entries) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx in range(total_batches):
            start = batch_idx * BATCH_SIZE
            end = min(start + BATCH_SIZE, len(entries))
            batch = entries[start:end]

            batch_suggestions = await asyncio.to_thread(
                _cleanup_batch_sync, client, tool, batch, start, source_data
            )
            all_suggestions.extend(batch_suggestions)

            # Delay between batches to respect rate limits
            if batch_idx < total_batches - 1:
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        # Transform AiSuggestion -> ProposedChange
        return [
            ProposedChange(
                entry_index=s.entry_index,
                field=s.field,
                current_value=s.current_value,
                proposed_value=s.suggested_value,
                reason=s.reason,
                confidence=s.confidence.value,
                source="ai_cleanup",
                authoritative=False,
            )
            for s in all_suggestions
        ]

    def is_available(self) -> bool:
        """Check if Gemini is configured and enabled."""
        return settings.use_gemini
