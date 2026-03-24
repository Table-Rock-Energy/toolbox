# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- ✅ **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (shipped 2026-03-19)
- ✅ **v1.7 Batch Processing & Resilience** -- Phases 13-17 (shipped 2026-03-20)
- 🚧 **v1.8 Preview System Overhaul** -- Phases 18-21 (in progress)

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

<details>
<summary>v1.7 Batch Processing & Resilience (Phases 13-17) -- SHIPPED 2026-03-20</summary>

- [x] Phase 13: Operation Context & Batch Engine (2/2 plans) -- completed 2026-03-19
- [x] Phase 14: AI Cleanup Batching (2/2 plans) -- completed 2026-03-19
- [x] Phase 15: Operation Persistence UI (1/1 plan) -- completed 2026-03-20
- [x] Phase 16: Revenue Multi-PDF Streaming (2/2 plans) -- completed 2026-03-20
- [x] Phase 17: Proration Performance (2/2 plans) -- completed 2026-03-20

See: `.planning/milestones/v1.7-ROADMAP.md` for full details

</details>

### 🚧 v1.8 Preview System Overhaul (In Progress)

**Milestone Goal:** Fix the preview data pipeline so filtering, enrichment highlights, and export all stay consistent regardless of when filters are applied.

- [ ] **Phase 18: Key-Based Highlight Tracking** - Replace array-index highlight tracking with stable entry keys
- [ ] **Phase 19: Filter Correctness** - Filters work at any time without breaking highlights, enrichment scoped to visible rows, export respects filters
- [ ] **Phase 20: Preview UX Refinements** - Click-to-reveal changes, no-change indicators, enriched row tinting
- [ ] **Phase 21: Proration Enhancements** - Smarter RRC lookup strategy and fetch-missing stop button

## Phase Details

### Phase 18: Key-Based Highlight Tracking
**Goal**: Enrichment highlights stay aligned with the correct rows regardless of filtering or sorting
**Depends on**: Nothing (first phase of v1.8)
**Requirements**: PREV-01
**Success Criteria** (what must be TRUE):
  1. After enrichment, applying a filter does not cause green highlights to shift to wrong rows
  2. Sorting the table after enrichment preserves highlight alignment on the correct cells
  3. Highlights reference entry keys (_uid or entry_number), not positional array indices
**Plans**: TBD
**UI hint**: yes

### Phase 19: Filter Correctness
**Goal**: Users can filter at any time and get correct, consistent behavior across enrichment and export
**Depends on**: Phase 18
**Requirements**: FILT-01, FILT-02, FILT-03, FILT-04
**Success Criteria** (what must be TRUE):
  1. Entity type filter (Individual, Trust, LLC, etc.) correctly hides non-matching rows on Extract, Title, and all tool pages
  2. Applying or changing filters before, during, or after enrichment does not corrupt highlight alignment or lose data
  3. Running enrichment with a filter active processes only the visible/filtered rows (not the full dataset)
  4. Exporting with a filter active produces a file containing only the visible rows with all enrichment changes applied
**Plans**: TBD
**UI hint**: yes

### Phase 20: Preview UX Refinements
**Goal**: Users can visually distinguish enriched, changed, and unchanged rows at a glance and inspect individual changes
**Depends on**: Phase 18
**Requirements**: PREV-02, PREV-03, PREV-04
**Success Criteria** (what must be TRUE):
  1. Clicking a green (changed) cell reveals the original value so the user can confirm what changed
  2. Rows sent to enrichment that had no changes display a subtle checkmark indicator
  3. Rows with enrichment changes display a blue-tinted background; unenriched rows remain white
**Plans**: TBD
**UI hint**: yes

### Phase 21: Proration Enhancements
**Goal**: RRC lookups are faster and fetch-missing is stoppable
**Depends on**: Nothing (independent of Phases 18-20)
**Requirements**: PROR-01, PROR-02
**Success Criteria** (what must be TRUE):
  1. RRC lookup tries lease number only first; falls back to district+lease only when lease-only returns no results
  2. New RRC results from the optimized lookup are persisted to Firestore
  3. Fetch-missing modal has a stop button that finishes the current lookup, then stops and returns all results found so far
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 18 -> 19 -> 20 -> 21
(Phase 20 and 21 can execute in parallel since they are independent, but sequential is fine.)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 18. Key-Based Highlight Tracking | v1.8 | 0/TBD | Not started | - |
| 19. Filter Correctness | v1.8 | 0/TBD | Not started | - |
| 20. Preview UX Refinements | v1.8 | 0/TBD | Not started | - |
| 21. Proration Enhancements | v1.8 | 0/TBD | Not started | - |
