"""In-memory RRC cache layer sitting in front of database lookups.

Provides a fast dict-based cache keyed by (district, lease_number) tuples.
The cache is populated from RRC DataFrame data and individual database
results are backfilled via update_cache().
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Module-level cache state
_rrc_cache: dict[tuple[str, str], dict | None] = {}
_rrc_cache_ready: bool = False


def get_from_cache(district: str, lease_number: str) -> dict | None:
    """Return cached RRC data for a (district, lease_number) key, or None on miss."""
    return _rrc_cache.get((district, lease_number))


def populate_cache(records: dict[tuple[str, str], dict]) -> None:
    """Bulk-populate cache from a lookup dict. Sets cache-ready flag."""
    global _rrc_cache_ready
    _rrc_cache.update(records)
    _rrc_cache_ready = True


def invalidate_cache() -> None:
    """Clear all cached data. Uses atomic dict replacement."""
    global _rrc_cache, _rrc_cache_ready
    _rrc_cache = {}
    _rrc_cache_ready = False


def is_cache_ready() -> bool:
    """Return True if cache has been populated at least once."""
    return _rrc_cache_ready


def update_cache(key: tuple[str, str], value: dict | None) -> None:
    """Single-key update for backfilling from database results."""
    _rrc_cache[key] = value


async def prewarm_rrc_cache() -> None:
    """Pre-warm the RRC DataFrame at startup (PERF-02).

    Loads the combined oil+gas lookup table in a background thread
    so the first proration request doesn't pay the cold-start cost.
    Does NOT populate the database-backed cache (too slow with 100K+ docs).
    """
    from app.services.proration.rrc_data_service import rrc_data_service

    lookup = await asyncio.to_thread(rrc_data_service._load_lookup)
    logger.info("RRC DataFrame pre-warmed: %d entries", len(lookup))
