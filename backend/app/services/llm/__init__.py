"""LLM provider abstraction layer for the enrichment pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.llm.protocol import LLMProvider


def get_llm_provider() -> LLMProvider | None:
    """Factory function to get the active LLM provider.

    Returns None if no provider is available (e.g., Gemini not configured).
    """
    from app.services.llm.gemini_provider import GeminiProvider

    provider = GeminiProvider()
    return provider if provider.is_available() else None
