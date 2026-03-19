# Requirements: Table Rock Tools

**Defined:** 2026-03-19
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results.

## v1.7 Requirements

Requirements for v1.7 Batch Processing & Resilience. Each maps to roadmap phases.

### Batch Processing

- [ ] **BATCH-01**: User sees AI cleanup process entries in batches of 25 with per-batch progress
- [ ] **BATCH-02**: User sees ETA for remaining batches based on first-batch timing
- [ ] **BATCH-03**: User can configure batch size per tool via admin settings
- [ ] **BATCH-04**: System runs multiple batches concurrently when Gemini rate limits allow

### Operation Resilience

- [ ] **RESIL-01**: All fetch requests use AbortController and cancel on component unmount
- [ ] **RESIL-02**: Backend stops Gemini processing when client disconnects (request.is_disconnected)
- [ ] **RESIL-03**: User receives partial results when a batch fails (successful batches preserved)
- [ ] **RESIL-04**: System automatically retries failed batches up to a configurable limit

### Operation Persistence

- [ ] **PERSIST-01**: Active operations continue when user navigates between pages
- [ ] **PERSIST-02**: User sees active operation status bar in MainLayout header
- [ ] **PERSIST-03**: User can return to a tool page and see results from an operation that completed while away

### Proration Performance

- [ ] **PERF-01**: Proration lookups check in-memory cache before Firestore
- [ ] **PERF-02**: RRC DataFrame cache pre-warms on application startup
- [ ] **PERF-03**: Proration Firestore reads use asyncio.gather for parallel execution
- [ ] **PERF-04**: In-memory cache updates when background RRC sync completes

### Revenue Streaming

- [ ] **REV-01**: User sees per-PDF progress during multi-PDF revenue upload via SSE

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Optimization

- **OPT-01**: Gemini response caching keyed on input hash to avoid duplicate API calls
- **OPT-02**: Smart diffing — skip unchanged entries on re-run

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Server-side job queue (Celery/Redis) | Overkill for small internal team; React Context sufficient |
| Zustand/Redux global state | React Context above Router handles the scope needed |
| WebSocket streaming | SSE and NDJSON already proven in codebase, simpler |
| Frontend test suite | Deferred from v1.6, not part of this milestone |
| Per-PDF cancel/retry in revenue | Nice-to-have, defer to v1.8 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BATCH-01 | Phase 13 | Pending |
| BATCH-02 | Phase 13 | Pending |
| BATCH-03 | Phase 14 | Pending |
| BATCH-04 | Phase 14 | Pending |
| RESIL-01 | Phase 13 | Pending |
| RESIL-02 | Phase 14 | Pending |
| RESIL-03 | Phase 13 | Pending |
| RESIL-04 | Phase 14 | Pending |
| PERSIST-01 | Phase 13 | Pending |
| PERSIST-02 | Phase 15 | Pending |
| PERSIST-03 | Phase 15 | Pending |
| PERF-01 | Phase 17 | Pending |
| PERF-02 | Phase 17 | Pending |
| PERF-03 | Phase 17 | Pending |
| PERF-04 | Phase 17 | Pending |
| REV-01 | Phase 16 | Pending |

**Coverage:**
- v1.7 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-19*
*Last updated: 2026-03-19 after roadmap creation*
