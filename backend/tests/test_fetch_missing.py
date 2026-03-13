"""Tests for RRC fetch-missing fixes (RRC-01, RRC-02, RRC-03).

RRC-01: Use individual_results directly instead of re-querying Firestore.
RRC-02: Split compound lease numbers (slash/comma separated) before lookup.
RRC-03: Set per-row fetch_status on every row returned from fetch-missing.
"""

from __future__ import annotations

import pytest

from app.models.proration import MineralHolderRow


# ---------------------------------------------------------------------------
# RRC-02: split_lease_number tests
# ---------------------------------------------------------------------------

def test_split_slash_separated():
    """Slash-separated compound lease numbers are split correctly."""
    from app.api.proration import split_lease_number
    assert split_lease_number("02-12345/02-12346") == ["02-12345", "02-12346"]


def test_split_comma_separated():
    """Comma-separated compound lease numbers are split correctly."""
    from app.api.proration import split_lease_number
    assert split_lease_number("02-12345,02-12346") == ["02-12345", "02-12346"]


def test_split_single_lease():
    """Single lease number returns a list with one element."""
    from app.api.proration import split_lease_number
    assert split_lease_number("02-12345") == ["02-12345"]


def test_split_empty_string():
    """Empty string returns empty list."""
    from app.api.proration import split_lease_number
    assert split_lease_number("") == []


def test_split_strips_whitespace():
    """Whitespace around parts is stripped after splitting."""
    from app.api.proration import split_lease_number
    assert split_lease_number("02-12345 / 02-12346") == ["02-12345", "02-12346"]


# ---------------------------------------------------------------------------
# RRC-03: fetch_status field on MineralHolderRow
# ---------------------------------------------------------------------------

def test_model_accepts_fetch_status():
    """MineralHolderRow validates with fetch_status field."""
    row = MineralHolderRow(
        county="MIDLAND",
        owner="Test Owner",
        interest=0.25,
        fetch_status="found",
    )
    assert row.fetch_status == "found"


def test_model_fetch_status_defaults_none():
    """MineralHolderRow fetch_status defaults to None."""
    row = MineralHolderRow(
        county="MIDLAND",
        owner="Test Owner",
        interest=0.25,
    )
    assert row.fetch_status is None


def test_model_accepts_all_fetch_status_values():
    """MineralHolderRow accepts all valid fetch_status values."""
    for status in ("found", "not_found", "multiple_matches", "split_lookup"):
        row = MineralHolderRow(
            county="MIDLAND",
            owner="Test Owner",
            interest=0.25,
            fetch_status=status,
        )
        assert row.fetch_status == status


