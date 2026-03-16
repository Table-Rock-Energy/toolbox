"""Protocol class for swappable LLM providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.pipeline import ProposedChange


@runtime_checkable
class LLMProvider(Protocol):
    """Interface for LLM-based cleanup providers.

    Implementations must provide:
    - cleanup_entries: Send entries to LLM for correction suggestions
    - is_available: Check if the provider is configured and usable
    """

    async def cleanup_entries(
        self, tool: str, entries: list[dict],
        *, source_data: list[dict] | None = None,
    ) -> list[ProposedChange]: ...

    def is_available(self) -> bool: ...
