"""Tests for security headers middleware (SEC-01 through SEC-06).

Verifies all 6 security headers are present with correct values
on both unauthenticated and authenticated endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_has_csp_header(unauthenticated_client: AsyncClient):
    """Content-Security-Policy header allows self, Google Fonts, inline styles."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "fonts.googleapis.com" in csp
    assert "fonts.gstatic.com" in csp
    assert "'unsafe-inline'" in csp


@pytest.mark.asyncio
async def test_health_has_hsts_header(unauthenticated_client: AsyncClient):
    """Strict-Transport-Security header with 1-year max-age."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


@pytest.mark.asyncio
async def test_health_has_x_frame_options(unauthenticated_client: AsyncClient):
    """X-Frame-Options DENY prevents clickjacking."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_health_has_x_content_type_options(unauthenticated_client: AsyncClient):
    """X-Content-Type-Options nosniff prevents MIME sniffing."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_health_has_referrer_policy(unauthenticated_client: AsyncClient):
    """Referrer-Policy controls referrer information leakage."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_health_has_permissions_policy(unauthenticated_client: AsyncClient):
    """Permissions-Policy restricts camera, microphone, geolocation."""
    response = await unauthenticated_client.get("/api/health")
    assert response.status_code == 200
    pp = response.headers["permissions-policy"]
    assert "camera=()" in pp
    assert "microphone=()" in pp
    assert "geolocation=()" in pp


@pytest.mark.asyncio
async def test_security_headers_on_authenticated_endpoint(authenticated_client: AsyncClient):
    """All 6 security headers present on authenticated endpoints too."""
    response = await authenticated_client.get("/api/health")
    assert response.status_code == 200
    expected_headers = [
        "content-security-policy",
        "strict-transport-security",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
    ]
    for header in expected_headers:
        assert header in response.headers, f"Missing header: {header}"
