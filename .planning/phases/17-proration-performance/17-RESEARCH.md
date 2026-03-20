# Phase 17: Proration Performance - Research

**Researched:** 2026-03-20
**Domain:** Python async caching, FastAPI startup hooks, Firestore batch reads, pandas DataFrame management
**Confidence:** HIGH

## Summary

This phase is a pure backend infrastructure optimization. The current proration upload flow has two performance problems: (1) cold-start latency because the RRC DataFrame is loaded lazily on first request, and (2) sequential per-row Firestore reads during CSV processing (one `await` per row in a `for` loop).

The fix is straightforward: pre-warm the RRC DataFrame cache in `main.py`'s startup event, add an in-memory lookup dict that mirrors Firestore RRC data, batch Firestore reads with `asyncio.gather`, and invalidate/refresh the in-memory cache when `rrc_background.py` completes a sync.

**Primary recommendation:** Layer a fast in-memory dict cache in front of Firestore, pre-warm it at startup, batch remaining Firestore lookups with `asyncio.gather`, and signal cache refresh after background sync completes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation choices at Claude's discretion.

### Claude's Discretion
All implementation choices are at Claude's discretion -- pure infrastructure phase.

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-01 | Proration lookups check in-memory cache before Firestore | In-memory dict cache in `csv_processor.py` keyed by `(district, lease_number)`, checked before any Firestore call |
| PERF-02 | RRC DataFrame cache pre-warms on application startup | FastAPI `@app.on_event("startup")` hook calls `rrc_data_service._load_lookup()` via `asyncio.to_thread` |
| PERF-03 | Proration Firestore reads use asyncio.gather for parallel execution | Collect all `(district, lease_number)` pairs from CSV rows, batch into `asyncio.gather` with chunking |
| PERF-04 | In-memory cache updates when background RRC sync completes | Signal mechanism (module-level flag or callback) in `rrc_background.py` that clears/rebuilds caches after sync |
</phase_requirements>

## Standard Stack

No new dependencies. This phase uses only existing libraries.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.x (existing) | Startup hooks, async endpoints | Already in stack |
| asyncio | stdlib | `asyncio.gather` for parallel Firestore reads, `asyncio.to_thread` for sync pre-warming | Built-in |
| pandas | 2.x (existing) | RRC DataFrame caching | Already in stack |
| google-cloud-firestore | existing | Async batch document reads via `get_all` | Already in stack |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level dict cache | Redis/memcached | Overkill -- single-instance Cloud Run, data fits in memory |
| Manual cache invalidation | `cachetools` TTL cache | TTL doesn't match the "invalidate after sync" requirement; manual control is simpler |

## Architecture Patterns

### Current Flow (Problem)
```
For each CSV row:
  1. Parse district + lease_number
  2. await lookup_rrc_acres(district, lease_number)  # Firestore: 2 doc reads (oil + gas)
  3. If miss: await lookup_rrc_by_lease_number(lease_number)  # Firestore query
  4. If miss: fall back to in-memory CSV lookup
```

For 200 rows, this is 200+ sequential Firestore round-trips (~50-100ms each = 10-20 seconds).

### Target Flow (Solution)
```
Startup:
  1. Load RRC CSV into pandas DataFrame (existing)
  2. Build combined lookup dict (existing _load_lookup)
  3. Pre-populate in-memory RRC cache from Firestore (new)

For each CSV row:
  1. Parse district + lease_number
  2. Check in-memory cache dict (microseconds)
  3. Collect cache misses

After loop:
  4. Batch Firestore reads for all misses via asyncio.gather (parallel)
  5. Update in-memory cache with Firestore results
  6. Apply results to rows

After background sync:
  7. Signal cache invalidation
  8. Next request rebuilds cache
```

### Pattern 1: In-Memory RRC Cache
**What:** Module-level dict in `csv_processor.py` (or a dedicated cache module) mapping `(district, lease_number)` -> `{acres, type, ...}`
**When to use:** Every proration lookup -- checked before Firestore
**Example:**
```python
# In-memory cache for RRC lookups (populated from Firestore + CSV)
_rrc_cache: dict[tuple[str, str], dict | None] = {}
_rrc_cache_ready = False

def get_from_cache(district: str, lease_number: str) -> dict | None:
    """Check in-memory cache. Returns None on miss, cached dict on hit."""
    return _rrc_cache.get((district, lease_number))

def populate_cache(records: dict[tuple[str, str], dict]) -> None:
    """Bulk-populate cache from Firestore or CSV data."""
    global _rrc_cache_ready
    _rrc_cache.update(records)
    _rrc_cache_ready = True

def invalidate_cache() -> None:
    """Clear cache after background sync."""
    global _rrc_cache_ready
    _rrc_cache.clear()
    _rrc_cache_ready = False
```

