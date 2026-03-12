"""Tests for the auto_enrich post-processing pipeline."""

from __future__ import annotations

import pytest

from app.models.ai_validation import AutoCorrection, ConfidenceLevel, PostProcessResult
from app.services.data_enrichment_pipeline import (
    _calculate_net_revenue,
    _fix_entity_type,
    _fix_name_casing,
    _infer_product_code,
    _propagate_statement_fields,
)


class TestNameCasing:
    """Tests for _fix_name_casing programmatic fix."""

    def test_all_caps_to_title_case(self):
        entries = [{"primary_name": "JOHN SMITH", "first_name": "JOHN", "last_name": "SMITH"}]
        corrections = _fix_name_casing(entries, ["primary_name", "first_name", "last_name"])

        assert len(corrections) == 3
        assert entries[0]["primary_name"] == "John Smith"
        assert entries[0]["first_name"] == "John"
        assert entries[0]["last_name"] == "Smith"

    def test_preserves_llc_lp_inc(self):
        entries = [{"primary_name": "SMITH ENERGY LLC"}]
        corrections = _fix_name_casing(entries, ["primary_name"])

        assert len(corrections) == 1
        assert entries[0]["primary_name"] == "Smith Energy LLC"

    def test_preserves_roman_numerals(self):
        entries = [{"primary_name": "JOHN SMITH III"}]
        _fix_name_casing(entries, ["primary_name"])

        assert entries[0]["primary_name"] == "John Smith III"

    def test_skips_already_title_case(self):
        entries = [{"primary_name": "John Smith"}]
        corrections = _fix_name_casing(entries, ["primary_name"])

        assert len(corrections) == 0
        assert entries[0]["primary_name"] == "John Smith"

    def test_skips_empty_fields(self):
        entries = [{"primary_name": "", "first_name": None}]
        corrections = _fix_name_casing(entries, ["primary_name", "first_name"])

        assert len(corrections) == 0

    def test_preserves_jr_sr(self):
        entries = [{"primary_name": "JAMES WILSON JR"}]
        _fix_name_casing(entries, ["primary_name"])

        assert entries[0]["primary_name"] == "James Wilson JR"

    def test_correction_metadata(self):
        entries = [{"owner": "MARY JONES"}]
        corrections = _fix_name_casing(entries, ["owner"])

        assert len(corrections) == 1
        c = corrections[0]
        assert c.entry_index == 0
        assert c.field == "owner"
        assert c.original_value == "MARY JONES"
        assert c.corrected_value == "Mary Jones"
        assert c.source == "programmatic"
        assert c.confidence == ConfidenceLevel.HIGH


class TestEntityType:
    """Tests for _fix_entity_type programmatic fix."""

    def test_detects_trust_from_name(self):
        entries = [{"full_name": "John Smith Family Trust", "entity_type": "INDIVIDUAL"}]
        corrections = _fix_entity_type(entries, "full_name", "entity_type")

        assert len(corrections) == 1
        assert entries[0]["entity_type"] == "TRUST"

    def test_detects_llc_from_name(self):
        entries = [{"full_name": "Smith Energy LLC", "entity_type": "INDIVIDUAL"}]
        corrections = _fix_entity_type(entries, "full_name", "entity_type")

        assert len(corrections) == 1
        assert entries[0]["entity_type"] == "CORPORATION"

    def test_skips_correct_individual(self):
        entries = [{"full_name": "John Smith", "entity_type": "INDIVIDUAL"}]
        corrections = _fix_entity_type(entries, "full_name", "entity_type")

        # Individual detected as Individual — no change
        assert len(corrections) == 0

    def test_skips_empty_name(self):
        entries = [{"full_name": "", "entity_type": "INDIVIDUAL"}]
        corrections = _fix_entity_type(entries, "full_name", "entity_type")

        assert len(corrections) == 0


class TestProductCodeInference:
    """Tests for _infer_product_code programmatic fix."""

    def test_infers_oil_from_description(self):
        entries = [{"product_code": "", "product_description": "Crude Oil"}]
        corrections = _infer_product_code(entries)

        assert len(corrections) == 1
        assert entries[0]["product_code"] == "OIL"

    def test_infers_gas_from_description(self):
        entries = [{"product_code": None, "product_description": "Natural Gas"}]
        corrections = _infer_product_code(entries)

        assert len(corrections) == 1
        assert entries[0]["product_code"] == "GAS"

    def test_infers_ngl_from_description(self):
        entries = [{"product_code": "", "product_description": "NGL Plant Products"}]
        corrections = _infer_product_code(entries)

        assert len(corrections) == 1
        assert entries[0]["product_code"] == "NGL"

    def test_skips_when_code_exists(self):
        entries = [{"product_code": "OIL", "product_description": "Crude Oil"}]
        corrections = _infer_product_code(entries)

        assert len(corrections) == 0

    def test_skips_empty_description(self):
        entries = [{"product_code": "", "product_description": ""}]
        corrections = _infer_product_code(entries)

        assert len(corrections) == 0


