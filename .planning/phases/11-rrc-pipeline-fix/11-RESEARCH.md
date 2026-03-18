# Phase 11: RRC Pipeline Fix - Research

**Researched:** 2026-03-18
**Domain:** RRC fetch-missing pipeline -- compound lease splitting, direct data use, per-row status
**Confidence:** HIGH

## Summary

This phase fixes three specific bugs/gaps in the existing fetch-missing pipeline. All changes are constrained to `backend/app/api/proration.py` (the fetch-missing endpoint), `backend/app/models/proration.py` (response model), `backend/app/services/proration/rrc_county_download_service.py` (concurrency model), and `frontend/src/pages/Proration.tsx` (merge + tooltip).

The existing code is well-structured for these changes. `split_lease_number()` already exists but is never called. The `fetch_status` field and frontend status icons already exist. The frontend merge logic at lines 676-687 already works by key. The main work is: (1) add district inheritance to `split_lease_number`, (2) integrate it into the fetch-missing loop, (3) replace `MAX_INDIVIDUAL_QUERIES` cap with `asyncio.Semaphore(8)` concurrency, (4) add sub-lease annotation field to response model, (5) add tooltip to frontend status icons.

**Primary recommendation:** This is a surgical fix -- modify the existing fetch-missing endpoint and its supporting code. No new files, no new dependencies, no architectural changes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Split on `/` and `,` delimiters (already what `split_lease_number()` does)
- District inheritance: if first sub-lease has a district prefix (e.g., "02-12345"), propagate that district to subsequent parts that lack one (e.g., "12346" becomes "02-12346"). Fall back to `row.district` if first part also lacks a prefix.
- Preserve the original `rrc_lease` string on the row. Matched sub-lease details go in a separate annotation field (not overwriting the original).
- When multiple sub-leases return different RRC data, return all as separate matches attached to the row (don't pick one or aggregate).
- fetch-missing API response includes full matched RRC fields (acres, allowable, etc.) per row
- Frontend merges RRC data into existing table rows in-place (patch RRC columns, preserve user edits to non-RRC fields, highlight changed cells)
- Background persist: return data to frontend immediately, write to Firestore via BackgroundTask so the cache is warm for future lookups
- Compound leases that have at least one sub-lease match show `split_lookup` status (green check, already wired in frontend)
- Compound leases where ALL sub-leases miss show regular `not_found` (no new status value needed)
- Sub-lease breakdown visible via tooltip on the status icon: "02-12345 found (240 acres), 12346 not found"
- No expandable sub-rows or inline detail -- tooltip is sufficient
- Expand all compound leases BEFORE the cap check (split first, deduplicate, then count)
- Remove the hard cap (MAX_INDIVIDUAL_QUERIES). Instead, use concurrency-limited throttling: max 8 concurrent HTML scrape requests at a time, queue the rest
- No absolute max on total queries -- process all expanded leases at the concurrency limit
- `asyncio.Semaphore(8)` pattern for throttling concurrent RRC HTML requests

### Claude's Discretion
- Exact asyncio semaphore implementation pattern
- How to structure the sub-lease results annotation field in the response model
- Tooltip rendering approach for sub-lease breakdown
- BackgroundTask implementation for Firestore persist

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RRC-01 | Compound lease numbers (slash/comma-separated) are split and each lease looked up individually | `split_lease_number()` exists at proration.py:41, needs district inheritance added, needs integration into fetch-missing loop at ~line 378 |
| RRC-02 | Fetch-missing uses returned RRC data directly instead of re-querying Firestore | Already partially implemented (lines 446-454 use `individual_results` directly). Need to ensure compound sub-leases also use results directly, plus BackgroundTask Firestore persist |
| RRC-03 | After fetch-missing, each row shows status: found, not found, or multiple matches | `fetch_status` field exists on model. Frontend icons at lines 1436-1439 already render all 4 statuses. Need to add sub-lease tooltip and ensure `split_lookup` is set for compound matches |
</phase_requirements>

## Standard Stack

No new dependencies. All changes use existing libraries already in the project.

### Core (already installed)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| FastAPI | 0.x | API endpoint (`fetch_missing_rrc_data`) | `BackgroundTasks` already in endpoint signature |
| Pydantic | 2.x | `FetchMissingResult`, `MineralHolderRow` models | Add annotation field |
| asyncio | stdlib | `Semaphore(8)` for concurrency throttling | Replace sequential loop in `fetch_individual_leases` |
| React | 19.x | Tooltip rendering for sub-lease breakdown | Use native `title` attribute or Tailwind hover |

**No installation needed.**

## Architecture Patterns

### Pattern 1: District Inheritance in split_lease_number

**What:** Enhanced `split_lease_number` that propagates district prefix from first part to subsequent parts.

**Current code** (proration.py:41-48):
```python
def split_lease_number(rrc_lease: str) -> list[str]:
    import re
    if not rrc_lease:
        return []
    parts = re.split(r"[/,]", rrc_lease)
    return [p.strip() for p in parts if p.strip()]
```

**Required change:** Add a new function or enhance existing one to return `list[tuple[str, str]]` (district, lease_number) pairs with inheritance:
```python
def split_compound_lease(rrc_lease: str, fallback_district: str = "") -> list[tuple[str, str]]:
    """Split compound lease and resolve district for each part.

    District inheritance: first part's district propagates to subsequent
    parts that lack one. Falls back to fallback_district if no part has one.

    Returns list of (district, lease_number) tuples.
    """
    import re
    if not rrc_lease:
        return []

    raw_parts = re.split(r"[/,]", rrc_lease)
    parts = [p.strip() for p in raw_parts if p.strip()]

    resolved: list[tuple[str, str]] = []
    inherited_district = fallback_district

    for part in parts:
        if "-" in part:
            d, ln = part.split("-", 1)
            inherited_district = d.strip()  # Learn district from first part that has one
            resolved.append((inherited_district, ln.strip()))
        else:
            resolved.append((inherited_district, part))

    return resolved
```

**When to use:** Called inside the fetch-missing loop when `rrc_lease` contains `/` or `,`.

### Pattern 2: Semaphore-Based Concurrency for Individual Lease Fetch

**What:** Replace sequential `for` loop + hard cap with `asyncio.Semaphore(8)` + `asyncio.gather`.

**Current code** (proration.py:422-440): Sequential loop with `MAX_INDIVIDUAL_QUERIES = 25` cap.

**Required change in `rrc_county_download_service.py`:** The `fetch_individual_leases` function currently uses a sequential `for` loop with synchronous `requests` calls. The semaphore pattern needs to wrap the existing sequential HTTP calls, not make them truly async (since `requests` is synchronous).

**Key insight:** `fetch_individual_leases` uses `requests.Session` (synchronous). To use `asyncio.Semaphore`, wrap each lease lookup in `asyncio.to_thread()` or use `run_in_executor`. The semaphore limits concurrency:

```python
import asyncio

MAX_CONCURRENT_RRC = 8

async def fetch_individual_leases(leases: list[tuple[str, str, str]]) -> dict:
    sem = asyncio.Semaphore(MAX_CONCURRENT_RRC)
    results: dict[tuple[str, str], dict] = {}

    async def fetch_one(district, lease_number, county_code, session):
        async with sem:
            # Run synchronous requests call in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, _fetch_single_lease_sync, session, district, lease_number, county_code
            )

    # ... gather all tasks
```

**Important caveat:** Each `requests.Session` holds cookies from the RRC warm-up. Multiple concurrent sessions may not work -- RRC may track session state server-side. The safer approach: use a single session with sequential requests but remove the cap, OR use multiple independent sessions (each warmed separately) with the semaphore. The user's FTP analogy suggests the latter (8 independent connections).

**Recommendation:** Use 8 independent sessions, each warmed once, dispatched via semaphore. If RRC rejects concurrent sessions, fall back to sequential with no cap.

### Pattern 3: Sub-Lease Annotation Field

**What:** New field on `MineralHolderRow` to carry sub-lease breakdown for tooltip display.

```python
# On MineralHolderRow:
sub_lease_results: Optional[list[dict]] = Field(
    None,
    description="Per-sub-lease results for compound leases: [{lease: '02-12345', status: 'found', acres: 240}, ...]"
)
```

Frontend reads this for tooltip text: `row.sub_lease_results?.map(s => ...).join(', ')`.

### Pattern 4: Frontend Tooltip on Status Icon

**What:** Add `title` attribute to the status icon `<span>` that shows sub-lease breakdown.

**Current code** (Proration.tsx:1434-1440): Status icons rendered inline next to acres value. No tooltip.

**Required change:**
```tsx
{row.fetch_status === 'split_lookup' && (
  <CheckCircle
    className="w-3.5 h-3.5 text-green-500"
    title={row.sub_lease_results?.map(s =>
      `${s.lease} ${s.status}${s.acres ? ` (${s.acres} acres)` : ''}`
    ).join(', ')}
  />
)}
```

Using native `title` attribute is simplest and matches the existing pattern (line 1424 already uses `title` for truncated text). No tooltip library needed.

### Anti-Patterns to Avoid
- **Don't create a separate session per request inside the loop** -- warm each session once, reuse it for multiple queries
- **Don't use `asyncio.gather` with `requests` without `run_in_executor`** -- `requests` is blocking; will block the event loop
- **Don't overwrite `row.rrc_lease`** -- user explicitly locked: preserve original, put details in annotation field
- **Don't aggregate sub-lease acres** -- user explicitly locked: return all matches separately

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrency limiting | Custom queue/counter | `asyncio.Semaphore(8)` | Battle-tested stdlib, handles edge cases |
| Tooltip rendering | Custom tooltip component | Native HTML `title` attribute | Sufficient for text-only tooltip, no JS needed |
| Thread pool dispatch | Manual threading | `asyncio.get_event_loop().run_in_executor()` | Standard pattern for sync-in-async |

## Common Pitfalls

### Pitfall 1: RRC Session Sharing Under Concurrency
**What goes wrong:** Multiple concurrent requests sharing one `requests.Session` cause cookie/state corruption. RRC uses server-side session tracking.
**Why it happens:** `requests.Session` is not thread-safe for concurrent use.
**How to avoid:** Create one session per concurrent worker (up to 8). Each session warms independently. Semaphore limits total active sessions.
**Warning signs:** Random 403s or "session expired" HTML responses from RRC.

### Pitfall 2: District Inheritance Edge Cases
**What goes wrong:** Lease like `"12345/12346"` (no district prefix on any part) gets empty district.
**Why it happens:** `split_compound_lease` can't infer district from the lease string alone.
**How to avoid:** Always pass `row.district` as `fallback_district`. The row's district is parsed from `rrc_lease` (the "02" in "02-12345") or from `raw_rrc` earlier in the loop.
**Warning signs:** Sub-leases looked up with empty district string.

### Pitfall 3: Blocking the Event Loop with requests
**What goes wrong:** `fetch_individual_leases` uses synchronous `requests.post()`. If called with `asyncio.gather` without `run_in_executor`, it blocks the FastAPI event loop for all 8 concurrent requests sequentially.
**Why it happens:** Python `requests` is synchronous. `asyncio.gather` doesn't magically make sync code async.
**How to avoid:** Wrap each synchronous HTTP call in `loop.run_in_executor(None, sync_fn, ...)`.
**Warning signs:** Other API endpoints become unresponsive during fetch-missing.

### Pitfall 4: Deduplication After Compound Split
**What goes wrong:** Two rows reference the same sub-lease (e.g., row A has "02-12345/12346", row B has "02-12346"). Without deduplication, lease 12346 is fetched twice.
**Why it happens:** Compound expansion creates new entries that may overlap with other rows.
**How to avoid:** After expanding all compound leases, deduplicate by (district, lease_number) before querying. Map results back to all rows that reference each lease.
**Warning signs:** Same lease appearing multiple times in RRC query logs.

### Pitfall 5: `_apply_rrc_info` for Split Leases
**What goes wrong:** For a compound lease with multiple sub-matches returning different acres, `_apply_rrc_info` is called once. Which sub-lease's acres goes on the row?
**Why it happens:** User decision says "return all as separate matches" but the row has one `rrc_acres` field.
**How to avoid:** For `split_lookup`, pick the first found sub-lease's acres for the row's `rrc_acres` (or the max). Put all sub-lease details in `sub_lease_results`. The tooltip shows the full breakdown.
**Warning signs:** Row shows acres from wrong sub-lease, or 0 acres despite sub-matches existing.

## Code Examples

### Enhanced split_compound_lease (verified against existing code)
```python
# Source: derived from existing split_lease_number at proration.py:41
def split_compound_lease(rrc_lease: str, fallback_district: str = "") -> list[tuple[str, str]]:
    """Split compound lease, inherit district from first part."""
    import re
    if not rrc_lease:
        return []
    raw_parts = re.split(r"[/,]", rrc_lease)
    parts = [p.strip() for p in raw_parts if p.strip()]

    resolved = []
    inherited_district = fallback_district
    for part in parts:
        if "-" in part:
            d, ln = part.split("-", 1)
            inherited_district = d.strip()
            resolved.append((inherited_district, ln.strip()))
        else:
            resolved.append((inherited_district, part))
    return resolved
```

### Semaphore-throttled fetch (pattern only -- actual impl depends on session management)
```python
# Source: asyncio stdlib pattern
import asyncio

MAX_CONCURRENT_RRC = 8

async def fetch_individual_leases_throttled(leases, create_session_fn):
    sem = asyncio.Semaphore(MAX_CONCURRENT_RRC)
    results = {}

    async def fetch_one(district, lease_number, county_code):
        async with sem:
            session = create_session_fn()
            _warm_rrc_session(session)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, _fetch_single_lease_sync, session, district, lease_number, county_code
            )
            if data:
                results[(district, lease_number)] = data

    tasks = [fetch_one(d, ln, cc) for d, ln, cc in leases]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Frontend tooltip for sub-lease breakdown
```tsx
// Source: pattern matching existing title usage at Proration.tsx:1424
{row.fetch_status === 'split_lookup' && (
  <CheckCircle
    className="w-3.5 h-3.5 text-green-500"
    title={row.sub_lease_results?.map((s: SubLeaseResult) =>
      `${s.district}-${s.lease_number}: ${s.status}${s.acres ? ` (${s.acres} acres)` : ''}`
    ).join('\n') || 'Split lookup'}
  />
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `MAX_INDIVIDUAL_QUERIES = 25` hard cap | `asyncio.Semaphore(8)` concurrency limit | This phase | All expanded leases processed, just throttled |
| `split_lease_number()` defined but unused | `split_compound_lease()` called in fetch-missing loop | This phase | Compound leases actually resolved |
| Re-query Firestore after individual fetch | Use `individual_results` directly | Already partially done (lines 446-454) | Faster response, no unnecessary Firestore reads |

## Open Questions

1. **RRC concurrent session tolerance**
   - What we know: RRC uses server-side sessions (cookies set during warm-up). Sequential requests work reliably.
   - What's unclear: Whether RRC allows 8 concurrent sessions from the same IP. The site is old and may have basic rate limiting.
   - Recommendation: Start with 8 concurrent sessions. If failures spike, add exponential backoff and reduce to 4. Log concurrency-related failures distinctly.

2. **Which sub-lease's data populates the row?**
   - What we know: User says "return all as separate matches" (don't aggregate). But `rrc_acres` is a single float field on the row.
   - What's unclear: Should the row show the first match's acres? The max? Leave it null and only show in tooltip?
   - Recommendation: Use the first found sub-lease's data for the row's `rrc_acres` and `well_type`. All sub-lease details in `sub_lease_results` for tooltip. This gives the user a useful value in the table while the tooltip shows the full picture.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (asyncio_mode = auto) |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_fetch_missing.py -x -v` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RRC-01 | Compound leases split with district inheritance | unit | `python3 -m pytest tests/test_fetch_missing.py::test_split_compound_lease_district_inheritance -x` | Wave 0 (new tests needed) |
| RRC-01 | Split leases integrated into fetch-missing loop | unit | `python3 -m pytest tests/test_fetch_missing.py::test_compound_lease_integrated -x` | Wave 0 |
| RRC-02 | Results used directly, no re-query | unit | `python3 -m pytest tests/test_fetch_missing.py::test_individual_results_used_directly -x` | Exists (already passes) |
| RRC-03 | Per-row fetch_status set correctly | unit | `python3 -m pytest tests/test_fetch_missing.py::test_fetch_status_set_on_returned_rows -x` | Exists (already passes) |
| RRC-03 | split_lookup status for compound matches | unit | `python3 -m pytest tests/test_fetch_missing.py::test_split_lookup_status -x` | Wave 0 |
| RRC-03 | sub_lease_results populated for compound leases | unit | `python3 -m pytest tests/test_fetch_missing.py::test_sub_lease_results_annotation -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -v`
- **Per wave merge:** `cd backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fetch_missing.py` -- add tests for: `split_compound_lease` district inheritance (multiple formats), compound lease integration into fetch-missing loop, `split_lookup` status assignment, `sub_lease_results` annotation field populated
- [ ] Existing tests cover RRC-02 and RRC-03 basics but NOT compound lease scenarios

## Sources

### Primary (HIGH confidence)
- `backend/app/api/proration.py` -- full fetch-missing endpoint code inspected
- `backend/app/models/proration.py` -- `MineralHolderRow` and `FetchMissingResult` models inspected
- `backend/app/services/proration/rrc_county_download_service.py` -- `fetch_individual_leases` implementation inspected
- `frontend/src/pages/Proration.tsx` -- merge logic (lines 676-687) and status icons (lines 1436-1439) inspected
- `backend/tests/test_fetch_missing.py` -- existing test coverage inspected
- `.planning/research/PITFALLS-V1.6.md` -- Pitfalls 4 and 9 directly relevant

### Secondary (MEDIUM confidence)
- asyncio.Semaphore documentation (stdlib, stable API)
- `run_in_executor` pattern for sync-in-async (well-established Python pattern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing code
- Architecture: HIGH -- patterns derived directly from reading existing code
- Pitfalls: HIGH -- identified from code inspection + PITFALLS-V1.6.md

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain, no external dependency changes)
