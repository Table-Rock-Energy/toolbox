# Phase 6: RRC & GHL Fixes - Research

**Researched:** 2026-03-13
**Domain:** RRC fetch-missing pipeline bug fixes + GHL UI label clarification
**Confidence:** HIGH

## Summary

Phase 6 addresses three RRC fetch-missing bugs and one GHL UI labeling issue. All five requirements are well-scoped bug fixes in existing code with clear before/after behavior. No new libraries or architectural changes are needed.

The RRC bugs stem from: (1) a re-lookup pattern where `fetch_individual_leases()` returns data that is ignored in favor of a redundant Firestore query, (2) missing logic to split compound lease numbers containing slashes or commas, and (3) no per-row status feedback to the user after fetch-missing completes. The GHL fix is a straightforward label rename in the send modal from "Campaign Name / SmartList Name" to "Campaign Tag" with an explanatory tooltip.

**Primary recommendation:** Fix the backend fetch-missing endpoint to use returned data directly, add lease number splitting before lookups, add per-row `fetch_status` field to the response, and rename the GHL modal field label. All changes are isolated to `backend/app/api/proration.py`, `backend/app/models/proration.py`, `frontend/src/pages/Proration.tsx`, `frontend/src/components/GhlSendModal.tsx`, and `backend/app/models/ghl.py`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RRC-01 | Fix fetch-missing to use returned data directly instead of re-looking up Firestore | Bug identified in `proration.py` lines 434-441: `individual_results` dict is fetched but then ignored in favor of re-querying Firestore |
| RRC-02 | Handle multi-lease numbers (slash/comma-separated) in fetch-missing lookups | No splitting logic exists anywhere in the fetch-missing code path; needs to be added before the lookup loop |
| RRC-03 | Surface fetch-missing results to user: found, not found, multiple matches per row | `FetchMissingResult` model only returns aggregate `matched_count`/`still_missing_count`; needs per-row `fetch_status` field |
| GHL-01 | Verify current GHL API v2 docs for SmartList/saved-search creation endpoints | Already verified out-of-scope per REQUIREMENTS.md: SmartLists are UI-only saved filters, not API-creatable |
| GHL-02 | Rename `smart_list_name` field to `campaign_name` with tooltip | `GhlSendModal.tsx` line 519 currently shows "Campaign Name" with misleading subtext about SmartLists; `BulkSendRequest` model has redundant `smart_list_name` field |
</phase_requirements>

## Standard Stack

No new libraries needed. All changes use existing stack components.

### Core (already in project)
| Library | Version | Purpose | Used For |
|---------|---------|---------|----------|
| FastAPI | 0.x | Backend API | `proration.py` fetch-missing endpoint |
| Pydantic | 2.x | Models | `FetchMissingResult`, `MineralHolderRow`, `BulkSendRequest` |
| React | 19.x | Frontend | `Proration.tsx`, `GhlSendModal.tsx` |
| TypeScript | 5.x | Frontend types | Interface updates |

## Architecture Patterns

### Current Fetch-Missing Flow (with bugs)

```
Frontend sends unmatched rows
  -> Backend: For each row, lookup Firestore (Step 1)
  -> Backend: For still-missing, call fetch_individual_leases() -> RRC HTML scrape -> upsert to Firestore
  -> Backend: BUG: Re-lookup Firestore AGAIN instead of using returned data  <-- RRC-01
  -> Backend: No multi-lease splitting                                        <-- RRC-02
  -> Backend: Returns aggregate counts only                                   <-- RRC-03
  -> Frontend: Merges updated rows into preview
```

### Fixed Fetch-Missing Flow

```
Frontend sends unmatched rows
  -> Backend: For each row, SPLIT compound lease numbers (slash/comma)        <-- RRC-02 fix
  -> Backend: For each row, lookup Firestore (Step 1)
  -> Backend: For still-missing, call fetch_individual_leases() -> RRC HTML scrape -> upsert to Firestore
  -> Backend: Use individual_results dict DIRECTLY to apply data              <-- RRC-01 fix
  -> Backend: Set per-row fetch_status: "found" | "not_found" | "multiple"   <-- RRC-03 fix
  -> Backend: Returns rows with per-row status
  -> Frontend: Merges updated rows, displays per-row feedback icons
```

