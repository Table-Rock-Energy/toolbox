"""Tests for Revenue streaming upload endpoint (NDJSON)."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.auth import require_auth
from app.main import app
from app.models.revenue import RevenueStatement, RevenueRow, StatementFormat


@pytest_asyncio.fixture
async def authenticated_client():
    """HTTP client with auth dependency overridden."""
    async def _override_auth():
        return {"email": "test@example.com", "uid": "test-uid"}

    app.dependency_overrides[require_auth] = _override_auth
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _make_fake_statement(filename: str) -> RevenueStatement:
    """Build a minimal RevenueStatement for mocking."""
    return RevenueStatement(
        filename=filename,
        format=StatementFormat.ENERGYLINK,
        payor="Test Payor",
        rows=[
            RevenueRow(
                property_name="Well #1",
                product_code="OIL",
                owner_net_revenue=100.0,
            )
        ],
        errors=[],
    )


def _parse_ndjson(text: str) -> list[dict]:
    """Parse NDJSON text into list of dicts."""
    lines = text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


@pytest.mark.asyncio
class TestStreamingUpload:
    """Tests for POST /api/revenue/upload-stream."""

    async def test_streaming_upload_yields_progress_and_result(self, authenticated_client):
        """POST with 2 valid PDFs yields progress lines and a final result."""
        fake_stmt = _make_fake_statement("test1.pdf")

        with patch(
            "app.api.revenue._process_single_pdf",
            new_callable=AsyncMock,
            return_value=(fake_stmt, []),
        ), patch(
            "app.api.revenue._run_post_processing",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.api.revenue._persist_result",
            new_callable=AsyncMock,
        ):
            files = [
                ("files", ("test1.pdf", b"%PDF-1.4 fake content 1", "application/pdf")),
                ("files", ("test2.pdf", b"%PDF-1.4 fake content 2", "application/pdf")),
            ]
            response = await authenticated_client.post(
                "/api/revenue/upload-stream",
                files=files,
            )

        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")

        messages = _parse_ndjson(response.text)
        # Should have: processing1, done1, processing2, done2, result
        progress_msgs = [m for m in messages if m["type"] == "progress"]
        result_msgs = [m for m in messages if m["type"] == "result"]

        assert len(progress_msgs) >= 4  # 2 processing + 2 done
        assert len(result_msgs) == 1

    async def test_progress_message_shape(self, authenticated_client):
        """Each progress line has type, file, index, total, status fields."""
        fake_stmt = _make_fake_statement("shape_test.pdf")

        with patch(
            "app.api.revenue._process_single_pdf",
            new_callable=AsyncMock,
            return_value=(fake_stmt, []),
        ), patch(
            "app.api.revenue._run_post_processing",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.api.revenue._persist_result",
            new_callable=AsyncMock,
        ):
            files = [
                ("files", ("shape_test.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ]
            response = await authenticated_client.post(
                "/api/revenue/upload-stream",
                files=files,
            )

        messages = _parse_ndjson(response.text)
        progress_msgs = [m for m in messages if m["type"] == "progress" and "file" in m]

        assert len(progress_msgs) >= 1
        msg = progress_msgs[0]
        assert msg["type"] == "progress"
        assert "file" in msg
        assert "index" in msg
        assert "total" in msg
        assert "status" in msg
        assert msg["index"] == 1
        assert msg["total"] == 1

    async def test_result_message_shape(self, authenticated_client):
        """Final result line has type=result with data containing expected fields."""
        fake_stmt = _make_fake_statement("result_test.pdf")

        with patch(
            "app.api.revenue._process_single_pdf",
            new_callable=AsyncMock,
            return_value=(fake_stmt, []),
        ), patch(
            "app.api.revenue._run_post_processing",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.api.revenue._persist_result",
            new_callable=AsyncMock,
        ):
            files = [
                ("files", ("result_test.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ]
            response = await authenticated_client.post(
                "/api/revenue/upload-stream",
                files=files,
            )

        messages = _parse_ndjson(response.text)
        result_msg = [m for m in messages if m["type"] == "result"][0]

        assert "data" in result_msg
        data = result_msg["data"]
        assert "success" in data
        assert "statements" in data
        assert "total_rows" in data
        assert "errors" in data

    async def test_invalid_file_yields_error_progress(self, authenticated_client):
        """Non-PDF file yields progress with status=error, processing continues."""
        fake_stmt = _make_fake_statement("valid.pdf")

        async def _mock_process(file):
            if file.filename and file.filename.endswith(".pdf"):
                return fake_stmt, []
            return None, [f"Invalid file type: {file.filename}. Only PDF files are accepted."]

        with patch(
            "app.api.revenue._process_single_pdf",
            side_effect=_mock_process,
        ), patch(
            "app.api.revenue._run_post_processing",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.api.revenue._persist_result",
            new_callable=AsyncMock,
        ):
            files = [
                ("files", ("bad.txt", b"not a pdf", "text/plain")),
                ("files", ("valid.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ]
            response = await authenticated_client.post(
                "/api/revenue/upload-stream",
                files=files,
            )

        assert response.status_code == 200
        messages = _parse_ndjson(response.text)
        error_msgs = [m for m in messages if m.get("status") == "error"]
        assert len(error_msgs) >= 1
        assert "error" in error_msgs[0]

        # Result should still be present
        result_msgs = [m for m in messages if m["type"] == "result"]
        assert len(result_msgs) == 1
        # The valid PDF should have been processed
        assert result_msgs[0]["data"]["success"] is True

    async def test_empty_files_returns_400(self, authenticated_client):
        """Empty file list returns HTTP 400, not a streaming response."""
        response = await authenticated_client.post(
            "/api/revenue/upload-stream",
            files=[],
        )
        # FastAPI will return 422 for missing required field, or we handle 400 explicitly
        assert response.status_code in (400, 422)
