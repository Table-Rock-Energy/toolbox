# Phase 17: Proration Performance - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Proration lookups are fast from first request and scale with row count. Cache-first architecture with startup pre-warming, batch Firestore reads, and cache invalidation after RRC sync.

Requirements: PERF-01, PERF-02, PERF-03, PERF-04

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `rrc_data_service.py` — Bulk RRC download with pandas DataFrame caching
- `csv_processor.py` — In-memory pandas lookup for proration data
- `firestore_service.py` — Firestore CRUD with batch operations (500-doc limit)
- `rrc_background.py` — Background RRC download worker with Firestore job tracking

### Established Patterns
- pandas DataFrame cached in memory after first load
- Firestore batch reads/writes with 500-doc commit limit
- asyncio.to_thread for CPU-bound operations
- Background task pattern with separate synchronous Firestore client

### Integration Points
- `backend/app/services/proration/csv_processor.py` — Cache-first lookup
- `backend/app/services/proration/rrc_data_service.py` — DataFrame pre-warming
- `backend/app/services/firestore_service.py` — Batch reads via asyncio.gather
- `backend/app/main.py` — Startup hooks for pre-warming

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>

---

*Phase: 17-proration-performance*
*Context gathered: 2026-03-20*
