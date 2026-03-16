# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- 🚧 **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (in progress)

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

### v1.5 Enrichment Pipeline & Bug Fixes (In Progress)

**Milestone Goal:** Fix broken enrichment/validation flows, add universal 3-button post-processing UI across all tools, fix ECF upload UX, and repair RRC fetch-missing pipeline.

- [ ] **Phase 5: ECF Upload Flow Fix** - Auto-detect ECF format, defer processing until user clicks Process
- [ ] **Phase 6: RRC & GHL Fixes** - Repair fetch-missing pipeline and clarify GHL campaign tagging
- [ ] **Phase 7: Enrichment UI & Preview State** - Shared post-processing buttons, preview table as single source of truth for exports
- [x] **Phase 8: Enrichment Pipeline Features** - Wire AI cleanup, address validation, and contact enrichment through the universal UI (completed 2026-03-16)
- [ ] **Phase 9: Tool-Specific AI Prompts** - Per-tool Gemini QA prompts for name cleanup, figure verification, and accuracy checks

## Phase Details

### Phase 5: ECF Upload Flow Fix
**Goal**: Users can upload ECF filings with the correct format pre-selected and optional CSV added before processing begins
**Depends on**: Nothing (independent bug fix)
**Requirements**: ECF-01, ECF-02, ECF-03, ECF-04
**Success Criteria** (what must be TRUE):
  1. When user uploads a PDF that is auto-detected as ECF format, the format dropdown switches to "ECF Filing" without user intervention
  2. After ECF detection, the Convey 640 CSV upload area appears automatically so user can optionally add CSV before processing
  3. No processing occurs until user explicitly clicks the Process button (uploading a file alone does not trigger extraction)
  4. When both PDF and CSV are provided, the merged results show PDF-corrected data with CSV head-start fields filled in
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md -- Backend detect-format endpoint + tests (ECF-01)
- [ ] 05-02-PLAN.md -- Frontend staged upload flow with Process button (ECF-02, ECF-03, ECF-04)

### Phase 6: RRC & GHL Fixes
**Goal**: Users get usable results from RRC fetch-missing and understand how GHL campaign tagging works
**Depends on**: Nothing (independent bug fixes)
**Requirements**: RRC-01, RRC-02, RRC-03, GHL-01, GHL-02
**Success Criteria** (what must be TRUE):
  1. When fetch-missing completes, found RRC data appears directly in the proration preview without requiring a page reload or second lookup
  2. Lease numbers containing slashes or commas (e.g., "02-12345/02-12346") are split and each lease is looked up individually
  3. After fetch-missing, user sees clear feedback per row: found, not found, or multiple matches
  4. The GHL send modal shows "Campaign Tag" (not "SmartList Name") with a tooltip explaining that SmartLists are created manually in GHL filtered by this tag
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md -- Fix RRC fetch-missing pipeline: direct data use, compound lease splitting, per-row status (RRC-01, RRC-02, RRC-03)
- [ ] 06-02-PLAN.md -- Rename GHL Campaign Tag label with tooltip, deprecate smart_list_name (GHL-01, GHL-02)

### Phase 7: Enrichment UI & Preview State
**Goal**: Users see three conditional enrichment buttons across all tool pages, and the preview table becomes the single source of truth for exports
**Depends on**: Nothing (can start in parallel with 5-6, but sequencing after them is preferred)
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-07, ENRICH-08, ENRICH-09
**Success Criteria** (what must be TRUE):
  1. Clean Up, Validate, and Enrich buttons appear on Extract, Title, Proration, and Revenue pages when their corresponding API keys and feature switches are configured
  2. Buttons are hidden when their required API keys or feature switches are missing (no broken buttons visible to users)
  3. Rows flagged during enrichment (e.g., validation mismatches) sort to the top of the preview table for user review
  4. User can uncheck flagged rows to omit them from export, edit cells inline, and export always reflects the current preview state (edits + unchecks + enrichment results)
  5. Infrastructure for preview-table-updates-after-enrichment is in place (updateEntries method) -- actual enrichment data flow delivered in Phase 8 (ENRICH-06)
