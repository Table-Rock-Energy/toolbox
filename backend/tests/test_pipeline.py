"""Tests for the pipeline API endpoints (cleanup, validate, enrich)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