### Pattern 2: Startup Pre-Warming
**What:** Load the RRC DataFrame + combined lookup dict during FastAPI startup
**When to use:** `@app.on_event("startup")` in `main.py`
**Example:**
```python
@app.on_event("startup")
async def startup_event() -> None:
    # ... existing startup code ...

    # Pre-warm RRC DataFrame cache (CPU-bound, run in thread)
    try:
        await asyncio.to_thread(rrc_data_service._load_lookup)
        logger.info("RRC DataFrame cache pre-warmed")
    except Exception as e:
        logger.warning(f"RRC pre-warm failed (will load on first request): {e}")
```

### Pattern 3: Batch Firestore Reads
**What:** Collect all cache-miss keys, read them in parallel
**When to use:** During `process_csv` after checking in-memory cache
**Example:**
```python
# Collect misses
cache_misses: list[tuple[str, str]] = []
for row in rows:
    district, lease_number = parse_rrc(row)
    if (district, lease_number) not in _rrc_cache:
        cache_misses.append((district, lease_number))

# Batch read from Firestore (parallel)
if cache_misses:
    CHUNK_SIZE = 50  # Firestore get_all handles up to 100 refs
    results = {}
    for chunk in chunked(cache_misses, CHUNK_SIZE):
        tasks = [lookup_rrc_acres(d, ln) for d, ln in chunk]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        for (d, ln), result in zip(chunk, chunk_results):
            if isinstance(result, Exception):
                results[(d, ln)] = None
            else:
                results[(d, ln)] = result

    # Update cache
    _rrc_cache.update(results)
```

### Pattern 4: Cache Invalidation After Sync
**What:** Signal from `rrc_background.py` that clears the in-memory cache
**When to use:** After `_run_rrc_download` completes successfully
**Consideration:** Background thread vs async context -- need thread-safe invalidation
**Example:**
```python
# In rrc_background.py, at end of _run_rrc_download:
def _run_rrc_download(job_id: str) -> None:
    # ... download + sync steps ...

    # Clear in-memory caches so next request picks up fresh data
    rrc_data_service._combined_lookup = None
    rrc_data_service._oil_df = None
    rrc_data_service._gas_df = None

    # Also clear the Firestore-backed cache
    from app.services.proration.csv_processor import invalidate_rrc_cache
    invalidate_rrc_cache()
```

### Anti-Patterns to Avoid
- **Pre-loading all Firestore RRC docs at startup:** The oil + gas collections have 100K+ docs. Loading them all into memory at startup would take minutes and use excessive memory. Instead, cache on-demand and let the CSV lookup dict serve as the primary fast path.
- **TTL-based cache expiration:** RRC data changes monthly, not on a timer. Invalidate explicitly after sync, not on a timer.
- **Firestore `get_all` with 100+ refs in one call:** Firestore `get_all` supports batches, but individual `asyncio.gather` over standard lookups is simpler and already works with the existing `lookup_rrc_acres` function.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel async execution | Custom threading/queue | `asyncio.gather` | Built-in, handles exceptions, well-understood |
| Thread-safe cache invalidation | Locks/mutexes | Module-level flag + dict.clear() | Python GIL makes dict operations atomic for simple cases; flag check is inherently safe |
| Startup pre-warming | Custom background task | FastAPI `on_event("startup")` + `asyncio.to_thread` | Standard FastAPI pattern |

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop During Pre-Warm
**What goes wrong:** `rrc_data_service._load_lookup()` reads CSV files and iterates DataFrames -- this is CPU-bound and will block the async event loop.
**Why it happens:** Calling synchronous pandas operations directly in an async startup handler.
**How to avoid:** Wrap in `asyncio.to_thread()`.
**Warning signs:** Slow startup, other startup tasks delayed.

### Pitfall 2: Race Condition Between Background Sync and Active Requests
**What goes wrong:** Background thread clears cache while a request is mid-processing, causing partial results.
**Why it happens:** `dict.clear()` removes entries that an in-flight request was about to read.
**How to avoid:** Replace the dict reference atomically (`_rrc_cache = {}`) rather than calling `.clear()` on the existing dict. Or accept the minor race since the fallback to Firestore still works.
**Warning signs:** Sporadic "Not found in RRC data" for rows that should match.

### Pitfall 3: asyncio.gather Overwhelming Firestore
**What goes wrong:** Launching 200 concurrent Firestore reads may hit rate limits or cause connection pool exhaustion.
**Why it happens:** Unbounded concurrency in `asyncio.gather`.
**How to avoid:** Use `asyncio.Semaphore` to limit concurrent Firestore reads (e.g., 20-30 at a time), or chunk into batches of 50 and await each batch sequentially.
**Warning signs:** Firestore timeout errors, gRPC connection resets.