**Plans**: 3 plans

Plans:
- [ ] 07-01-PLAN.md -- Backend feature status endpoint + EnrichmentToolbar component + useFeatureFlags hook (ENRICH-01, ENRICH-02)
- [ ] 07-02-PLAN.md -- usePreviewState hook + EditableCell component (ENRICH-07, ENRICH-08, ENRICH-09)
- [ ] 07-03-PLAN.md -- Wire shared components into all 4 tool pages (ENRICH-01, ENRICH-02, ENRICH-07, ENRICH-08, ENRICH-09)

### Phase 8: Enrichment Pipeline Features
**Goal**: Users can run AI cleanup, address validation, and contact enrichment in sequence through the universal enrichment buttons
**Depends on**: Phase 7 (enrichment UI must exist)
**Requirements**: ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06, ENRICH-10
**Success Criteria** (what must be TRUE):
  1. Clean Up button sends entries to AI service which fixes names, strips c/o from addresses, moves extras to notes, and attempts to complete partial entries -- results appear in preview
  2. Validate button sends cleaned entries to Google Maps address validation and flags mismatches -- flagged rows sort to top
  3. Enrich button sends validated entries to PDL/SearchBug and fills phone/email fields -- results appear in preview
  4. After each enrichment step completes, the preview table immediately reflects the updated data without page reload (ENRICH-06 -- uses updateEntries infrastructure from Phase 7)
  5. AI cleanup service uses a provider-agnostic LLM interface so Gemini can be swapped for Ollama/Qwen in v1.6 via admin settings without code changes
**Plans**: 3 plans

Plans:
- [x] 08-01-PLAN.md -- LLM protocol + pipeline API endpoints (cleanup, validate, enrich) with unified ProposedChange format (ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-10)
- [x] 08-02-PLAN.md -- Frontend useEnrichmentPipeline hook, ProposedChangesPanel, wire into all 4 tool pages (ENRICH-06)
- [ ] 08-03-PLAN.md -- Gap closure: wire recentlyAppliedKeys green row highlight into all 4 tool pages (ENRICH-06)

### Phase 9: Tool-Specific AI Prompts
**Goal**: Each tool gets tailored AI QA prompts that leverage tool-specific data patterns for better cleanup and validation
**Depends on**: Phase 8 (AI cleanup must be functional)
**Requirements**: ENRICH-11
**Success Criteria** (what must be TRUE):
  1. Extract and Title tools use name-focused cleanup prompts (fix casing, standardize suffixes, detect entity types from name patterns)
  2. Revenue tool uses figure-verification prompts (cross-check amounts, flag outliers, validate decimal positions)
  3. ECF tool uses cross-file accuracy prompts (compare PDF-extracted vs CSV-provided data, flag discrepancies between sources)
**Plans**: TBD

Plans:
- [ ] 09-01: TBD

## Progress

**Execution Order:** Phases 5 and 6 are independent and can execute in parallel. Phases 7-9 are sequential.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Auth Enforcement & CORS | v1.3 | 2/2 | Complete | 2026-03-11 |
| 2. Encryption Hardening | v1.3 | 2/2 | Complete | 2026-03-11 |
| 3. Backend Test Suite | v1.3 | 2/2 | Complete | 2026-03-11 |
| 1. ECF PDF Parsing | v1.4 | 2/2 | Complete | 2026-03-12 |
| 2. Convey 640 Processing | v1.4 | 1/1 | Complete | 2026-03-12 |
| 3. Merge and Export | v1.4 | 2/2 | Complete | 2026-03-12 |
| 4. Frontend Integration | v1.4 | 2/2 | Complete | 2026-03-11 |
| 5. ECF Upload Flow Fix | 1/2 | In Progress|  | - |
| 6. RRC & GHL Fixes | v1.5 | 0/2 | Planning complete | - |
| 7. Enrichment UI & Preview State | 2/3 | In Progress|  | - |
| 8. Enrichment Pipeline Features | 3/3 | Complete   | 2026-03-16 | - |
| 9. Tool-Specific AI Prompts | v1.5 | 0/? | Not started | - |