# ---------------------------------------------------------------------------
# RRC-01: individual_results used directly (no redundant Firestore re-query)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_individual_results_used_directly(monkeypatch):
    """After individual fetch, results are used directly without calling lookup_rrc_acres again.

    Mocks lookup_rrc_acres and lookup_rrc_by_lease_number in the Firestore
    service to track whether they are called during the post-individual-fetch
    re-application loop. They should NOT be called.
    """
    from unittest.mock import AsyncMock, patch

    # Track calls to Firestore lookup functions
    firestore_lookup_calls: list[str] = []

    async def mock_lookup_rrc_acres(district, lease_number):
        firestore_lookup_calls.append(f"lookup_rrc_acres({district},{lease_number})")
        return None  # Simulate not found in Firestore

    async def mock_lookup_rrc_by_lease_number(lease_number):
        firestore_lookup_calls.append(f"lookup_rrc_by_lease_number({lease_number})")
        return None

    async def mock_fetch_individual_leases(leases):
        """Simulate successful individual fetch returning results."""
        results = {}
        for d, ln, _cc in leases:
            results[(d, ln)] = {"acres": 640.0, "type": "oil"}
        return results

    async def mock_ensure_counties_fresh(counties):
        return [{"status": "fresh", "county_name": c["county_name"], "records_downloaded": 0} for c in counties]

    def mock_lookup_county(name):
        return ("123", "08", name.upper())

    # Patch at the module level where the imports are used
    with patch("app.api.proration.lookup_rrc_acres", side_effect=mock_lookup_rrc_acres), \
         patch("app.api.proration.lookup_rrc_by_lease_number", side_effect=mock_lookup_rrc_by_lease_number), \
         patch("app.api.proration.fetch_individual_leases", side_effect=mock_fetch_individual_leases), \
         patch("app.api.proration.ensure_counties_fresh", side_effect=mock_ensure_counties_fresh), \
         patch("app.services.proration.rrc_county_codes.lookup_county", side_effect=mock_lookup_county):

        from app.api.proration import fetch_missing_rrc_data
        from app.models.proration import FetchMissingRequest

        # Create a mock BackgroundTasks
        bg = AsyncMock()
        bg.add_task = lambda *a, **kw: None

        request = FetchMissingRequest(rows=[
            MineralHolderRow(
                county="MIDLAND",
                owner="Test Owner",
                interest=0.25,
                district="08",
                lease_number="41100",
                rrc_lease="08-41100",
            ),
        ])

        # Clear call tracker before the endpoint runs
        firestore_lookup_calls.clear()

        result = await fetch_missing_rrc_data(request, bg)

        # Step 1 Firestore lookups are expected (initial check)
        step1_calls = [c for c in firestore_lookup_calls if "lookup_rrc_acres" in c or "lookup_rrc_by_lease_number" in c]
        # After individual_results are populated, lookup_rrc_acres should NOT
        # be called again in the re-application loop. The total calls should be
        # only from Step 1 (at most 2: lookup_rrc_acres + lookup_rrc_by_lease_number).
        assert len(step1_calls) <= 2, (
            f"Expected at most 2 Firestore lookups (Step 1 only), got {len(step1_calls)}: {step1_calls}"
        )

        # The row should be matched via individual_results
        assert result.matched_count == 1
        assert result.updated_rows[0].rrc_acres == 640.0


# ---------------------------------------------------------------------------
# RRC-03: fetch_status set on returned rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_status_set_on_returned_rows(monkeypatch):
    """Rows returned from fetch-missing have fetch_status set appropriately."""
    from unittest.mock import AsyncMock, patch

    async def mock_lookup_rrc_acres(district, lease_number):
        return None

    async def mock_lookup_rrc_by_lease_number(lease_number):
        return None

    async def mock_fetch_individual_leases(leases):
        results = {}
        # Only return data for the first lease
        for d, ln, _cc in leases[:1]:
            results[(d, ln)] = {"acres": 320.0, "type": "gas"}
        return results

    async def mock_ensure_counties_fresh(counties):
        return []

    def mock_lookup_county(name):
        return ("123", "08", name.upper())

    with patch("app.api.proration.lookup_rrc_acres", side_effect=mock_lookup_rrc_acres), \
         patch("app.api.proration.lookup_rrc_by_lease_number", side_effect=mock_lookup_rrc_by_lease_number), \
         patch("app.api.proration.fetch_individual_leases", side_effect=mock_fetch_individual_leases), \
         patch("app.api.proration.ensure_counties_fresh", side_effect=mock_ensure_counties_fresh), \
         patch("app.services.proration.rrc_county_codes.lookup_county", side_effect=mock_lookup_county):

        from app.api.proration import fetch_missing_rrc_data
        from app.models.proration import FetchMissingRequest

        bg = AsyncMock()
        bg.add_task = lambda *a, **kw: None

        request = FetchMissingRequest(rows=[
            MineralHolderRow(
                county="MIDLAND",
                owner="Owner A",
                interest=0.25,
                district="08",
                lease_number="41100",
                rrc_lease="08-41100",
            ),
            MineralHolderRow(
                county="MIDLAND",
                owner="Owner B",
                interest=0.10,
                district="08",
                lease_number="99999",
                rrc_lease="08-99999",
            ),
        ])

        result = await fetch_missing_rrc_data(request, bg)

        # First row should be "found", second should be "not_found"
        statuses = {row.owner: row.fetch_status for row in result.updated_rows}
        assert statuses["Owner A"] == "found"
        assert statuses["Owner B"] == "not_found"
