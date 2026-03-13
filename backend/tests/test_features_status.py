"""Tests for the GET /api/features/status endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_feature_status_all_disabled(authenticated_client):
    """When all feature switches are off (default config), all flags return false."""
    with patch("app.api.features.settings") as mock_settings:
        mock_settings.use_gemini = False
        mock_settings.use_google_maps = False
        mock_settings.use_enrichment = False

        response = await authenticated_client.get("/api/features/status")

    assert response.status_code == 200
    data = response.json()
    assert data["cleanup_enabled"] is False
    assert data["validate_enabled"] is False
    assert data["enrich_enabled"] is False


@pytest.mark.asyncio
async def test_feature_status_cleanup_enabled(authenticated_client):
    """When gemini is configured, cleanup_enabled is true."""
    with patch("app.api.features.settings") as mock_settings:
        mock_settings.use_gemini = True
        mock_settings.use_google_maps = False
        mock_settings.use_enrichment = False

        response = await authenticated_client.get("/api/features/status")

    assert response.status_code == 200
    data = response.json()
    assert data["cleanup_enabled"] is True
    assert data["validate_enabled"] is False
    assert data["enrich_enabled"] is False


@pytest.mark.asyncio
async def test_feature_status_validate_enabled(authenticated_client):
    """When google maps is configured, validate_enabled is true."""
    with patch("app.api.features.settings") as mock_settings:
        mock_settings.use_gemini = False
        mock_settings.use_google_maps = True
        mock_settings.use_enrichment = False

        response = await authenticated_client.get("/api/features/status")

    assert response.status_code == 200
    data = response.json()
    assert data["cleanup_enabled"] is False
    assert data["validate_enabled"] is True
    assert data["enrich_enabled"] is False


@pytest.mark.asyncio
async def test_feature_status_enrich_enabled(authenticated_client):
    """When enrichment is configured, enrich_enabled is true."""
    with patch("app.api.features.settings") as mock_settings:
        mock_settings.use_gemini = False
        mock_settings.use_google_maps = False
        mock_settings.use_enrichment = True

        response = await authenticated_client.get("/api/features/status")

    assert response.status_code == 200
    data = response.json()
    assert data["cleanup_enabled"] is False
    assert data["validate_enabled"] is False
    assert data["enrich_enabled"] is True


@pytest.mark.asyncio
async def test_feature_status_all_enabled(authenticated_client):
    """When all features are configured, all flags return true."""
    with patch("app.api.features.settings") as mock_settings:
        mock_settings.use_gemini = True
        mock_settings.use_google_maps = True
        mock_settings.use_enrichment = True

        response = await authenticated_client.get("/api/features/status")

    assert response.status_code == 200
    data = response.json()
    assert data["cleanup_enabled"] is True
    assert data["validate_enabled"] is True
    assert data["enrich_enabled"] is True
