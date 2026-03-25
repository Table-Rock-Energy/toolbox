"""LLM provider abstraction layer for the enrichment pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.llm.protocol import LLMProvider


def get_llm_provider() -> LLMProvider | None:
    """Factory function to get the active LLM provider.

    Routes based on ai_provider config:
    - "lmstudio": Returns OpenAIProvider (OpenAI-compatible local inference)
    - "none": Returns None (AI disabled)

    Falls back to GeminiProvider when ai_provider is not set but Gemini is configured.
    """
    if settings.ai_provider == "lmstudio":
        from app.services.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        return provider if provider.is_available() else None

    if settings.ai_provider == "none":
        return None

    # Legacy fallback: use Gemini if still configured
    from app.services.llm.gemini_provider import GeminiProvider

    provider = GeminiProvider()
    return provider if provider.is_available() else None
