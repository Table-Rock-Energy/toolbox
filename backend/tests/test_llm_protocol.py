"""Tests for LLM provider protocol, OpenAI provider, JSON parsing, and factory."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.pipeline import ProposedChange, PipelineRequest, PipelineResponse
from app.services.llm.protocol import LLMProvider
from app.services.llm.prompts import CLEANUP_PROMPTS


class TestLLMProtocol:
    """Test that OpenAIProvider satisfies the LLMProvider Protocol."""

    def test_openai_provider_satisfies_protocol(self):
        """OpenAIProvider is a valid LLMProvider (runtime_checkable)."""
        from app.services.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        assert isinstance(provider, LLMProvider)

    @patch("app.services.llm.openai_provider.settings")
    def test_is_available_returns_true_when_ollama(self, mock_settings):
        """is_available() returns True when ai_provider='ollama'."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_settings.ai_provider = "ollama"
        provider = OpenAIProvider()
        assert provider.is_available() is True

    @patch("app.services.llm.openai_provider.settings")
    def test_is_available_returns_false_when_none(self, mock_settings):
        """is_available() returns False when ai_provider='none'."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_settings.ai_provider = "none"
        provider = OpenAIProvider()
        assert provider.is_available() is False


class TestJsonParsing:
    """Test parse_json_response handles various LLM output formats."""

    def test_clean_json(self):
        """parse_json_response extracts from clean JSON string."""
        from app.services.llm.openai_provider import parse_json_response

        text = '{"suggestions": [{"entry_index": 0, "field": "name"}]}'
        result = parse_json_response(text)
        assert result["suggestions"][0]["entry_index"] == 0

    def test_markdown_fenced_json(self):
        """parse_json_response extracts from markdown-fenced JSON."""
        from app.services.llm.openai_provider import parse_json_response

        text = '```json\n{"suggestions": []}\n```'
        result = parse_json_response(text)
        assert result["suggestions"] == []

    def test_preamble_json(self):
        """parse_json_response extracts from preamble + JSON."""
        from app.services.llm.openai_provider import parse_json_response

        text = 'Here are my suggestions:\n{"suggestions": [{"entry_index": 1, "field": "state"}]}'
        result = parse_json_response(text)
        assert result["suggestions"][0]["entry_index"] == 1

    def test_non_json_raises_valueerror(self):
        """parse_json_response raises ValueError on non-JSON text."""
        from app.services.llm.openai_provider import parse_json_response

        with pytest.raises(ValueError):
            parse_json_response("This is just plain text with no JSON.")


class TestProviderFactory:
    """Test get_llm_provider factory routing."""

    def test_factory_returns_openai_when_ollama(self):
        """get_llm_provider returns OpenAIProvider when ai_provider='ollama'."""
        from app.services.llm.openai_provider import OpenAIProvider

        with patch("app.services.llm.settings") as mock_factory_settings, \
             patch("app.services.llm.openai_provider.settings") as mock_provider_settings:
            mock_factory_settings.ai_provider = "ollama"
            mock_provider_settings.ai_provider = "ollama"

            from app.services.llm import get_llm_provider

            provider = get_llm_provider()
            assert provider is not None
            assert isinstance(provider, OpenAIProvider)

    def test_factory_returns_none_when_none(self):
        """get_llm_provider returns None when ai_provider='none'."""
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.ai_provider = "none"

            from app.services.llm import get_llm_provider

            provider = get_llm_provider()
            assert provider is None


class TestOpenAIProviderCleanup:
    """Test OpenAIProvider.cleanup_entries transforms results correctly."""

    @pytest.mark.asyncio
    async def test_cleanup_entries_returns_proposed_changes(self):
        """cleanup_entries() calls AsyncOpenAI and returns list[ProposedChange]."""
        from app.services.llm.openai_provider import OpenAIProvider

        # Mock the AsyncOpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "suggestions": [
                {
                    "entry_index": 0,
                    "field": "name",
                    "current_value": "JOHN SMITH",
                    "suggested_value": "John Smith",
                    "reason": "Convert ALL CAPS to Title Case",
                    "confidence": "high",
                }
            ]
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        provider = OpenAIProvider()
        provider._client = mock_client
        provider._model_verified = True

        with patch("app.services.llm.openai_provider.settings") as mock_settings:
            mock_settings.llm_model = "test-model"
            mock_settings.ai_provider = "ollama"
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


class TestVerifyModel:
    """Test OpenAIProvider.verify_model() model verification."""

    @pytest.mark.asyncio
    async def test_verify_model_success(self):
        """verify_model returns (True, '') when configured model is loaded."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "qwen3.5-9b"}]}

        with patch("app.services.llm.openai_provider.settings") as mock_settings:
            mock_settings.llm_api_base = "http://localhost:11434/v1"
            mock_settings.llm_model = "qwen3.5-9b"

            provider = OpenAIProvider()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client_instance

                valid, error = await provider.verify_model()

        assert valid is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_verify_model_wrong_model(self):
        """verify_model returns (False, ...) when configured model is not available."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "other-model"}]}

        with patch("app.services.llm.openai_provider.settings") as mock_settings:
            mock_settings.llm_api_base = "http://localhost:11434/v1"
            mock_settings.llm_model = "qwen3.5-9b"

            provider = OpenAIProvider()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client_instance

                valid, error = await provider.verify_model()

        assert valid is False
        assert "not found" in error
        assert "other-model" in error

    @pytest.mark.asyncio
    async def test_verify_model_no_models_loaded(self):
        """verify_model returns (False, ...) when no models are loaded."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": []}

        with patch("app.services.llm.openai_provider.settings") as mock_settings:
            mock_settings.llm_api_base = "http://localhost:11434/v1"
            mock_settings.llm_model = "qwen3.5-9b"

            provider = OpenAIProvider()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client_instance

                valid, error = await provider.verify_model()

        assert valid is False
        assert "no models available" in error

    @pytest.mark.asyncio
    async def test_verify_model_connection_error(self):
        """verify_model returns (False, ...) when Ollama is unreachable."""
        import httpx
        from app.services.llm.openai_provider import OpenAIProvider

        with patch("app.services.llm.openai_provider.settings") as mock_settings:
            mock_settings.llm_api_base = "http://localhost:11434/v1"
            mock_settings.llm_model = "qwen3.5-9b"

            provider = OpenAIProvider()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(
                    side_effect=httpx.ConnectError("Connection refused")
                )
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client_instance

                valid, error = await provider.verify_model()

        assert valid is False
        assert "Cannot connect" in error

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_verify_fails(self):
        """cleanup_entries returns [] when verify_model fails."""
        from app.services.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        provider._model_verified = False

        with patch.object(provider, "verify_model", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (False, "Cannot connect to Ollama")

            with patch("app.services.llm.openai_provider.settings") as mock_settings:
                mock_settings.batch_size = 25
                mock_settings.llm_model = "test-model"
                mock_settings.ai_provider = "ollama"
                mock_settings.llm_api_base = "http://localhost:11434/v1"
                mock_settings.llm_api_key = None

                result = await provider.cleanup_entries("extract", [{"name": "test"}])

        assert result == []

    @pytest.mark.asyncio
    async def test_cleanup_caches_verification(self):
        """cleanup_entries calls verify_model only once across multiple calls."""
        from app.services.llm.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"suggestions": []})

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        provider = OpenAIProvider()
        provider._client = mock_client
        provider._model_verified = False

        with patch.object(provider, "verify_model", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (True, "")

            with patch("app.services.llm.openai_provider.settings") as mock_settings:
                mock_settings.batch_size = 25
                mock_settings.llm_model = "test-model"
                mock_settings.ai_provider = "ollama"

                await provider.cleanup_entries("extract", [{"name": "test"}])
                await provider.cleanup_entries("extract", [{"name": "test2"}])

        assert mock_verify.call_count == 1


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


class TestValidationPrompts:
    """Test that TOOL_PROMPTS and REVENUE_VERIFY_PROMPT are in prompts.py."""

    def test_tool_prompts_exist(self):
        """TOOL_PROMPTS dict exists in prompts.py with expected keys."""
        from app.services.llm.prompts import TOOL_PROMPTS

        assert "extract" in TOOL_PROMPTS
        assert "title" in TOOL_PROMPTS
        assert "proration" in TOOL_PROMPTS
        assert "revenue" in TOOL_PROMPTS

    def test_revenue_verify_prompt_exists(self):
        """REVENUE_VERIFY_PROMPT exists in prompts.py."""
        from app.services.llm.prompts import REVENUE_VERIFY_PROMPT

        assert isinstance(REVENUE_VERIFY_PROMPT, str)
        assert len(REVENUE_VERIFY_PROMPT) > 50

    def test_validation_response_schema_exists(self):
        """VALIDATION_RESPONSE_SCHEMA exists in prompts.py."""
        from app.services.llm.prompts import VALIDATION_RESPONSE_SCHEMA

        assert "suggestions" in VALIDATION_RESPONSE_SCHEMA["properties"]
