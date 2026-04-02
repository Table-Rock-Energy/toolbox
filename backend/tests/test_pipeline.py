"""Tests for the pipeline API endpoints (cleanup, validate, enrich)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.models.pipeline import ProposedChange


class TestPipelineCleanup:
    """Test POST /api/pipeline/cleanup endpoint."""

    @pytest.mark.asyncio
    async def test_cleanup_returns_proposed_changes(self, authenticated_client):
        """POST /api/pipeline/cleanup with valid entries returns ProposedChange list."""
        mock_changes = [
            ProposedChange(
                entry_index=0,
                field="name",
                current_value="JOHN SMITH",
                proposed_value="John Smith",
                reason="Title case",
                confidence="high",
                source="ai_cleanup",
                authoritative=False,
            ),
        ]

        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=mock_changes)
        mock_provider.is_available.return_value = True

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={
                    "tool": "extract",
                    "entries": [{"name": "JOHN SMITH"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["proposed_changes"]) == 1
        assert data["proposed_changes"][0]["source"] == "ai_cleanup"
        assert data["proposed_changes"][0]["authoritative"] is False
        assert data["entries_processed"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_returns_error_when_unavailable(self, authenticated_client):
        """POST /api/pipeline/cleanup returns error when LLM provider unavailable."""
        with patch("app.api.pipeline.get_llm_provider", return_value=None):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={
                    "tool": "extract",
                    "entries": [{"name": "test"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not configured" in data["error"].lower() or "not available" in data["error"].lower()


class TestPipelineValidate:
    """Test POST /api/pipeline/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_returns_proposed_changes(self, authenticated_client):
        """POST /api/pipeline/validate returns ProposedChange list with authoritative=true."""
        from app.services.address_validation_service import AddressValidationResult

        mock_result = AddressValidationResult(
            original_street="123 Main St",
            original_city="Springfield",
            original_state="IL",
            original_zip="62701",
            validated_street="123 N Main St",
            validated_city="Springfield",
            validated_state="IL",
            validated_zip="62701",
            confidence="high",
            changed=True,
            changes=["Street: '123 Main St' -> '123 N Main St'"],
        )

        with patch(
            "app.api.pipeline.settings"
        ) as mock_settings, patch(
            "app.api.pipeline.validate_address", return_value=mock_result
        ):
            mock_settings.use_google_maps = True

            response = await authenticated_client.post(
                "/api/pipeline/validate",
                json={
                    "tool": "extract",
                    "entries": [
                        {
                            "mailing_address": "123 Main St",
                            "city": "Springfield",
                            "state": "IL",
                            "zip_code": "62701",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["proposed_changes"]) >= 1
        # Find the street change
        street_change = next(
            (c for c in data["proposed_changes"] if c["field"] == "mailing_address"),
            None,
        )
        assert street_change is not None
        assert street_change["authoritative"] is True
        assert street_change["source"] == "google_maps"

    @pytest.mark.asyncio
    async def test_validate_uses_field_mapping(self, authenticated_client):
        """POST /api/pipeline/validate uses field_mapping from request."""
        from app.services.address_validation_service import AddressValidationResult

        mock_result = AddressValidationResult(
            original_street="456 Oak Ave",
            original_city="Austin",
            original_state="TX",
            original_zip="78701",
            validated_street="456 Oak Ave",
            validated_city="Austin",
            validated_state="TX",
            validated_zip="78701",
            confidence="high",
            changed=False,
            changes=[],
        )

        with patch(
            "app.api.pipeline.settings"
        ) as mock_settings, patch(
            "app.api.pipeline.validate_address", return_value=mock_result
        ) as mock_validate:
            mock_settings.use_google_maps = True

            response = await authenticated_client.post(
                "/api/pipeline/validate",
                json={
                    "tool": "title",
                    "entries": [
                        {
                            "street_addr": "456 Oak Ave",
                            "town": "Austin",
                            "st": "TX",
                            "postal": "78701",
                        }
                    ],
                    "field_mapping": {
                        "street": "street_addr",
                        "city": "town",
                        "state": "st",
                        "zip": "postal",
                    },
                },
            )

        assert response.status_code == 200
        # Verify validate_address was called with correct field values
        mock_validate.assert_called_once()
        call_kwargs = mock_validate.call_args
        assert call_kwargs.kwargs.get("street") == "456 Oak Ave" or call_kwargs[1].get("street") == "456 Oak Ave"

    @pytest.mark.asyncio
    async def test_validate_revenue_returns_empty(self, authenticated_client):
        """POST /api/pipeline/validate for revenue tool returns empty changes (no address fields)."""
        with patch("app.api.pipeline.settings") as mock_settings:
            mock_settings.use_google_maps = True

            response = await authenticated_client.post(
                "/api/pipeline/validate",
                json={
                    "tool": "revenue",
                    "entries": [{"product_code": "OIL"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["proposed_changes"] == []


class TestPipelineEnrich:
    """Test POST /api/pipeline/enrich endpoint."""

    @pytest.mark.asyncio
    async def test_enrich_returns_proposed_changes(self, authenticated_client):
        """POST /api/pipeline/enrich returns ProposedChange list for phone/email."""
        from app.models.enrichment import EnrichedPerson, EnrichmentResponse, PhoneNumber, PublicRecordFlags

        mock_response = EnrichmentResponse(
            success=True,
            results=[
                EnrichedPerson(
                    original_name="John Smith",
                    phones=[PhoneNumber(number="555-123-4567", type="mobile")],
                    emails=["john@example.com"],
                    enrichment_sources=["peopledatalabs"],
                    public_records=PublicRecordFlags(),
                ),
            ],
            total_requested=1,
            total_enriched=1,
        )

        with patch(
            "app.api.pipeline.is_enrichment_enabled", return_value=True
        ), patch(
            "app.api.pipeline.enrich_persons",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await authenticated_client.post(
                "/api/pipeline/enrich",
                json={
                    "tool": "extract",
                    "entries": [
                        {
                            "name": "John Smith",
                            "mailing_address": "123 Main St",
                            "city": "Austin",
                            "state": "TX",
                            "zip_code": "78701",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["proposed_changes"]) >= 1
        # Check phone change
        phone_change = next(
            (c for c in data["proposed_changes"] if c["field"] == "phone"), None
        )
        assert phone_change is not None
        assert phone_change["authoritative"] is False

    @pytest.mark.asyncio
    async def test_enrich_returns_error_when_disabled(self, authenticated_client):
        """POST /api/pipeline/enrich returns error when enrichment not enabled."""
        with patch(
            "app.api.pipeline.is_enrichment_enabled", return_value=False
        ):
            response = await authenticated_client.post(
                "/api/pipeline/enrich",
                json={
                    "tool": "extract",
                    "entries": [{"name": "John Smith"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not enabled" in data["error"].lower() or "not configured" in data["error"].lower()


class TestPipelineRequestModel:
    """Test PipelineRequest model extensions."""

    def test_pipeline_request_accepts_source_data(self):
        """PipelineRequest accepts source_data=None by default (existing calls still work)."""
        from app.models.pipeline import PipelineRequest

        # Without source_data (backward compatible)
        req = PipelineRequest(tool="extract", entries=[{"name": "Test"}])
        assert req.source_data is None

        # With source_data
        csv_rows = [{"entry_number": "1", "name": "Test"}]
        req2 = PipelineRequest(
            tool="ecf", entries=[{"name": "Test"}], source_data=csv_rows
        )
        assert req2.source_data == csv_rows

    def test_pipeline_request_accepts_ecf_tool(self):
        """PipelineRequest accepts tool='ecf'."""
        from app.models.pipeline import PipelineRequest

        req = PipelineRequest(tool="ecf", entries=[])
        assert req.tool == "ecf"


class TestPipelineMedianInjection:
    """Test revenue median injection and ECF source_data passthrough."""

    @pytest.mark.asyncio
    async def test_ecf_cleanup_passes_source_data(self, authenticated_client):
        """POST /api/pipeline/cleanup with tool='ecf' passes source_data to provider."""
        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=[])
        mock_provider.is_available.return_value = True

        csv_rows = [{"entry_number": "1", "name": "Test User"}]

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={
                    "tool": "ecf",
                    "entries": [{"name": "Test User", "entry_number": "1"}],
                    "source_data": csv_rows,
                },
            )

        assert response.status_code == 200
        # Verify source_data was passed to cleanup_entries
        mock_provider.cleanup_entries.assert_called_once()
        call_kwargs = mock_provider.cleanup_entries.call_args
        assert call_kwargs.kwargs.get("source_data") == csv_rows

    @pytest.mark.asyncio
    async def test_revenue_injects_median(self, authenticated_client):
        """POST /api/pipeline/cleanup with tool='revenue' injects _batch_median_value."""
        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=[])
        mock_provider.is_available.return_value = True

        entries = [
            {"owner_value": "100.00"},
            {"owner_value": "200.00"},
            {"owner_value": "150.00"},
        ]

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={"tool": "revenue", "entries": entries},
            )

        assert response.status_code == 200
        # Check that entries passed to provider had median injected
        call_args = mock_provider.cleanup_entries.call_args
        passed_entries = call_args[0][1]  # positional arg: entries
        assert "_batch_median_value" in passed_entries[0]
        assert "_outlier_threshold" in passed_entries[0]
        assert passed_entries[0]["_batch_median_value"] == 150.0
        assert passed_entries[0]["_outlier_threshold"] == 450.0

    @pytest.mark.asyncio
    async def test_revenue_skips_median_when_few_values(self, authenticated_client):
        """POST /api/pipeline/cleanup with < 3 revenue entries skips median injection."""
        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=[])
        mock_provider.is_available.return_value = True

        entries = [
            {"owner_value": "100.00"},
            {"owner_value": "200.00"},
        ]

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={"tool": "revenue", "entries": entries},
            )

        assert response.status_code == 200
        call_args = mock_provider.cleanup_entries.call_args
        passed_entries = call_args[0][1]
        assert "_batch_median_value" not in passed_entries[0]

    @pytest.mark.asyncio
    async def test_extract_does_not_inject_median(self, authenticated_client):
        """POST /api/pipeline/cleanup with tool='extract' does NOT inject median metadata."""
        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=[])
        mock_provider.is_available.return_value = True

        entries = [
            {"name": "A", "owner_value": "100.00"},
            {"name": "B", "owner_value": "200.00"},
            {"name": "C", "owner_value": "150.00"},
        ]

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={"tool": "extract", "entries": entries},
            )

        assert response.status_code == 200
        call_args = mock_provider.cleanup_entries.call_args
        passed_entries = call_args[0][1]
        assert "_batch_median_value" not in passed_entries[0]


class TestBatchConfig:
    """Test batch configuration fields, persistence, and thread-safe rate limiting."""

    def test_settings_has_batch_fields(self):
        """Settings class has batch_size, batch_max_concurrency, batch_max_retries with defaults."""
        from app.core.config import Settings

        s = Settings()
        assert s.batch_size == 25
        assert s.batch_max_concurrency == 2
        assert s.batch_max_retries == 1

    def test_apply_settings_with_batch_config(self):
        """_apply_settings_to_runtime applies batch_config values to runtime settings."""
        from app.api.admin import _apply_settings_to_runtime
        from app.core.config import settings as runtime_settings

        original_batch_size = runtime_settings.batch_size
        original_concurrency = runtime_settings.batch_max_concurrency
        original_retries = runtime_settings.batch_max_retries

        try:
            _apply_settings_to_runtime({
                "batch_config": {
                    "batch_size": 50,
                    "max_concurrency": 3,
                    "max_retries": 2,
                }
            })
            assert runtime_settings.batch_size == 50
            assert runtime_settings.batch_max_concurrency == 3
            assert runtime_settings.batch_max_retries == 2
        finally:
            runtime_settings.batch_size = original_batch_size
            runtime_settings.batch_max_concurrency = original_concurrency
            runtime_settings.batch_max_retries = original_retries

    def test_apply_settings_without_batch_config_keeps_defaults(self):
        """_apply_settings_to_runtime without batch_config leaves defaults unchanged."""
        from app.api.admin import _apply_settings_to_runtime
        from app.core.config import settings as runtime_settings

        original_batch_size = runtime_settings.batch_size

        _apply_settings_to_runtime({})
        assert runtime_settings.batch_size == original_batch_size

    def test_batch_config_clamping(self):
        """Out-of-range batch_config values are clamped."""
        from app.api.admin import _apply_settings_to_runtime
        from app.core.config import settings as runtime_settings

        original_batch_size = runtime_settings.batch_size
        original_concurrency = runtime_settings.batch_max_concurrency
        original_retries = runtime_settings.batch_max_retries

        try:
            _apply_settings_to_runtime({
                "batch_config": {
                    "batch_size": 200,
                    "max_concurrency": 10,
                    "max_retries": 5,
                }
            })
            assert runtime_settings.batch_size == 100
            assert runtime_settings.batch_max_concurrency == 5
            assert runtime_settings.batch_max_retries == 3

            _apply_settings_to_runtime({
                "batch_config": {
                    "batch_size": 1,
                    "max_concurrency": 0,
                    "max_retries": -1,
                }
            })
            assert runtime_settings.batch_size == 5
            assert runtime_settings.batch_max_concurrency == 1
            assert runtime_settings.batch_max_retries == 0
        finally:
            runtime_settings.batch_size = original_batch_size
            runtime_settings.batch_max_concurrency = original_concurrency
            runtime_settings.batch_max_retries = original_retries

    def test_api_settings_response_has_batch_fields(self):
        """ApiSettingsResponse model accepts batch config fields."""
        from app.api.admin import ApiSettingsResponse

        resp = ApiSettingsResponse(
            has_key=True,
            ai_enabled=True,
            ai_model="qwen3.5-9b",
            maps_enabled=False,
            places_enabled=False,
            batch_size=50,
            batch_max_concurrency=3,
            batch_max_retries=2,
        )
        assert resp.batch_size == 50
        assert resp.batch_max_concurrency == 3
        assert resp.batch_max_retries == 2


class TestDisconnectDetection:
    """Test disconnect detection in pipeline cleanup."""

    def test_protocol_includes_disconnect_check(self):
        """LLMProvider protocol includes disconnect_check parameter."""
        import inspect
        from app.services.llm.protocol import LLMProvider

        sig = inspect.signature(LLMProvider.cleanup_entries)
        assert "disconnect_check" in sig.parameters

    @pytest.mark.asyncio
    async def test_pipeline_endpoint_accepts_request_and_body(self, authenticated_client):
        """pipeline_cleanup endpoint accepts Request + PipelineRequest parameters."""
        mock_provider = AsyncMock()
        mock_provider.cleanup_entries = AsyncMock(return_value=[])
        mock_provider.is_available.return_value = True

        with patch(
            "app.api.pipeline.get_llm_provider", return_value=mock_provider
        ):
            response = await authenticated_client.post(
                "/api/pipeline/cleanup",
                json={
                    "tool": "extract",
                    "entries": [{"name": "JOHN SMITH"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify disconnect_check was passed
        call_kwargs = mock_provider.cleanup_entries.call_args
        assert "disconnect_check" in call_kwargs.kwargs


class TestPipelineAuth:
    """Test that pipeline endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_cleanup_requires_auth(self, unauthenticated_client):
        """POST /api/pipeline/cleanup without auth returns 401/403."""
        response = await unauthenticated_client.post(
            "/api/pipeline/cleanup",
            json={"tool": "extract", "entries": []},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_validate_requires_auth(self, unauthenticated_client):
        """POST /api/pipeline/validate without auth returns 401/403."""
        response = await unauthenticated_client.post(
            "/api/pipeline/validate",
            json={"tool": "extract", "entries": []},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_enrich_requires_auth(self, unauthenticated_client):
        """POST /api/pipeline/enrich without auth returns 401/403."""
        response = await unauthenticated_client.post(
            "/api/pipeline/enrich",
            json={"tool": "extract", "entries": []},
        )
        assert response.status_code in (401, 403)
