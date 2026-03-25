"""OpenAI-compatible LLM provider for LM Studio."""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, TYPE_CHECKING

from app.core.config import settings
from app.models.ai_validation import AiSuggestion, AiValidationResult, ConfidenceLevel
from app.models.pipeline import ProposedChange
from app.services.llm.prompts import (
    CLEANUP_PROMPTS,
    TOOL_PROMPTS,
    REVENUE_VERIFY_PROMPT,
    VALIDATION_RESPONSE_SCHEMA,
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response text.

    Handles three common output patterns from local LLMs:
    1. Clean JSON string
    2. Markdown-fenced JSON (```json ... ```)
    3. Preamble text followed by JSON object

    Raises ValueError if no valid JSON found.
    """
    # Try direct JSON parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try extracting first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


class OpenAIProvider:
    """LLM provider backed by AsyncOpenAI client (LM Studio compatible).

    Satisfies the LLMProvider protocol. Uses the openai SDK configured
    to point at a local LM Studio server.
    """

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy-initialize the AsyncOpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=settings.llm_api_base,
                api_key=settings.llm_api_key or "not-needed",
            )
        return self._client

    def is_available(self) -> bool:
        """Check if the OpenAI-compatible provider is configured."""
        return settings.ai_provider == "lmstudio"

    async def cleanup_entries(
        self,
        tool: str,
        entries: list[dict],
        *,
        source_data: list[dict] | None = None,
        disconnect_check: Callable[[], bool] | None = None,
    ) -> list[ProposedChange]:
        """Send entries to LLM for cleanup suggestions.

        Batches entries and calls the OpenAI-compatible API for each batch.
        No rate limiting needed for local inference.

        Returns a list of ProposedChange objects (source='ai_cleanup', authoritative=False).
        """
        batch_size = getattr(settings, "batch_size", 25)
        client = self._get_client()
        total_batches = (len(entries) + batch_size - 1) // batch_size
        all_suggestions: list[AiSuggestion] = []

        system_prompt = CLEANUP_PROMPTS.get(tool, CLEANUP_PROMPTS["extract"])

        for batch_idx in range(total_batches):
            # Check disconnect before each batch
            if disconnect_check and disconnect_check():
                logger.warning("Client disconnected, skipping batch %d", batch_idx)
                break

            start = batch_idx * batch_size
            batch = entries[start : start + batch_size]

            entries_text = json.dumps(
                [{"index": start + i, **e} for i, e in enumerate(batch)],
                indent=2,
                default=str,
            )

            user_prompt = (
                f"Clean up the following {len(batch)} data entries "
                f"(indices {start}-{start + len(batch) - 1}) "
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

            try:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                )

                content = response.choices[0].message.content or ""
                data = parse_json_response(content)

                for s in data.get("suggestions", []):
                    try:
                        all_suggestions.append(
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
                        logger.warning("Skipping malformed cleanup suggestion: %s", e)
                        continue

            except Exception as e:
                logger.error("LLM cleanup error for batch %d: %s", batch_idx, e)
                continue

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

    async def validate_entries(
        self, tool: str, entries: list[dict]
    ) -> AiValidationResult:
        """Validate entries using the OpenAI-compatible API.

        Uses TOOL_PROMPTS (validation prompts) from prompts.py.
        Replaces gemini_service.validate_entries().
        """
        if not self.is_available():
            return AiValidationResult(
                success=False,
                error_message="AI validation is not enabled. Set AI_PROVIDER=lmstudio.",
            )

        batch_size = getattr(settings, "batch_size", 25)
        client = self._get_client()
        total_batches = (len(entries) + batch_size - 1) // batch_size
        all_suggestions: list[AiSuggestion] = []

        system_prompt = TOOL_PROMPTS.get(tool, TOOL_PROMPTS["extract"])

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            batch = entries[start : start + batch_size]

            entries_text = json.dumps(
                [{"index": start + i, **e} for i, e in enumerate(batch)],
                indent=2,
                default=str,
            )

            user_prompt = (
                f"Review the following {len(batch)} data entries "
                f"(indices {start}-{start + len(batch) - 1}) "
                f"and provide correction suggestions.\n\n"
                f'Return a JSON object with a "suggestions" array. Each suggestion must have: '
                f"entry_index (matching the index field), field, current_value, suggested_value, "
                f"reason, and confidence (high/medium/low).\n\n"
                f'If all entries look correct, return {{"suggestions": []}}.\n\n'
                f"Entries:\n{entries_text}"
            )

            try:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                )

                content = response.choices[0].message.content or ""
                data = parse_json_response(content)

                for s in data.get("suggestions", []):
                    try:
                        all_suggestions.append(
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
                        logger.warning("Skipping malformed validation suggestion: %s", e)
                        continue

            except Exception as e:
                logger.error("LLM validation error for batch %d: %s", batch_idx, e)
                continue

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

    async def verify_revenue_entries(
        self,
        entries: list[dict],
        context: dict | None = None,
    ) -> AiValidationResult:
        """Verify revenue entries using the revenue-specific prompt.

        Replaces gemini_service.verify_revenue_entries().
        """
        if not self.is_available():
            return AiValidationResult(
                success=False,
                error_message="AI validation is not enabled.",
            )

        # Build context string
        context_str = ""
        if context:
            parts = []
            for key in ("payor", "operator_name", "filename"):
                if context.get(key):
                    parts.append(f"{key}: {context[key]}")
            if parts:
                context_str = f"\n\nStatement context: {', '.join(parts)}"

        batch_size = getattr(settings, "batch_size", 25)
        client = self._get_client()
        total_batches = (len(entries) + batch_size - 1) // batch_size
        all_suggestions: list[AiSuggestion] = []

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            batch = entries[start : start + batch_size]

            entries_text = json.dumps(
                [{"index": start + i, **e} for i, e in enumerate(batch)],
                indent=2,
                default=str,
            )

            user_prompt = (
                f"Verify the following {len(batch)} revenue rows "
                f"(indices {start}-{start + len(batch) - 1}).{context_str}\n\n"
                f'Return a JSON object with a "suggestions" array. Each suggestion must have: '
                f"entry_index, field, current_value, suggested_value, reason, confidence.\n\n"
                f'If all entries look correct, return {{"suggestions": []}}.\n\n'
                f"Entries:\n{entries_text}"
            )

            try:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": REVENUE_VERIFY_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                )

                content = response.choices[0].message.content or ""
                data = parse_json_response(content)

                for s in data.get("suggestions", []):
                    try:
                        all_suggestions.append(
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
                        logger.warning(
                            "Skipping malformed revenue suggestion: %s", e
                        )
                        continue

            except Exception as e:
                logger.error(
                    "LLM revenue verification error for batch %d: %s", batch_idx, e
                )
                continue

        return AiValidationResult(
            success=True,
            suggestions=all_suggestions,
            summary=f"Verified {len(entries)} revenue rows. Found {len(all_suggestions)} issues.",
            entries_reviewed=len(entries),
            issues_found=len(all_suggestions),
        )
