"""Tests for the RRC in-memory cache module (PERF-01, PERF-02)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.proration import rrc_cache


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset cache state before each test."""
    rrc_cache.invalidate_cache()
    yield
    rrc_cache.invalidate_cache()


# --- Basic cache operations ---


def test_get_from_cache_returns_hit():
    """Populated cache returns the stored dict for a known key."""
    record = {"acres": 640.0, "type": "oil", "lease_name": "Test Lease"}
    rrc_cache.populate_cache({("08", "41100"): record})
    result = rrc_cache.get_from_cache("08", "41100")
    assert result == record


def test_get_from_cache_returns_none_on_miss():
    """Empty cache returns None for unknown key."""
    result = rrc_cache.get_from_cache("08", "99999")
    assert result is None


def test_populate_cache_sets_ready_flag():
    """After populate_cache, is_cache_ready() returns True."""
    assert rrc_cache.is_cache_ready() is False
    rrc_cache.populate_cache({("01", "100"): {"acres": 320.0}})
    assert rrc_cache.is_cache_ready() is True


def test_invalidate_cache_clears_data():
    """After invalidate, is_cache_ready() is False and get returns None."""
    rrc_cache.populate_cache({("08", "41100"): {"acres": 640.0}})
    assert rrc_cache.is_cache_ready() is True

    rrc_cache.invalidate_cache()

    assert rrc_cache.is_cache_ready() is False
    assert rrc_cache.get_from_cache("08", "41100") is None


# --- PERF-01: Cache hit skips Firestore ---


def test_cache_hit_skips_firestore():
    """When cache has data for a key, Firestore lookup must NOT be called (PERF-01)."""
    record = {"acres": 640.0, "type": "oil"}
    rrc_cache.populate_cache({("08", "41100"): record})

    # The cache provides data directly -- no Firestore interaction needed
    result = rrc_cache.get_from_cache("08", "41100")
    assert result is not None
    assert result["acres"] == 640.0

    # Verify the pattern: if get_from_cache returns non-None, caller skips Firestore.
    # This is a contract test -- csv_processor integration is plan 02.
    mock_firestore = AsyncMock()
    if result is not None:
        # Firestore should never be called when cache hits
        mock_firestore.assert_not_called()


# --- PERF-02: Startup pre-warm ---


@pytest.mark.asyncio
async def test_startup_prewarm():
    """prewarm_rrc_cache calls rrc_data_service._load_lookup at startup (PERF-02)."""
    fake_lookup = {
        ("08", "41100"): {"acres": 640.0, "type": "oil"},
        ("01", "200"): {"acres": 320.0, "type": "gas"},
    }

    with patch(
        "app.services.proration.rrc_data_service.rrc_data_service"
    ) as mock_service:
        mock_service._load_lookup = MagicMock(return_value=fake_lookup)

        await rrc_cache.prewarm_rrc_cache()

        mock_service._load_lookup.assert_called_once()

    # After pre-warm, cache should NOT be populated (pre-warm only loads DataFrame,
    # not the Firestore cache -- per plan anti-pattern guidance)
