"""Tests for LLM provider protocol, Pydantic models, and cleanup prompts."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.pipeline import ProposedChange, PipelineRequest, PipelineResponse
from app.services.llm.protocol import LLMProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.prompts import CLEANUP_PROMPTS
from app.models.ai_validation import AiSuggestion, AiValidationResult, ConfidenceLevel


class TestLLMProtocol:
    """Test that GeminiProvider satisfies the LLMProvider Protocol."""

    def test_gemini_provider_satisfies_protocol(self):
        """GeminiProvider is a valid LLMProvider (runtime_checkable)."""
        provider = GeminiProvider()
        assert isinstance(provider, LLMProvider)

    @patch("app.services.llm.gemini_provider.settings")
    def test_is_available_returns_false_when_disabled(self, mock_settings):
        """is_available() returns False when GEMINI_ENABLED is not set."""
        mock_settings.use_gemini = False
        provider = GeminiProvider()
        assert provider.is_available() is False

    @patch("app.services.llm.gemini_provider.settings")
    def test_is_available_returns_true_when_enabled(self, mock_settings):
        """is_available() returns True when Gemini is enabled."""
        mock_settings.use_gemini = True
        provider = GeminiProvider()
        assert provider.is_available() is True


class TestGeminiProviderCleanup:
    """Test GeminiProvider.cleanup_entries transforms results correctly."""

    @pytest.mark.asyncio
    async def test_cleanup_entries_returns_proposed_changes(self):
        """cleanup_entries() calls gemini infrastructure and returns list[ProposedChange]."""
        canned_suggestions = [
            AiSuggestion(
                entry_index=0,
                field="name",
                current_value="JOHN SMITH",
                suggested_value="John Smith",
                reason="Convert ALL CAPS to Title Case",
                confidence=ConfidenceLevel.HIGH,
            ),
        ]

        provider = GeminiProvider()

        with patch(
            "app.services.llm.gemini_provider.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=canned_suggestions,
        ), patch(
            "app.services.gemini_service._get_client",
            return_value=MagicMock(),
        ):
            result = await provider.cleanup_entries(
                "extract", [{"name": "JOHN SMITH"}]
            )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ProposedChange)
        assert result[0].proposed_value == "John Smith"
        assert result[0].source == "ai_cleanup"
        assert result[0].authoritative is False


class TestPipelineModels:
    """Test Pydantic models for the pipeline API."""

    def test_proposed_change_validates_all_fields(self):
        """ProposedChange model validates with all required fields."""
        change = ProposedChange(
            entry_index=0,
            field="name",
            current_value="JOHN",
            proposed_value="John",
            reason="Title case",
            confidence="high",
            source="ai_cleanup",
            authoritative=False,
        )
        assert change.entry_index == 0
        assert change.source == "ai_cleanup"
        assert change.authoritative is False

    def test_proposed_change_authoritative_default(self):
        """ProposedChange defaults authoritative to False."""
        change = ProposedChange(
            entry_index=0,
            field="name",
            current_value="X",
            proposed_value="Y",
            reason="test",
            confidence="high",
            source="ai_cleanup",
        )
        assert change.authoritative is False

    def test_pipeline_request_accepts_tool_entries_field_mapping(self):
        """PipelineRequest model accepts tool, entries, and field_mapping."""
        req = PipelineRequest(
            tool="extract",
            entries=[{"name": "test"}],
            field_mapping={"street": "mailing_address"},
        )
        assert req.tool == "extract"
        assert len(req.entries) == 1
        assert req.field_mapping["street"] == "mailing_address"

    def test_pipeline_request_default_field_mapping(self):
        """PipelineRequest defaults field_mapping to empty dict."""
        req = PipelineRequest(tool="title", entries=[])
        assert req.field_mapping == {}

    def test_pipeline_response_structure(self):
        """PipelineResponse has success, proposed_changes, error, entries_processed."""
        resp = PipelineResponse(
            success=True,
            proposed_changes=[],
            entries_processed=5,
        )
        assert resp.success is True
        assert resp.proposed_changes == []
        assert resp.entries_processed == 5
        assert resp.error is None


class TestCleanupPrompts:
    """Test cleanup prompt constants."""

    def test_cleanup_prompts_has_all_tool_keys(self):
        """CLEANUP_PROMPTS has keys for extract, title, proration, revenue."""
        assert "extract" in CLEANUP_PROMPTS
        assert "title" in CLEANUP_PROMPTS
        assert "proration" in CLEANUP_PROMPTS
        assert "revenue" in CLEANUP_PROMPTS

    def test_cleanup_prompts_are_nonempty_strings(self):
        """Each cleanup prompt is a non-empty string."""
        for tool, prompt in CLEANUP_PROMPTS.items():
            assert isinstance(prompt, str), f"{tool} prompt is not a string"
            assert len(prompt) > 50, f"{tool} prompt is too short"

    def test_cleanup_prompts_contain_no_guess_instruction(self):
        """Each prompt instructs LLM not to guess missing data."""
        for tool, prompt in CLEANUP_PROMPTS.items():
            lower = prompt.lower()
            assert "do not guess" in lower or "don't guess" in lower, (
                f"{tool} prompt missing 'do not guess' instruction"
            )
