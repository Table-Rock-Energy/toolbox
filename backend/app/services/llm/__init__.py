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
    - "none" (or anything else): Returns None (AI disabled)
    """
    if settings.ai_provider == "lmstudio":
        from app.services.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        return provider if provider.is_available() else None

    return None
