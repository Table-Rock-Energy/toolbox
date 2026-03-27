"""Tests for auth enforcement on all protected routes.

Verifies:
- Unauthenticated requests to router-level protected routes return 401
- Unauthenticated requests to per-endpoint protected routes return 401
- Authenticated requests succeed (do not return 401) for every router
- Intentionally unprotected endpoints remain accessible without auth
- Admin write endpoints return 401 without auth (require_admin chains on require_auth)

NOTE: /api/ghl/send/{job_id}/progress uses query-param token auth (?token=...)
because the EventSource API does not support custom headers. This endpoint is
intentionally excluded from standard Bearer-token smoke tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Router-level auth: unauthenticated -> 401
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GHL per-endpoint auth: unauthenticated -> 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_ghl_connections_returns_401(unauthenticated_client: AsyncClient):
    """GHL connections endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.get("/api/ghl/connections")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_contacts_upsert_returns_401(unauthenticated_client: AsyncClient):
    """GHL contacts upsert endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.post("/api/ghl/contacts/upsert")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_bulk_send_returns_401(unauthenticated_client: AsyncClient):
    """GHL bulk send endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.post("/api/ghl/contacts/bulk-send")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_cancel_returns_401(unauthenticated_client: AsyncClient):
    """GHL cancel send endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.post("/api/ghl/send/test-job/cancel")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_status_returns_401(unauthenticated_client: AsyncClient):
    """GHL send status endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.get("/api/ghl/send/test-job/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_ghl_quick_check_returns_401(unauthenticated_client: AsyncClient):
    """GHL quick-check connection endpoint requires per-endpoint auth."""
    response = await unauthenticated_client.post("/api/ghl/connections/test-id/quick-check")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Admin write endpoints: unauthenticated -> 401
# (require_admin chains on require_auth, so missing token hits 401 first)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_admin_create_user_returns_401(unauthenticated_client: AsyncClient):
    """Admin create user requires auth (require_admin chains require_auth)."""
    response = await unauthenticated_client.post("/api/admin/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_update_user_returns_401(unauthenticated_client: AsyncClient):
    """Admin update user requires auth."""
    response = await unauthenticated_client.put("/api/admin/users/test@example.com")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_delete_user_returns_401(unauthenticated_client: AsyncClient):
    """Admin delete user requires auth."""
    response = await unauthenticated_client.delete("/api/admin/users/test@example.com")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_update_ai_settings_returns_401(unauthenticated_client: AsyncClient):
    """Admin update AI settings requires auth."""
    response = await unauthenticated_client.put("/api/admin/settings/ai")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_update_maps_settings_returns_401(unauthenticated_client: AsyncClient):
    """Admin update google maps settings requires auth."""
    response = await unauthenticated_client.put("/api/admin/settings/google-maps")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_options_returns_401(unauthenticated_client: AsyncClient):
    """Admin options endpoint now requires auth (require_admin)."""
    response = await unauthenticated_client.get("/api/admin/options")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_users_list_returns_401(unauthenticated_client: AsyncClient):
    """Admin users list endpoint requires auth."""
    response = await unauthenticated_client.get("/api/admin/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_settings_ai_returns_401(unauthenticated_client: AsyncClient):
    """Admin AI settings GET requires auth."""
    response = await unauthenticated_client.get("/api/admin/settings/ai")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_settings_api_config_returns_401(unauthenticated_client: AsyncClient):
    """Admin api-config settings GET requires auth."""
    response = await unauthenticated_client.get("/api/admin/settings/api-config")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_admin_settings_google_maps_returns_401(unauthenticated_client: AsyncClient):
    """Admin google maps settings GET requires auth."""
    response = await unauthenticated_client.get("/api/admin/settings/google-maps")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Admin: authenticated non-admin -> 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticated_nonadmin_create_user_returns_403(authenticated_client: AsyncClient):
    """Authenticated non-admin user gets 403 on admin write endpoints."""
    response = await authenticated_client.post(
        "/api/admin/users",
        json={"email": "new@example.com"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_authenticated_nonadmin_options_returns_403(authenticated_client: AsyncClient):
    """Authenticated non-admin gets 403 on admin options."""
    response = await authenticated_client.get("/api/admin/options")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_authenticated_nonadmin_users_list_returns_403(authenticated_client: AsyncClient):
    """Authenticated non-admin gets 403 on admin users list."""
    response = await authenticated_client.get("/api/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_authenticated_nonadmin_settings_ai_returns_403(authenticated_client: AsyncClient):
    """Authenticated non-admin gets 403 on admin AI settings."""
    response = await authenticated_client.get("/api/admin/settings/ai")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Authenticated success tests: auth gate passes (non-401)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticated_extract_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to extract router passes auth gate."""
    response = await authenticated_client.get("/api/extract/health")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_title_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to title router passes auth gate."""
    response = await authenticated_client.get("/api/title/health")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_proration_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to proration router passes auth gate."""
    response = await authenticated_client.get("/api/proration/rrc/status")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_history_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to history router passes auth gate."""
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_user_jobs = AsyncMock(return_value=[])
        response = await authenticated_client.get("/api/history/jobs")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_etl_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to ETL router passes auth gate."""
    response = await authenticated_client.get("/api/etl/health")
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_authenticated_ghl_connections_succeeds(authenticated_client: AsyncClient):
    """Authenticated request to GHL connections passes auth gate."""
    with patch(
        "app.services.ghl.connection_service.list_connections",
        return_value=[],
    ):
        response = await authenticated_client.get("/api/ghl/connections")
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# Intentionally unprotected endpoints: accessible without auth
# ---------------------------------------------------------------------------


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
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_ghl_daily_limit_no_auth_required(unauthenticated_client: AsyncClient):
    """GHL daily-limit endpoint does NOT require auth."""
    response = await unauthenticated_client.get("/api/ghl/daily-limit")
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# Dev-mode bypass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_dev_mode_bypass(unauthenticated_client: AsyncClient):
    """Requests with invalid JWT tokens get 401.

    v2.0 uses JWT auth — invalid tokens fail decode and return 401.
    """
    response = await unauthenticated_client.post(
        "/api/extract/upload",
        headers={"Authorization": "Bearer fake-dev-token"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GHL: smart_list_name field removed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ghl_bulk_send_model_no_smart_list_name():
    """BulkSendRequest model no longer has smart_list_name field."""
    from app.models.ghl import BulkSendRequest
    assert "smart_list_name" not in BulkSendRequest.model_fields


# ---------------------------------------------------------------------------
# History: user-scoped jobs and delete ownership
# ---------------------------------------------------------------------------


def _make_mock_job(job_id="j1", tool="extract", user_id="test@example.com", status="completed"):
    """Create a mock Job object with the attributes history.py expects."""
    from unittest.mock import MagicMock
    from app.models.db_models import ToolType, JobStatus
    job = MagicMock()
    job.id = job_id
    job.user_id = user_id
    job.tool = ToolType(tool)
    job.status = JobStatus(status)
    job.source_filename = "test.csv"
    job.source_file_size = 1000
    job.total_count = 10
    job.success_count = 10
    job.error_count = 0
    job.error_message = None
    job.options = {}
    job.created_at = None
    job.completed_at = None
    return job


@pytest.mark.asyncio
async def test_history_scoped_nonadmin_gets_own_jobs(authenticated_client: AsyncClient):
    """Non-admin user gets only their own jobs from history."""
    mock_jobs = [_make_mock_job("j1", "extract", "test@example.com")]
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_user_jobs = AsyncMock(return_value=mock_jobs)
        response = await authenticated_client.get("/api/history/jobs")
    assert response.status_code == 200
    mock_db.get_user_jobs.assert_called_once()
    # Verify get_user_jobs was called with the user's email
    call_args = mock_db.get_user_jobs.call_args
    assert call_args[1].get("user_id") == "test@example.com" or call_args[0][1] == "test@example.com"


@pytest.mark.asyncio
async def test_history_admin_gets_all_jobs(admin_client: AsyncClient):
    """Admin user gets all jobs from history."""
    mock_jobs = [
        _make_mock_job("j1", "extract", "test@example.com"),
        _make_mock_job("j2", "title", "other@example.com"),
    ]
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_recent_jobs = AsyncMock(return_value=mock_jobs)
        response = await admin_client.get("/api/history/jobs")
    assert response.status_code == 200
    mock_db.get_recent_jobs.assert_called_once()


@pytest.mark.asyncio
async def test_delete_own_job_succeeds(authenticated_client: AsyncClient):
    """User can delete their own job."""
    mock_job = _make_mock_job("j1", "extract", "test@example.com")
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_job = AsyncMock(return_value=mock_job)
        mock_db.delete_job = AsyncMock(return_value=True)
        response = await authenticated_client.delete("/api/history/jobs/j1")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_other_user_job_returns_403(authenticated_client: AsyncClient):
    """Non-admin cannot delete another user's job."""
    mock_job = _make_mock_job("j1", "extract", "other@example.com")
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_job = AsyncMock(return_value=mock_job)
        response = await authenticated_client.delete("/api/history/jobs/j1")
    assert response.status_code == 403
    assert "your own jobs" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_delete_other_user_job_succeeds(admin_client: AsyncClient):
    """Admin can delete any user's job."""
    mock_job = _make_mock_job("j1", "extract", "other@example.com")
    with patch("app.api.history.db_service") as mock_db:
        mock_db.get_job = AsyncMock(return_value=mock_job)
        mock_db.delete_job = AsyncMock(return_value=True)
        await admin_client.delete("/api/history/jobs/j1")
