"""Tests for auth enforcement on all tool endpoints (AUTH-01).

Verifies:
- Unauthenticated requests to protected routes return 401
- Health check remains accessible without auth
- Admin user-check endpoint remains accessible without auth
- Authenticated requests succeed (do not return 401)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unauthenticated_extract_returns_401(unauthenticated_client: AsyncClient):
    """Extract router requires auth."""
    response = await unauthenticated_client.get("/api/extract/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_title_returns_401(unauthenticated_client: AsyncClient):
    """Title router requires auth."""
    response = await unauthenticated_client.get("/api/title/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_proration_returns_401(unauthenticated_client: AsyncClient):
    """Proration router requires auth."""
    response = await unauthenticated_client.get("/api/proration/rrc/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_revenue_returns_401(unauthenticated_client: AsyncClient):
    """Revenue router requires auth."""
    response = await unauthenticated_client.post("/api/revenue/upload")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_prep_returns_401(unauthenticated_client: AsyncClient):
    """GHL Prep router requires auth."""
    response = await unauthenticated_client.post("/api/ghl-prep/upload")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_history_returns_401(unauthenticated_client: AsyncClient):
    """History router requires auth."""
    response = await unauthenticated_client.get("/api/history/jobs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ai_returns_401(unauthenticated_client: AsyncClient):
    """AI router requires auth."""
    response = await unauthenticated_client.get("/api/ai/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_enrichment_returns_401(unauthenticated_client: AsyncClient):
    """Enrichment router requires auth."""
    response = await unauthenticated_client.get("/api/enrichment/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_etl_returns_401(unauthenticated_client: AsyncClient):
    """ETL router requires auth."""
    response = await unauthenticated_client.get("/api/etl/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check_returns_200(unauthenticated_client: AsyncClient):
    """Health check endpoint does NOT require auth."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_admin_check_no_auth_required(unauthenticated_client: AsyncClient):
    """Admin user-check endpoint does NOT require auth."""
    response = await unauthenticated_client.get("/api/admin/users/test@example.com/check")
    # Should NOT be 401 -- the admin router has no router-level auth
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_extract_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to a protected route should not return 401."""
    response = await authenticated_client.get("/api/extract/health")
    # May return 404 (no such sub-route) but NOT 401
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_dev_mode_bypass(unauthenticated_client: AsyncClient):
    """When Firebase not configured, request with Bearer token gets synthetic user (not 401).

    In dev mode (Firebase not initialized), any Bearer token should be accepted
    and return the synthetic dev user, not a 401.
    """
    with patch("app.core.auth.get_firebase_app", return_value=None):
        response = await unauthenticated_client.get(
            "/api/extract/health",
            headers={"Authorization": "Bearer fake-dev-token"},
        )
    # Should NOT be 401 because dev-mode bypass returns synthetic user
    assert response.status_code != 401
