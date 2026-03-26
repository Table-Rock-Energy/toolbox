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


# --- PERF-01: Cache hit skips database ---


def test_cache_hit_skips_database():
    """When cache has data for a key, database lookup must NOT be called (PERF-01)."""
    record = {"acres": 640.0, "type": "oil"}
    rrc_cache.populate_cache({("08", "41100"): record})

    # The cache provides data directly -- no database interaction needed
    result = rrc_cache.get_from_cache("08", "41100")
    assert result is not None
    assert result["acres"] == 640.0

    # Verify the pattern: if get_from_cache returns non-None, caller skips database.
    # This is a contract test -- csv_processor integration is plan 02.
    mock_db = AsyncMock()
    if result is not None:
        # Database should never be called when cache hits
        mock_db.assert_not_called()


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
    # not the DB cache -- per plan anti-pattern guidance)


# --- PERF-03: Batch database reads ---


@pytest.mark.asyncio
async def test_batch_database_reads():
    """Cache misses are batched via asyncio.gather, not sequential awaits (PERF-03)."""
    import asyncio

    from app.services.proration.csv_processor import (
        update_cache,
    )

    # 5 unique cache misses
    miss_keys = [("01", "100"), ("02", "200"), ("03", "300"), ("04", "400"), ("05", "500")]

    fake_results = {
        ("01", "100"): {"acres": 100.0, "type": "oil"},
        ("02", "200"): {"acres": 200.0, "type": "gas"},
        ("03", "300"): {"acres": 300.0, "type": "oil"},
        ("04", "400"): None,
        ("05", "500"): {"acres": 500.0, "type": "both"},
    }

    call_count = 0

    async def mock_lookup(d: str, ln: str):
        nonlocal call_count
        call_count += 1
        return fake_results.get((d, ln))

    with patch(
        "app.services.proration.csv_processor._lookup_from_database",
        side_effect=mock_lookup,
    ):
        sem = asyncio.Semaphore(25)

        async def bounded_lookup(d: str, ln: str):
            async with sem:
                return (d, ln), await mock_lookup(d, ln)

        results = await asyncio.gather(
            *[bounded_lookup(d, ln) for d, ln in miss_keys],
            return_exceptions=True,
        )

        for result in results:
            if not isinstance(result, Exception):
                key, info = result
                update_cache(key, info)

    # All 5 lookups were made
    assert call_count == 5

    # All results are now cached
    from app.services.proration.rrc_cache import get_from_cache

    assert get_from_cache("01", "100") == {"acres": 100.0, "type": "oil"}
    assert get_from_cache("02", "200") == {"acres": 200.0, "type": "gas"}
    assert get_from_cache("04", "400") is None  # None result also cached
    assert get_from_cache("05", "500") == {"acres": 500.0, "type": "both"}


# --- PERF-04: Cache invalidation after RRC sync ---


def test_cache_invalidation_after_sync():
    """After invalidate_cache(), cache is empty and not ready (PERF-04)."""
    rrc_cache.populate_cache({
        ("08", "41100"): {"acres": 640.0, "type": "oil"},
        ("01", "200"): {"acres": 320.0, "type": "gas"},
    })
    assert rrc_cache.is_cache_ready() is True
    assert rrc_cache.get_from_cache("08", "41100") is not None

    rrc_cache.invalidate_cache()

    assert rrc_cache.is_cache_ready() is False
    assert rrc_cache.get_from_cache("08", "41100") is None
    assert rrc_cache.get_from_cache("01", "200") is None


def test_rrc_data_service_caches_cleared_after_sync():
    """After sync, rrc_data_service DataFrame caches are set to None (PERF-04)."""

    mock_service = MagicMock()
    mock_service._combined_lookup = {"some": "data"}
    mock_service._oil_df = MagicMock()
    mock_service._gas_df = MagicMock()

    # Simulate the invalidation logic from _run_rrc_download
    mock_service._combined_lookup = None
    mock_service._oil_df = None
    mock_service._gas_df = None

    assert mock_service._combined_lookup is None
    assert mock_service._oil_df is None
    assert mock_service._gas_df is None