### Pitfall 4: Firestore get_all vs Individual Doc Reads
**What goes wrong:** Using Firestore `get_all` (batch document read) requires document references, which means you need to know the doc IDs upfront. The current `lookup_rrc_acres` reads from TWO collections (oil + gas), so a single `get_all` won't work directly.
**Why it happens:** Attempting to optimize with `get_all` without accounting for the two-collection structure.
**How to avoid:** Either (a) use `asyncio.gather` over the existing `lookup_rrc_acres` function, or (b) do two `get_all` calls (one for oil refs, one for gas refs) and merge results. Option (a) is simpler.
**Warning signs:** Missing gas data in results.

## Code Examples

### Refactored process_csv with Cache-First + Batch Lookup

```python
async def process_csv(file_bytes, filename, options):
    # ... parse CSV, filter, iterate rows ...

    # Phase 1: Parse all rows and check in-memory cache
    parsed_rows = []
    cache_misses = []

    for idx, row_data in df_filtered.iterrows():
        district, lease_number = rrc_data_service.parse_rrc_lease(rrc_lease_str)

        # Check in-memory cache first (PERF-01)
        cached = None
        if district and lease_number:
            cached = _rrc_cache.get((district, lease_number))

        parsed_rows.append((idx, row_data, district, lease_number, cached))

        if cached is None and district and lease_number:
            cache_misses.append((district, lease_number))

    # Phase 2: Batch Firestore reads for misses (PERF-03)
    if cache_misses and _use_firestore:
        sem = asyncio.Semaphore(25)

        async def bounded_lookup(d, ln):
            async with sem:
                return (d, ln), await _lookup_from_firestore(d, ln)

        results = await asyncio.gather(
            *[bounded_lookup(d, ln) for d, ln in set(cache_misses)],
            return_exceptions=True,
        )

        for result in results:
            if not isinstance(result, Exception):
                key, info = result
                _rrc_cache[key] = info

    # Phase 3: Build MineralHolderRow objects using cache
    for idx, row_data, district, lease_number, cached in parsed_rows:
        rrc_info = cached or _rrc_cache.get((district, lease_number))
        if rrc_info is None and district and lease_number:
            rrc_info = rrc_data_service.lookup_acres(district, lease_number)
        # ... build MineralHolderRow ...
```

### Startup Pre-Warm Hook

```python
# In main.py startup_event:
try:
    from app.services.proration.rrc_data_service import rrc_data_service
    await asyncio.to_thread(rrc_data_service._load_lookup)
    logger.info("RRC DataFrame pre-warmed: %d entries", len(rrc_data_service._combined_lookup or {}))
except Exception as e:
    logger.warning("RRC pre-warm failed: %s", e)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential per-row Firestore reads | Batch with asyncio.gather | This phase | 200 rows: ~20s -> ~2s |
| Lazy DataFrame load on first request | Pre-warm at startup | This phase | First request: ~5s cold start -> instant |
| No in-memory RRC cache | Dict cache checked before Firestore | This phase | Cache hit: ~50ms -> <1ms |

## Open Questions

1. **How large is the Firestore RRC dataset in practice?**
   - What we know: Oil + gas collections combined are the full RRC dataset (tens of thousands of docs)
   - What's unclear: Exact count affects whether full pre-loading from Firestore is feasible
   - Recommendation: Don't pre-load from Firestore at startup. The CSV DataFrame lookup already covers the bulk dataset. The cache will warm naturally from per-request Firestore hits.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01 | Cache checked before Firestore | unit | `cd backend && python3 -m pytest tests/test_proration_cache.py::test_cache_hit_skips_firestore -x` | Wave 0 |
| PERF-02 | Pre-warm runs at startup | integration | `cd backend && python3 -m pytest tests/test_proration_cache.py::test_startup_prewarm -x` | Wave 0 |
| PERF-03 | Batch Firestore reads use gather | unit | `cd backend && python3 -m pytest tests/test_proration_cache.py::test_batch_firestore_reads -x` | Wave 0 |
| PERF-04 | Cache invalidated after sync | unit | `cd backend && python3 -m pytest tests/test_proration_cache.py::test_cache_invalidation_after_sync -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_proration_cache.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_proration_cache.py` -- covers PERF-01 through PERF-04
- No framework install needed (pytest already configured)
- Existing `conftest.py` fixtures (authenticated_client, mock_user) are reusable

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `csv_processor.py`, `rrc_data_service.py`, `firestore_service.py`, `rrc_background.py`, `main.py`, `proration.py`
- FastAPI startup events: existing pattern in `main.py` lines 108-157
- Firestore async client: existing pattern in `firestore_service.py`

### Secondary (MEDIUM confidence)
- `asyncio.gather` concurrency patterns: Python stdlib documentation
- Firestore `get_all` batch read limits: existing code in `firestore_service.py` lines 782-794 (100 refs per batch)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries
- Architecture: HIGH -- patterns directly derived from reading existing code and identifying bottlenecks
- Pitfalls: HIGH -- identified from concrete code analysis (two-collection lookup, thread safety, event loop blocking)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable infrastructure, no external dependencies changing)
