# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- ✅ **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (shipped 2026-03-19)
- **v1.7 Batch Processing & Resilience** -- Phases 13-17 (in progress)

## Phases

<details>
<summary>v1.3 Security Hardening (Phases 1-3) -- SHIPPED 2026-03-11</summary>

- [x] Phase 1: Auth Enforcement & CORS Lockdown (2/2 plans) -- completed 2026-03-11
- [x] Phase 2: Encryption Hardening (2/2 plans) -- completed 2026-03-11
- [x] Phase 3: Backend Test Suite (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.3-ROADMAP.md` for full details

</details>

<details>
<summary>v1.4 ECF Extraction (Phases 1-4) -- SHIPPED 2026-03-12</summary>

- [x] Phase 1: ECF PDF Parsing (2/2 plans) -- completed 2026-03-12
- [x] Phase 2: Convey 640 Processing (1/1 plan) -- completed 2026-03-12
- [x] Phase 3: Merge and Export (2/2 plans) -- completed 2026-03-12
- [x] Phase 4: Frontend Integration (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.4-ROADMAP.md` for full details

</details>

<details>
<summary>v1.5 Enrichment Pipeline & Bug Fixes (Phases 5-9) -- SHIPPED 2026-03-17</summary>

- [x] Phase 5: ECF Upload Flow Fix (2/2 plans) -- completed 2026-03-14
- [x] Phase 6: RRC & GHL Fixes (2/2 plans) -- completed 2026-03-14
- [x] Phase 7: Enrichment UI & Preview State (3/3 plans) -- completed 2026-03-15
- [x] Phase 8: Enrichment Pipeline Features (3/3 plans) -- completed 2026-03-16
- [x] Phase 9: Tool-Specific AI Prompts (2/2 plans) -- completed 2026-03-17

See: `.planning/milestones/v1.5-ROADMAP.md` for full details

</details>

<details>
<summary>v1.6 Pipeline Fixes & Unified Enrichment (Phases 10-12) -- SHIPPED 2026-03-19</summary>

- [x] Phase 10: Auth Hardening & GHL Cleanup (3/3 plans) -- completed 2026-03-19
- [x] Phase 11: RRC Pipeline Fix (1/1 plan) -- completed 2026-03-18
- [x] Phase 12: Unified Enrichment Modal (2/2 plans) -- completed 2026-03-19

See: `.planning/milestones/v1.6-ROADMAP.md` for full details

</details>

### v1.7 Batch Processing & Resilience

- [x] **Phase 13: Operation Context & Batch Engine** - Global operation state and client-side batch orchestration foundation (completed 2026-03-19)
- [x] **Phase 14: AI Cleanup Batching** - Wire batch engine into enrichment pipeline with cancel and retry (completed 2026-03-19)
- [x] **Phase 15: Operation Persistence UI** - Status bar and result recovery across navigation (completed 2026-03-20)
- [ ] **Phase 16: Revenue Multi-PDF Streaming** - Per-PDF SSE progress for revenue uploads
- [ ] **Phase 17: Proration Performance** - Cache-first lookups, pre-warming, and parallel Firestore reads

## Phase Details

### Phase 13: Operation Context & Batch Engine
**Goal**: Operations have a place to live that survives navigation, and batch processing has an engine
**Depends on**: Phase 12
**Requirements**: PERSIST-01, BATCH-01, BATCH-02, RESIL-01, RESIL-03
**Success Criteria** (what must be TRUE):
  1. User can navigate away from a tool page and the active operation continues running
  2. User sees AI cleanup processing entries in batches with a progress indicator showing batch N of M
  3. User sees an ETA for remaining batches that updates after each batch completes
  4. If a batch fails mid-run, user receives all results from previously successful batches
  5. Navigating away from a page cancels any pending fetch requests (no orphaned connections)
**Plans**: 1 plan

Plans:
- [ ] 13-01-PLAN.md — OperationContext provider with batch-aware pipeline engine
- [ ] 13-02-PLAN.md — Tool page refactor and EnrichmentModal batch progress

### Phase 14: AI Cleanup Batching
**Goal**: AI cleanup is configurable, concurrent, cancellable, and retries failed work
**Depends on**: Phase 13
**Requirements**: BATCH-03, BATCH-04, RESIL-02, RESIL-04
**Success Criteria** (what must be TRUE):
  1. Admin can configure batch size per tool in admin settings
  2. System sends multiple batch requests concurrently when Gemini rate limits allow
  3. When user cancels an in-flight operation, backend stops Gemini processing within one batch cycle
  4. Failed batches are automatically retried up to the configured limit before returning partial results
**Plans**: 1 plan

Plans:
- [ ] 14-01-PLAN.md — Backend batch config, concurrency, thread safety, disconnect detection
- [ ] 14-02-PLAN.md — Frontend dynamic batch size, retry logic, admin UI controls

### Phase 15: Operation Persistence UI
**Goal**: Users always know what operations are running and can recover results after navigating away
**Depends on**: Phase 13
**Requirements**: PERSIST-02, PERSIST-03
**Success Criteria** (what must be TRUE):
  1. User sees a status bar in the header showing active operations with tool name and progress
  2. User can navigate to another page, return to the tool, and see results from an operation that completed while away
  3. Status bar clears completed operations after user has viewed the results
**Plans**: 1 plan

Plans:
- [ ] 15-01-PLAN.md — Status bar component, MainLayout integration, and auto-restore clearing

### Phase 16: Revenue Multi-PDF Streaming
**Goal**: Revenue multi-PDF uploads show per-file progress instead of blocking with no feedback
**Depends on**: Phase 12
**Requirements**: REV-01
**Success Criteria** (what must be TRUE):
  1. User sees progress update for each PDF as it completes during a multi-PDF revenue upload
  2. User sees which PDF is currently being processed and how many remain
**Plans**: 1 plan

Plans:
- [ ] 16-01-PLAN.md — NDJSON streaming endpoint + frontend progress UI

### Phase 17: Proration Performance
**Goal**: Proration lookups are fast from first request and scale with row count
**Depends on**: Phase 12
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04
**Success Criteria** (what must be TRUE):
  1. First proration upload after server start returns results without a cold-cache delay
  2. Proration lookups check in-memory DataFrame before hitting Firestore
  3. Proration upload with 200 rows completes noticeably faster than sequential per-row Firestore reads
  4. After a background RRC sync completes, subsequent proration lookups use the fresh data without restart
**Plans**: 1 plan

Plans:
- [ ] 17-01: TBD

## Progress

**Execution Order:**
Phases 13 and 14 are sequential. Phases 15, 16, 17 can run after 13 completes (15 depends on 13; 16 and 17 are independent).

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Auth Enforcement & CORS | v1.3 | 2/2 | Complete | 2026-03-11 |
| 2. Encryption Hardening | v1.3 | 2/2 | Complete | 2026-03-11 |
| 3. Backend Test Suite | v1.3 | 2/2 | Complete | 2026-03-11 |
| 1. ECF PDF Parsing | v1.4 | 2/2 | Complete | 2026-03-12 |
| 2. Convey 640 Processing | v1.4 | 1/1 | Complete | 2026-03-12 |
| 3. Merge and Export | v1.4 | 2/2 | Complete | 2026-03-12 |
| 4. Frontend Integration | v1.4 | 2/2 | Complete | 2026-03-11 |
| 5. ECF Upload Flow Fix | v1.5 | 2/2 | Complete | 2026-03-14 |
| 6. RRC & GHL Fixes | v1.5 | 2/2 | Complete | 2026-03-14 |
| 7. Enrichment UI & Preview State | v1.5 | 3/3 | Complete | 2026-03-15 |
| 8. Enrichment Pipeline Features | v1.5 | 3/3 | Complete | 2026-03-16 |
| 9. Tool-Specific AI Prompts | v1.5 | 2/2 | Complete | 2026-03-17 |
| 10. Auth Hardening & GHL Cleanup | v1.6 | 3/3 | Complete | 2026-03-19 |
| 11. RRC Pipeline Fix | v1.6 | 1/1 | Complete | 2026-03-18 |
| 12. Unified Enrichment Modal | v1.6 | 2/2 | Complete | 2026-03-19 |
| 13. Operation Context & Batch Engine | 2/2 | Complete    | 2026-03-19 | - |
| 14. AI Cleanup Batching | 2/2 | Complete    | 2026-03-19 | - |
| 15. Operation Persistence UI | 1/1 | Complete    | 2026-03-20 | - |
| 16. Revenue Multi-PDF Streaming | v1.7 | 0/? | Not started | - |
| 17. Proration Performance | v1.7 | 0/? | Not started | - |
