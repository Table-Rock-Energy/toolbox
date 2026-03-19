# Phase 11: RRC Pipeline Fix - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the fetch-missing pipeline so compound lease numbers are split and looked up individually, results are returned directly to the frontend without re-querying Firestore, and each row shows its fetch status. Requirements: RRC-01, RRC-02, RRC-03.

</domain>

<decisions>
## Implementation Decisions

### Compound Lease Splitting
- Split on `/` and `,` delimiters (already what `split_lease_number()` does)
- District inheritance: if first sub-lease has a district prefix (e.g., "02-12345"), propagate that district to subsequent parts that lack one (e.g., "12346" becomes "02-12346"). Fall back to `row.district` if first part also lacks a prefix.
- Preserve the original `rrc_lease` string on the row. Matched sub-lease details go in a separate annotation field (not overwriting the original).
- When multiple sub-leases return different RRC data, return all as separate matches attached to the row (don't pick one or aggregate).

### Direct Data Use
- fetch-missing API response includes full matched RRC fields (acres, allowable, etc.) per row
- Frontend merges RRC data into existing table rows in-place (patch RRC columns, preserve user edits to non-RRC fields, highlight changed cells)
- Background persist: return data to frontend immediately, write to Firestore via BackgroundTask so the cache is warm for future lookups

### Per-Row Status Feedback
- Compound leases that have at least one sub-lease match show `split_lookup` status (green check, already wired in frontend)
- Compound leases where ALL sub-leases miss show regular `not_found` (no new status value needed)
- Sub-lease breakdown visible via tooltip on the status icon: "02-12345 found (240 acres), 12346 not found"
- No expandable sub-rows or inline detail — tooltip is sufficient

### Rate Limit Budget
- Expand all compound leases BEFORE the cap check (split first, deduplicate, then count)
- Remove the hard cap (MAX_INDIVIDUAL_QUERIES). Instead, use concurrency-limited throttling: max 8 concurrent HTML scrape requests at a time, queue the rest
- No absolute max on total queries — process all expanded leases at the concurrency limit
- `asyncio.Semaphore(8)` pattern for throttling concurrent RRC HTML requests

### Claude's Discretion
- Exact asyncio semaphore implementation pattern
- How to structure the sub-lease results annotation field in the response model
- Tooltip rendering approach for sub-lease breakdown
- BackgroundTask implementation for Firestore persist

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### RRC Pipeline
- `.planning/REQUIREMENTS.md` — RRC-01, RRC-02, RRC-03 requirement definitions
- `.planning/research/PITFALLS-V1.6.md` — Pitfalls 4 (compound lease splitting), 9 (rate limit budget)

### Existing Implementation
- `backend/app/api/proration.py` — `split_lease_number()` at line 41, `fetch_missing_rrc_data()` at line 343
- `backend/app/models/proration.py` — `fetch_status` field definition
- `frontend/src/pages/Proration.tsx` — fetch-missing call, status icon rendering, result merging logic

### Prior Phase
- `.planning/phases/06-rrc-ghl-fixes/06-01-PLAN.md` — Phase 6 RRC fixes context

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `split_lease_number()` (proration.py:41): Already splits on `/` and `,`, returns list of strings. Needs district inheritance logic added.
- Frontend status icons (Proration.tsx:1436-1439): Already renders found/not_found/multiple_matches/split_lookup with appropriate icons and colors.
- Frontend result merge (Proration.tsx:678-685): Merges by `owner|county|rrc_lease` key. Works for direct data use.
- `BackgroundTasks` already used in the fetch-missing endpoint signature.

### Established Patterns
- RRC HTML scraping via `rrc_county_download_service.py` with custom SSL adapter
- Firestore batch writes commit every 500 docs
- Frontend uses `fetch()` with `API_BASE` for proration endpoints

### Integration Points
- `split_lease_number()` must be called inside the fetch-missing loop at ~line 382 when `rrc_lease` contains `/` or `,`
- Response model (`FetchMissingResult`) needs sub-lease detail field for tooltip data
- Frontend merge logic needs to handle in-place RRC field updates without losing user edits
- Semaphore-based concurrency replaces the current `MAX_INDIVIDUAL_QUERIES` cap

</code_context>

<specifics>
## Specific Ideas

- Concurrency throttling modeled after FTP max-connections pattern: collect all queries, drip them out max 8 at a time instead of hard-capping at 25
- "Like when I do FTP connections I keep it max 8 at once so I don't overrun the server"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-rrc-pipeline-fix*
*Context gathered: 2026-03-18*
