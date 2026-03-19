# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- 🚧 **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (in progress)

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

### v1.6 Pipeline Fixes & Unified Enrichment (In Progress)

**Milestone Goal:** Fix RRC fetch-missing pipeline, harden admin/history auth, clean up GHL legacy fields, and replace 3-button enrichment with a single-button modal that runs all steps with real-time progress and live preview updates.

- [ ] **Phase 10: Auth Hardening & GHL Cleanup** - Secure admin/history endpoints and remove deprecated GHL smart_list_name field
- [x] **Phase 11: RRC Pipeline Fix** - Compound lease splitting, direct data use, per-row status feedback (completed 2026-03-18)
- [ ] **Phase 12: Unified Enrichment Modal** - Single-button modal replaces 3-button toolbar with sequential pipeline execution and live preview

## Phase Details

### Phase 10: Auth Hardening & GHL Cleanup
**Goal**: Admin settings and job history are properly authenticated, user-scoped, and the deprecated GHL field is removed
**Depends on**: Nothing (independent fixes)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, GHL-01, GHL-02
**Success Criteria** (what must be TRUE):
  1. Unauthenticated requests to admin GET endpoints (/options, /users, /settings/*) return 401
  2. The check_user endpoint still works without authentication (login flow unbroken)
  3. Non-admin users see only their own jobs in history; admin users see all jobs
  4. Deleting a job that belongs to another user returns 403 (unless requester is admin)
  5. The GHL send modal no longer shows or sends a smart_list_name field
**Plans:** 1/3 plans executed

Plans:
- [ ] 10-01-PLAN.md -- GHL smart_list_name removal (GHL-01, GHL-02)
- [ ] 10-02-PLAN.md -- Admin endpoint auth with per-endpoint Depends (AUTH-01, AUTH-02)
- [ ] 10-03-PLAN.md -- History user-scoping and delete ownership (AUTH-03, AUTH-04, AUTH-05)

### Phase 11: RRC Pipeline Fix
**Goal**: Fetch-missing correctly handles compound lease numbers and returns usable results directly
**Depends on**: Nothing (independent of Phase 10, but sequenced after for build order discipline)
**Requirements**: RRC-01, RRC-02, RRC-03
**Success Criteria** (what must be TRUE):
  1. Lease numbers with slashes or commas (e.g., "02-12345/12346") are split and each part is looked up individually with the district prefix inherited
  2. After fetch-missing completes, found RRC data appears in the proration table without a page reload or re-query
  3. Each row shows its fetch status: found, not found, or multiple matches
**Plans:** 1/1 plans complete

Plans:
- [ ] 11-01: Compound lease splitting with district inheritance + direct data use + per-row status UI (RRC-01, RRC-02, RRC-03)

### Phase 12: Unified Enrichment Modal
**Goal**: Users run all enrichment steps from a single button with real-time progress and live preview updates
**Depends on**: Phase 10 and Phase 11 (backend must be stable before building modal UX on top)
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06, ENRICH-07
**Success Criteria** (what must be TRUE):
  1. A single "Enrich" button replaces the 3-button toolbar on Extract, Title, Proration, and Revenue pages
  2. Clicking Enrich opens a modal that runs cleanup, validate, and enrich steps sequentially without user intervention
  3. The modal shows a progress bar with step labels and estimated time remaining
  4. As each step completes, the preview table behind the modal updates in real-time with the new data
  5. Modified cells are highlighted so the user can see exactly what changed after closing the modal
**Plans:** TBD

Plans:
- [ ] 12-01: useEnrichmentPipeline.runAllSteps() with local variable threading and AbortController (ENRICH-02, ENRICH-03, ENRICH-06)
- [ ] 12-02: EnrichmentModal component with progress UI, step labels, and ETA (ENRICH-01, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-07)

## Progress

**Execution Order:** Phases 10 and 11 are independent and can execute in parallel. Phase 12 depends on both completing first.

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
| 10. Auth Hardening & GHL Cleanup | 1/3 | In Progress|  | - |
| 11. RRC Pipeline Fix | 1/1 | Complete    | 2026-03-18 | - |
| 12. Unified Enrichment Modal | v1.6 | 0/2 | Not started | - |