### Anti-Patterns to Avoid
- **Double Firestore lookup:** Never re-query Firestore for data you already have in memory from `fetch_individual_leases()`. The individual results dict already contains `acres`, `type`, `operator`, `lease_name`.
- **Silently swallowing compound leases:** A lease number like "02-12345/02-12346" will never match a Firestore doc because no doc has that compound ID. Must split before lookup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lease splitting | Custom multi-format parser | Simple `re.split(r'[/,]', lease_str)` | Only two delimiters (slash, comma) are documented in requirements |
| Tooltip UI | Custom tooltip component | HTML `title` attribute or a small CSS tooltip | The GHL tooltip is a one-off; Tailwind `group`/`group-hover` pattern is sufficient |

## Common Pitfalls

### Pitfall 1: fetch_individual_leases returns keyed by (district, lease_number) but rows use different formats
**What goes wrong:** The `individual_results` dict is keyed by `(district, lease_number)` tuples. If splitting produces lease numbers with different formatting (leading zeros, whitespace), keys won't match.
**Why it happens:** `fetch_individual_leases` strips and zero-pads districts but lease numbers come back as-is from HTML parsing.
**How to avoid:** After splitting, strip whitespace and ensure consistent formatting before building lookup keys. The `_parse_rrc_html` function returns `lease_number` as the raw string from the HTML.
**Warning signs:** Rows show "not found" even though trace logs show the individual fetch succeeded.

### Pitfall 2: Splitting compound leases changes the row count
**What goes wrong:** If "02-12345/02-12346" is split into two leases, both map to the SAME row. The row needs to be enriched with the best match (e.g., highest acres), not duplicated.
**Why it happens:** One MineralHolderRow can reference multiple leases but only has one `rrc_acres` field.
**How to avoid:** Split lease numbers, look up each individually, then apply the best result (highest acres) back to the single row.

### Pitfall 3: Frontend merge key collisions
**What goes wrong:** The frontend merges updated rows by `owner|county|rrc_lease` key. If two rows have identical keys, one overwrites the other.
**Why it happens:** The merge uses a Map with composite string keys that aren't guaranteed unique.
**How to avoid:** The existing key strategy works for current data patterns. Adding `property_id` or index-based matching would be safer but is out of scope. Keep current key strategy unless bugs surface.

### Pitfall 4: GHL model backward compatibility
**What goes wrong:** Renaming `smart_list_name` in the Pydantic model breaks any clients sending the old field name.
**Why it happens:** The `BulkSendRequest.smart_list_name` field is used in the API contract.
**How to avoid:** The field already has `campaign_tag` as the primary field (line 106 of `ghl.py`). `smart_list_name` is optional and only used as a display label in `create_send_job`. Safe to deprecate or alias it.

## Code Examples

### RRC-01 Fix: Use individual_results directly (backend)

Current buggy code in `proration.py` lines 434-441:
```python
# BUG: re-queries Firestore instead of using individual_results
if individual_results:
    for row_idx, district, lease_number, _cc in missing_leases:
        row = updated_rows[row_idx]
        rrc_info = await lookup_rrc_acres(district, lease_number)     # redundant!
        if rrc_info is None:
            rrc_info = await lookup_rrc_by_lease_number(lease_number)  # redundant!
        if rrc_info:
            _apply_rrc_info(row, rrc_info, WellType)
            matched += 1
```

Fixed code:
```python
# Use individual_results directly — data is already in memory
if individual_results:
    for row_idx, district, lease_number, _cc in missing_leases:
        row = updated_rows[row_idx]
        rrc_info = individual_results.get((district, lease_number))
        if rrc_info:
            _apply_rrc_info(row, rrc_info, WellType)
            matched += 1
```

### RRC-02 Fix: Split compound lease numbers (backend)

Add before the main loop in `fetch_missing_rrc_data`:
```python
def split_lease_number(rrc_lease: str) -> list[str]:
    """Split compound lease numbers like '02-12345/02-12346' or '02-12345,02-12346'.

    Returns list of individual lease identifiers (district-lease format).
    """
    if not rrc_lease:
        return []
    parts = re.split(r'[/,]', rrc_lease)
    return [p.strip() for p in parts if p.strip()]
```

### RRC-03 Fix: Per-row fetch_status field

