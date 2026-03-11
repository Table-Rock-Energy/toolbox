"""Tests for CORS configuration (SEC-01).

Verifies:
- Unknown origins do not get Access-Control-Allow-Origin header
- Configured origins get proper CORS headers
- Preflight (OPTIONS) requests work correctly for allowed origins
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(unauthenticated_client: AsyncClient):
    """Request from unknown origin should NOT get Access-Control-Allow-Origin."""
    response = await unauthenticated_client.get(
        "/api/health",
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 200
    # The CORS middleware should NOT reflect the disallowed origin
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(unauthenticated_client: AsyncClient):
    """Request from allowed origin should get proper CORS headers."""
    response = await unauthenticated_client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_preflight_allowed_origin(unauthenticated_client: AsyncClient):
    """CORS preflight (OPTIONS) for allowed origin returns proper headers."""
    response = await unauthenticated_client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_preflight_rejected_origin(unauthenticated_client: AsyncClient):
    """CORS preflight (OPTIONS) for disallowed origin should not reflect origin."""
    response = await unauthenticated_client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert "access-control-allow-origin" not in response.headers
