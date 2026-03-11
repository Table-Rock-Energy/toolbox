# Requirements: Table Rock Tools v1.4 ECF Extraction

**Defined:** 2026-03-11
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results.

## v1.4 Requirements

Requirements for ECF/Convey 640 extraction. Each maps to roadmap phases.

### ECF PDF Parsing

- [ ] **ECF-01**: User can upload an ECF PDF and extract numbered respondent entries (name + address)
- [ ] **ECF-02**: Parser correctly handles multi-line respondent names and addresses from PDF text
- [ ] **ECF-03**: Parser extracts case metadata from PDF header (county, legal description, applicant name, case number, well name)
- [ ] **ECF-04**: Entity type is detected for each respondent (Individual, Trust, LLC, Estate, Corporation, etc.)
- [ ] **ECF-05**: Format detector identifies ECF filings and routes to the correct parser

### Convey 640 Processing

- [ ] **CSV-01**: User can optionally upload a Convey 640 CSV or Excel file alongside the ECF PDF
- [ ] **CSV-02**: Parser strips entry line numbers from the name column and normalizes respondent names
- [ ] **CSV-03**: Parser preserves ZIP codes as strings (prevents float/NaN loss of leading zeros)
- [ ] **CSV-04**: Parser extracts metadata columns (county, STR, applicant, case number, classification)

### Merge Logic

- [ ] **MRG-01**: When both PDF and CSV are provided, merge uses PDF as source of truth for names and addresses
- [ ] **MRG-02**: CSV metadata (county, STR, case number) enriches the merged result
- [ ] **MRG-03**: Entries are matched between PDF and CSV by entry number
- [ ] **MRG-04**: Mismatched entry counts or unmatched entries are flagged for user review

### Export

- [ ] **EXP-01**: Merged results export to mineral export CSV format (MINERAL_EXPORT_COLUMNS)
- [ ] **EXP-02**: Merged results export to mineral export Excel format
- [ ] **EXP-03**: County, case number, applicant, and legal description populate appropriate mineral export fields

### Frontend

- [ ] **FE-01**: Extract page supports dual-file upload (PDF required, CSV/Excel optional) when ECF format is selected
- [ ] **FE-02**: Results table displays respondent entries with name, entity type, address, city, state, ZIP
- [ ] **FE-03**: Case metadata (county, case number, applicant, well name) displays above the results table
- [ ] **FE-04**: User can export results as mineral export CSV or Excel

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Matching

- **MATCH-01**: Fuzzy name matching between PDF and CSV respondents when entry numbers don't align
- **MATCH-02**: Manual match override UI for unmatched entries
- **MATCH-03**: Match confidence scoring with visual indicators

### Additional Formats

- **FMT-01**: Support for other OCC filing types beyond multiunit horizontal well applications
- **FMT-02**: Support for Convey 640 schema variations across different export versions

## Out of Scope

| Feature | Reason |
|---------|--------|
| AI-powered OCR correction | PDF text via PyMuPDF is sufficient for born-digital OCC filings |
| Automatic Convey 640 download | User provides the file manually — no scraping |
| Batch processing (multiple ECF filings) | One filing per upload, consistent with other tools |
| GoHighLevel direct send from ECF | Use existing GHL Prep workflow after mineral export |
| Address geocoding/validation | Defer to optional enrichment services |
| RRC data lookup for ECF respondents | RRC API is for proration, not contact extraction |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ECF-01 | — | Pending |
| ECF-02 | — | Pending |
| ECF-03 | — | Pending |
| ECF-04 | — | Pending |
| ECF-05 | — | Pending |
| CSV-01 | — | Pending |
| CSV-02 | — | Pending |
| CSV-03 | — | Pending |
| CSV-04 | — | Pending |
| MRG-01 | — | Pending |
| MRG-02 | — | Pending |
| MRG-03 | — | Pending |
| MRG-04 | — | Pending |
| EXP-01 | — | Pending |
| EXP-02 | — | Pending |
| EXP-03 | — | Pending |
| FE-01 | — | Pending |
| FE-02 | — | Pending |
| FE-03 | — | Pending |
| FE-04 | — | Pending |

**Coverage:**
- v1.4 requirements: 20 total
- Mapped to phases: 0
- Unmapped: 20

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after initial definition*