Add to `MineralHolderRow` model:
```python
fetch_status: Optional[str] = Field(
    None,
    description="Status from fetch-missing: found, not_found, multiple_matches, split_lookup"
)
```

Frontend display pattern:
```typescript
// In the row rendering, show icon based on fetch_status
{row.fetch_status === 'found' && <CheckCircle className="w-4 h-4 text-green-500" />}
{row.fetch_status === 'not_found' && <XCircle className="w-4 h-4 text-red-500" />}
{row.fetch_status === 'multiple_matches' && <AlertTriangle className="w-4 h-4 text-amber-500" />}
```

### GHL-02 Fix: Rename label and add tooltip

Current in `GhlSendModal.tsx` line 517-521:
```tsx
<label className="block text-sm font-medium text-gray-700 mb-1">
  Campaign Name
</label>
<p className="text-xs text-gray-500 mb-1">Used as the campaign tag and SmartList name</p>
```

Fixed:
```tsx
<label className="block text-sm font-medium text-gray-700 mb-1">
  Campaign Tag
  <span className="relative group ml-1 inline-block">
    <AlertCircle className="w-3.5 h-3.5 text-gray-400 inline" />
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
      To create a SmartList in GHL, filter contacts by this tag manually
    </span>
  </span>
</label>
```

## State of the Art

No ecosystem changes relevant. All fixes are internal bug fixes and UI label changes.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Re-lookup Firestore after individual fetch | Use returned data directly | This phase | Eliminates redundant Firestore reads, faster response |
| Single compound lease number lookup | Split and lookup each individually | This phase | Finds RRC data for previously unmatchable rows |
| Aggregate match counts only | Per-row fetch_status field | This phase | Users see exactly which rows found/not-found |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x with pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RRC-01 | fetch-missing uses individual_results directly, not re-query Firestore | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_uses_individual_results_directly -x` | No - Wave 0 |
| RRC-02 | Compound lease "02-12345/02-12346" split into two lookups | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_split_compound_lease_numbers -x` | No - Wave 0 |
| RRC-03 | Each row gets fetch_status: found, not_found, or multiple_matches | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_per_row_fetch_status -x` | No - Wave 0 |
| GHL-01 | SmartList not API-creatable (already documented, no code change) | manual-only | N/A - verified in requirements research | N/A |
| GHL-02 | GHL modal shows "Campaign Tag" label with tooltip | manual-only | Visual check in browser | N/A |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fetch_missing.py` -- covers RRC-01, RRC-02, RRC-03 (unit tests with mocked Firestore)
- [ ] Mock fixtures for `fetch_individual_leases` return values and Firestore lookup functions

## Open Questions

1. **Multiple matches for a single lease**
   - What we know: `fetch_individual_leases` can return multiple records for a single search (deduped by max acres in `_parse_rrc_html`). The `lookup_rrc_by_lease_number` sums acres across districts.
   - What's unclear: Should "multiple matches" mean multiple districts with different acres, or multiple records from the same HTML page?
   - Recommendation: Set `fetch_status = "multiple_matches"` when `lookup_rrc_by_lease_number` finds records in more than one district. The user should review these manually.

2. **Compound lease number format variations**
   - What we know: Requirements mention "02-12345/02-12346" format. The `rrc_lease` field stores "district-lease" format.
   - What's unclear: Are there other separator patterns (semicolons, spaces, "and")?
   - Recommendation: Start with slash and comma splitting only. Log unhandled patterns for future iteration.

## Sources

### Primary (HIGH confidence)
- Direct code analysis of `backend/app/api/proration.py` lines 333-478 (fetch-missing endpoint)
- Direct code analysis of `backend/app/services/proration/rrc_county_download_service.py` (fetch_individual_leases)
- Direct code analysis of `backend/app/services/firestore_service.py` lines 447-643 (lookup functions)
- Direct code analysis of `frontend/src/pages/Proration.tsx` (handleFetchMissing)
- Direct code analysis of `frontend/src/components/GhlSendModal.tsx` (send modal UI)
- Direct code analysis of `backend/app/models/ghl.py` (BulkSendRequest model)
- Direct code analysis of `backend/app/models/proration.py` (FetchMissingResult model)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing code
- Architecture: HIGH - bugs clearly identified in source code with line numbers
- Pitfalls: HIGH - based on direct code reading, not speculation

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable internal codebase, no external dependency concerns)