class TestNetRevenueCalculation:
    """Tests for _calculate_net_revenue programmatic fix."""

    def test_calculates_when_components_exist(self):
        entries = [{
            "owner_value": 1000.0,
            "owner_tax_amount": 50.0,
            "owner_deduct_amount": 25.0,
            "owner_net_revenue": None,
        }]
        corrections = _calculate_net_revenue(entries)

        assert len(corrections) == 1
        assert entries[0]["owner_net_revenue"] == 925.0

    def test_handles_zero_deductions(self):
        entries = [{
            "owner_value": 500.0,
            "owner_tax_amount": 0,
            "owner_deduct_amount": 0,
            "owner_net_revenue": None,
        }]
        _calculate_net_revenue(entries)

        assert entries[0]["owner_net_revenue"] == 500.0

    def test_skips_when_already_set(self):
        entries = [{
            "owner_value": 1000.0,
            "owner_tax_amount": 50.0,
            "owner_deduct_amount": 25.0,
            "owner_net_revenue": 925.0,
        }]
        corrections = _calculate_net_revenue(entries)

        assert len(corrections) == 0

    def test_skips_when_no_owner_value(self):
        entries = [{
            "owner_value": None,
            "owner_tax_amount": 50.0,
            "owner_deduct_amount": 25.0,
            "owner_net_revenue": None,
        }]
        corrections = _calculate_net_revenue(entries)

        assert len(corrections) == 0

    def test_handles_missing_deductions(self):
        entries = [{
            "owner_value": 750.0,
            "owner_net_revenue": None,
        }]
        _calculate_net_revenue(entries)

        assert entries[0]["owner_net_revenue"] == 750.0


class TestPropagateStatementFields:
    """Tests for _propagate_statement_fields."""

    def test_propagates_from_context(self):
        entries = [{"property_name": "", "interest_type": ""}]
        context = {"property_name": "Well A", "interest_type": "RI"}
        corrections = _propagate_statement_fields(entries, context)

        assert len(corrections) == 2
        assert entries[0]["property_name"] == "Well A"
        assert entries[0]["interest_type"] == "RI"

    def test_forward_fills_property_name(self):
        entries = [
            {"property_name": "Well A"},
            {"property_name": ""},
            {"property_name": ""},
            {"property_name": "Well B"},
        ]
        _propagate_statement_fields(entries, None)

        assert entries[1]["property_name"] == "Well A"
        assert entries[2]["property_name"] == "Well A"
        assert entries[3]["property_name"] == "Well B"

    def test_skips_when_already_set(self):
        entries = [{"property_name": "Existing", "interest_type": "WI"}]
        context = {"property_name": "Other", "interest_type": "RI"}
        _propagate_statement_fields(entries, context)

        assert entries[0]["property_name"] == "Existing"
        assert entries[0]["interest_type"] == "WI"


class TestPostProcessResult:
    """Tests for PostProcessResult model."""

    def test_empty_result(self):
        result = PostProcessResult()
        assert result.corrections == []
        assert result.ai_suggestions == []
        assert result.steps_completed == []
        assert result.steps_skipped == []

    def test_with_corrections(self):
        result = PostProcessResult(
            corrections=[
                AutoCorrection(
                    entry_index=0,
                    field="primary_name",
                    original_value="JOHN",
                    corrected_value="John",
                    source="programmatic",
                    confidence=ConfidenceLevel.HIGH,
                )
            ],
            steps_completed=["name_casing"],
            steps_skipped=["ai_verification"],
        )
        assert len(result.corrections) == 1
        assert result.corrections[0].source == "programmatic"


@pytest.fixture()
def _disable_external_services(monkeypatch):
    """Disable Gemini and Google Maps for isolated testing."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_enabled", False)
    monkeypatch.setattr(settings, "google_maps_enabled", False)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_disable_external_services")
class TestAutoEnrichIntegration:
    """Integration tests for auto_enrich pipeline."""

    async def test_extract_pipeline_no_ai(self):
        """Test extract pipeline with Gemini disabled."""
        from app.services.data_enrichment_pipeline import auto_enrich

        entries = [
            {
                "primary_name": "JOHN SMITH",
                "entity_type": "Individual",
                "first_name": "JOHN",
                "last_name": "SMITH",
                "mailing_address": None,
                "city": None,
                "state": None,
                "zip_code": None,
            }
        ]
        result = await auto_enrich("extract", entries)

        assert "name_casing" in result.steps_completed
        assert "ai_verification" in result.steps_skipped
        assert len(result.corrections) > 0
        assert entries[0]["primary_name"] == "John Smith"

    async def test_revenue_pipeline_no_ai(self):
        """Test revenue pipeline with Gemini disabled."""
        from app.services.data_enrichment_pipeline import auto_enrich

        entries = [
            {
                "product_code": "",
                "product_description": "Crude Oil",
                "owner_value": 1000.0,
                "owner_tax_amount": 50.0,
                "owner_deduct_amount": 25.0,
                "owner_net_revenue": None,
            }
        ]
        result = await auto_enrich("revenue", entries)

        assert "revenue_inference" in result.steps_completed
        assert entries[0]["product_code"] == "OIL"
        assert entries[0]["owner_net_revenue"] == 925.0

    async def test_proration_pipeline_name_casing(self):
        """Test proration pipeline only fixes names."""
        from app.services.data_enrichment_pipeline import auto_enrich

        entries = [{"owner": "MARY JONES LLC"}]
        result = await auto_enrich("proration", entries)

        assert "name_casing" in result.steps_completed
        assert "entity_type" in result.steps_skipped
        assert entries[0]["owner"] == "Mary Jones LLC"

    async def test_graceful_when_gemini_disabled(self):
        """Pipeline returns programmatic fixes only when Gemini is off."""
        from app.services.data_enrichment_pipeline import auto_enrich

        entries = [{"primary_name": "TEST NAME", "entity_type": "Individual"}]
        result = await auto_enrich("extract", entries)

        assert "ai_verification" in result.steps_skipped
        assert len(result.ai_suggestions) == 0
