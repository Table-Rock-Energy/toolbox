# Roadmap: Table Rock Tools v1.4 ECF Extraction

## Milestones

- ✅ **v1.3 Security Hardening** — Phases 1-3 (shipped 2026-03-11)
- 🚧 **v1.4 ECF Extraction** — Phases 1-4 (in progress)

Add ECF/Convey 640 as a new extraction format within the existing Extract tool. The build validates PDF parsing independently (Phase 1), adds CSV processing (Phase 2), integrates merge logic with export (Phase 3), then wires up the frontend (Phase 4). Each phase delivers a testable capability via Swagger before the next begins.

## Phases

<details>
<summary>✅ v1.3 Security Hardening (Phases 1-3) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Auth Enforcement & CORS Lockdown (2/2 plans) — completed 2026-03-11
- [x] Phase 2: Encryption Hardening (2/2 plans) — completed 2026-03-11
- [x] Phase 3: Backend Test Suite (2/2 plans) — completed 2026-03-11

See: `.planning/milestones/v1.3-ROADMAP.md` for full details

</details>

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: ECF PDF Parsing** - Parse ECF Exhibit A respondent lists from OCC multiunit well application PDFs with entity detection and case metadata
- [x] **Phase 2: Convey 640 Processing** - Parse optional Convey 640 CSV/Excel files with name normalization and ZIP code preservation
- [ ] **Phase 3: Merge and Export** - Combine PDF-authoritative respondent data with CSV metadata and export to mineral format
- [x] **Phase 4: Frontend Integration** - Dual-file upload UI in Extract page with metadata display and mineral export (completed 2026-03-11)

## Phase Details

### Phase 1: ECF PDF Parsing
**Goal**: Users can upload an ECF PDF and get accurately parsed respondent data with case metadata, without needing any CSV file
**Depends on**: Nothing (first phase)
**Requirements**: ECF-01, ECF-02, ECF-03, ECF-04, ECF-05
**Success Criteria** (what must be TRUE):
  1. User uploads an ECF PDF via `/api/extract/upload` and receives a list of numbered respondent entries with parsed name and address fields
  2. Multi-line respondent names and addresses are correctly preserved (no name fragments bleeding into address or vice versa)
  3. Case metadata (county, legal description, applicant name, case number, well name) is extracted from the PDF header and returned in the response
  4. Each respondent has an entity type assigned (Individual, Trust, LLC, Estate, Corporation, etc.) with deceased parties classified as Estate
  5. Format detector identifies ECF filings distinctly from existing OCC Exhibit A format and routes to the ECF parser
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md -- ECF parser module, CaseMetadata model, format enum, and test suite
- [ ] 01-02-PLAN.md -- API endpoint routing, export address filtering, and integration tests

### Phase 2: Convey 640 Processing
**Goal**: Users can upload a Convey 640 CSV or Excel file and get clean, normalized respondent and metadata records
**Depends on**: Nothing (independent of Phase 1; can run in parallel)
**Requirements**: CSV-01, CSV-02, CSV-03, CSV-04
**Success Criteria** (what must be TRUE):
  1. User uploads a Convey 640 CSV or Excel file and receives parsed respondent rows with names stripped of entry line numbers
  2. ZIP codes with leading zeros (e.g., 02101 for Massachusetts) are preserved as strings in the parsed output
  3. Metadata columns (county, section-township-range, applicant, case number, classification) are extracted and returned separately from respondent data
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md -- Convey 640 parser with name normalization pipeline, ZIP preservation, metadata extraction, and TDD test suite

### Phase 3: Merge and Export
**Goal**: When both PDF and CSV are provided, the system merges them with PDF as source of truth and exports to mineral format with maximum field coverage
**Depends on**: Phase 1, Phase 2
**Requirements**: MRG-01, MRG-02, MRG-03, MRG-04, EXP-01, EXP-02, EXP-03
**Success Criteria** (what must be TRUE):
  1. When PDF and CSV are both provided, merged output uses PDF names and addresses (not CSV values that may contain OCR errors)
  2. CSV metadata (county, STR, case number) appears in the merged result even when the PDF header extraction is incomplete
  3. Entries are matched by entry number, and mismatched counts or unmatched entries are flagged with warnings in the response
  4. Merged results export to mineral export CSV and Excel formats with county, case number, applicant, and legal description populating the appropriate columns
  5. PDF-only mode (no CSV) still produces a valid mineral export with whatever metadata the PDF header provides
**Plans**: 1 plan

Plans:
- [ ] 03-01: Merge service with entry-number matching and PDF precedence rules
- [ ] 03-02: Mineral export mapping for ECF metadata fields

### Phase 4: Frontend Integration
**Goal**: Users can upload ECF PDFs (with optional CSV) through the Extract UI and view, review, and export respondent data
**Depends on**: Phase 3
**Requirements**: FE-01, FE-02, FE-03, FE-04
**Success Criteria** (what must be TRUE):
  1. Extract page shows a dual-file upload when ECF format is selected: PDF upload is required, CSV/Excel upload is optional
  2. Results table displays respondent entries with name, entity type, address, city, state, and ZIP columns
  3. Case metadata (county, case number, applicant, well name) displays above the results table in a summary panel
  4. User can export results as mineral export CSV or Excel using the existing export buttons
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md -- ECF format option, dual-file upload, CaseMetadata types
- [x] 04-02-PLAN.md -- Case metadata panel, mineral export modal wiring, visual verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4
(Phases 1 and 2 may execute in parallel since they are independent)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. ECF PDF Parsing | 0/2 | Not started | - |
| 2. Convey 640 Processing | 1/1 | Complete | 2026-03-12 |
| 3. Merge and Export | 0/2 | Not started | - |
| 4. Frontend Integration | 2/2 | Complete   | 2026-03-11 |
