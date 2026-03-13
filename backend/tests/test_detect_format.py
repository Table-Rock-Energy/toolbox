"""Tests for the POST /api/extract/detect-format endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# --- Fake text patterns that trigger format detection ---

ECF_TEXT = (
    "APPLICATION OF SOME OPERATOR FOR A PERMIT TO DRILL A\n"
    "MULTIUNIT HORIZONTAL WELL IN SOME COUNTY\n"
    "CAUSE CD 2024-012345\n"
    "EXHIBIT A - LIST OF RESPONDENTS\n"
    "1. John Doe, 123 Main St, City, ST 12345\n"
    "2. Jane Smith, 456 Oak Ave, Town, ST 67890\n"
    + "x" * 100  # pad to exceed 50-char threshold
)

FREE_TEXT_NUMBERED_TEXT = (
    "EXHIBIT A\n"
    "NOTICE OF HEARING\n"
    "1. John Doe\n"
    "   123 Main Street\n"
    "   Oklahoma City, OK 73101\n"
    "2. Jane Smith\n"
    "   456 Oak Avenue\n"
    "   Tulsa, OK 74101\n"
    + "x" * 100  # pad to exceed 50-char threshold
)

SHORT_TEXT = "too short"


@pytest.mark.asyncio
async def test_detect_format_ecf(authenticated_client):
    """ECF PDF should return format='ECF' with label 'ECF Filing'."""
    with patch(
        "app.api.extract.extract_text_from_pdf", return_value=ECF_TEXT
    ):
        response = await authenticated_client.post(
            "/api/extract/detect-format",
            files={"file": ("test.pdf", b"%PDF-fake-content", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "ECF"
    assert data["format_label"] == "ECF Filing"


@pytest.mark.asyncio
async def test_detect_format_free_text(authenticated_client):
    """Non-ECF PDF should return correct non-ECF format."""
    with patch(
        "app.api.extract.extract_text_from_pdf",
        return_value=FREE_TEXT_NUMBERED_TEXT,
    ):
        response = await authenticated_client.post(
            "/api/extract/detect-format",
            files={"file": ("test.pdf", b"%PDF-fake-content", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "FREE_TEXT_NUMBERED"
    assert "format_label" in data


@pytest.mark.asyncio
async def test_detect_format_unreadable(authenticated_client):
    """Unreadable PDF should return format=null with error."""
    with patch(
        "app.api.extract.extract_text_from_pdf", return_value=SHORT_TEXT
    ):
        response = await authenticated_client.post(
            "/api/extract/detect-format",
            files={"file": ("test.pdf", b"%PDF-fake-content", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["format"] is None
    assert "error" in data
    assert "Could not extract text" in data["error"]
