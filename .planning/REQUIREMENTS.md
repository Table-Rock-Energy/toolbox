# Requirements: Table Rock Tools

**Defined:** 2026-03-13
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results. Everything else is secondary to parsing accuracy and data integrity.

## v1.5 Requirements

Requirements for v1.5 Enrichment Pipeline & Bug Fixes. Each maps to roadmap phases.

### Extract (ECF Upload Flow)

- [x] **ECF-01**: When ECF format is auto-detected from uploaded PDF, system auto-selects ECF filing type in format dropdown
- [ ] **ECF-02**: After ECF detection, Convey 640 CSV upload area opens automatically before processing begins
- [ ] **ECF-03**: Processing waits for explicit "Process" button click (no auto-processing on file upload)
- [ ] **ECF-04**: CSV provides head-start data; PDF fills remaining fields and corrects inaccuracies from CSV (PDF is authoritative)

### GHL (Smart List Clarification)

- [ ] **GHL-01**: Verify current GHL API v2 docs for SmartList/saved-search creation endpoints
- [ ] **GHL-02**: Rename `smart_list_name` field to `campaign_name` with tooltip explaining SmartList is created manually in GHL filtered by this tag (pending GHL-01 verification)

### Enrichment Pipeline

- [x] **ENRICH-01**: Three conditional buttons shown across all tool pages: Clean Up, Validate, Enrich
- [x] **ENRICH-02**: Buttons visible only when corresponding API keys are set and feature switches enabled (Google API key + switches for Clean Up and Validate; PDL/SearchBug keys for Enrich)
- [x] **ENRICH-03**: Clean Up (AI) runs first: fix names, strip c/o from addresses, move extras to notes, attempt to complete partial entries
- [x] **ENRICH-04**: Validate (Google Maps) runs second: verify cleaned addresses, flag mismatches
- [x] **ENRICH-05**: Enrich (PDL/SearchBug) runs third: fill phone/email using clean validated addresses
- [x] **ENRICH-06**: After each enrichment step, preview table updates with enriched data visible to user
- [x] **ENRICH-07**: Flagged rows (validation mismatches) sort to top of preview for user review
- [x] **ENRICH-08**: User can uncheck flagged rows to omit from export, or edit inline to fix
- [x] **ENRICH-09**: Export always reflects current preview state (edits, unchecks, enrichment results)
- [x] **ENRICH-10**: AI cleanup service uses provider-agnostic LLM interface (Gemini now, Ollama/Qwen swappable via admin settings in v1.6)
- [ ] **ENRICH-11**: Tool-specific AI QA prompts: name cleanup for Extract/Title, figure verification for Revenue, address cleaning for all, overall accuracy check across both source files for ECF

### RRC/Proration

- [ ] **RRC-01**: Fix fetch-missing to use returned data directly instead of re-looking up Firestore
- [ ] **RRC-02**: Handle multi-lease numbers (slash/comma-separated) in fetch-missing lookups
- [ ] **RRC-03**: Surface fetch-missing results to user: found, not found, multiple matches per row

## Future Requirements

Deferred to v1.6 (On-Prem & ETL Pipeline).

### On-Prem Infrastructure
- **ONPREM-01**: Ubuntu server deployment with VM setup
- **ONPREM-02**: Bronze/silver/gold tiered database for ETL pipeline
- **ONPREM-03**: Local LLM (Ollama/Qwen) replaces Gemini via admin settings provider switch

### Deferred
- **DEFER-01**: Fuzzy name matching between PDF/CSV respondents
- **DEFER-02**: Frontend test suite
- **DEFER-03**: Rate limiting
- **DEFER-04**: Structured logging / request tracing

## Out of Scope

| Feature | Reason |
|---------|--------|
| GHL SmartList API creation | SmartLists are UI-only saved filters in GHL, not API-creatable (verified in research) |
| Bronze/silver/gold database tiers | Deferred to v1.6 on-prem milestone |
| Local LLM deployment (Ollama/Qwen) | v1.5 builds the abstraction layer; v1.6 adds the provider |
| Batch ECF processing (multiple filings) | One filing per upload is sufficient for current workflow |
| Enrichment progress via SSE | Simple loading states on buttons sufficient for sub-2-minute operations |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ECF-01 | Phase 5 | Complete |
| ECF-02 | Phase 5 | Pending |
| ECF-03 | Phase 5 | Pending |
| ECF-04 | Phase 5 | Pending |
| GHL-01 | Phase 6 | Pending |
| GHL-02 | Phase 6 | Pending |
| ENRICH-01 | Phase 7 | Complete |
| ENRICH-02 | Phase 7 | Complete |
| ENRICH-03 | Phase 8 | Complete |
| ENRICH-04 | Phase 8 | Complete |
| ENRICH-05 | Phase 8 | Complete |
| ENRICH-06 | Phase 8 | Complete |
| ENRICH-07 | Phase 7 | Complete |
| ENRICH-08 | Phase 7 | Complete |
| ENRICH-09 | Phase 7 | Complete |
| ENRICH-10 | Phase 8 | Complete |
| ENRICH-11 | Phase 9 | Pending |
| RRC-01 | Phase 6 | Pending |
| RRC-02 | Phase 6 | Pending |
| RRC-03 | Phase 6 | Pending |

**Coverage:**
- v1.5 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after plan revision (ENRICH-06 moved from Phase 7 to Phase 8)*
