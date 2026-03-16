"""Tests for prompt content in CLEANUP_PROMPTS and TOOL_PROMPTS."""

from __future__ import annotations

from app.services.llm.prompts import CLEANUP_PROMPTS
from app.services.gemini_service import TOOL_PROMPTS


class TestEcfPrompts:
    """Test ECF prompt existence and content."""

    def test_ecf_cleanup_prompt_exists(self):
        """CLEANUP_PROMPTS contains 'ecf' key."""
        assert "ecf" in CLEANUP_PROMPTS

    def test_ecf_cleanup_prompt_content(self):
        """CLEANUP_PROMPTS['ecf'] contains cross-file comparison instructions."""
        prompt = CLEANUP_PROMPTS["ecf"]
        assert "cross-file" in prompt.lower() or "cross-file" in prompt
        assert "PDF is authoritative" in prompt
        assert "source_data" in prompt
        assert "entry_number" in prompt

    def test_ecf_validation_prompt_exists(self):
        """TOOL_PROMPTS contains 'ecf' key."""
        assert "ecf" in TOOL_PROMPTS

    def test_ecf_validation_prompt_content(self):
        """TOOL_PROMPTS['ecf'] contains ECF and Convey 640 references."""
        prompt = TOOL_PROMPTS["ecf"]
        assert "ECF" in prompt
        assert "Convey 640" in prompt


class TestSuffixStandardization:
    """Test suffix standardization additions to extract and title prompts."""

    def test_suffix_standardization_in_extract(self):
        """CLEANUP_PROMPTS['extract'] contains suffix standardization instructions."""
        prompt = CLEANUP_PROMPTS["extract"]
        assert "Suffix standardization" in prompt
        assert "Jr" in prompt
        assert "Sr" in prompt
        assert "III" in prompt

    def test_suffix_standardization_in_title(self):
        """CLEANUP_PROMPTS['title'] contains suffix standardization instructions."""
        prompt = CLEANUP_PROMPTS["title"]
        assert "Suffix standardization" in prompt
        assert "Jr" in prompt
        assert "Sr" in prompt
        assert "III" in prompt


class TestRevenueOutlierDetection:
    """Test revenue outlier detection additions."""

    def test_revenue_outlier_detection(self):
        """CLEANUP_PROMPTS['revenue'] contains outlier detection instructions."""
        prompt = CLEANUP_PROMPTS["revenue"]
        assert "_batch_median_value" in prompt
        assert "_outlier_threshold" in prompt
        assert "3x" in prompt


class TestAllToolsCovered:
    """Test that all tools have prompts."""

    def test_all_tools_have_cleanup_prompts(self):
        """All 5 tool keys exist in CLEANUP_PROMPTS."""
        expected = {"extract", "title", "proration", "revenue", "ecf"}
        assert expected.issubset(set(CLEANUP_PROMPTS.keys()))
