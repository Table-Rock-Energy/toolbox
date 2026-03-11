# Feature Landscape: ECF/Convey 640 Extraction

**Domain:** OCC multiunit horizontal well application processing with optional CSV/Excel data merge
**Researched:** 2026-03-11

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ECF PDF text extraction | Core functionality — PDF is authoritative data source | Low | Reuses existing PyMuPDF extraction from Extract tool |
| Respondent name parsing | Expected from existing Extract tool (OCC Exhibit A) | Low | Reuses existing name_parser.py infrastructure |
| Respondent address parsing | Expected from existing Extract tool | Low | Reuses existing address_parser.py infrastructure |
| Entity type detection | Expected from existing Extract tool | Low | Reuses existing entity_detector.py patterns |
| Numbered entry extraction | Respondent lists are numbered 1, 2, 3... in ECF filings | Medium | New pattern — numbered list with name + address blocks |
| PDF header metadata extraction | County, legal description, applicant, case number visible in header | Medium | New — OCC filing headers have structured metadata |
| Convey 640 CSV/Excel upload (optional) | Users already have Convey 640 data, expect to use it | Low | Reuses existing pandas CSV/Excel processing |
| PDF-authoritative merge | When PDF and CSV disagree, PDF wins (Convey 640 has OCR errors) | Medium | New merge logic — match by entry number, use PDF for names/addresses |
| Mineral export output | Expected format for all Extract/Title outputs | Low | Reuses existing MINERAL_EXPORT_COLUMNS (50+ fields) |
| Dual-file upload UI | PDF required, CSV/Excel optional accelerator | Medium | Extends existing FileUpload component to support secondary optional file |
| Export to CSV/Excel | Standard output format across all tools | Low | Reuses existing export_service.py utilities |
| Entry flagging for low confidence | Users expect warnings when parsing is uncertain | Low | Reuses existing flagging mechanism from Extract |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Convey 640 metadata enrichment | CSV provides county, STR, case number — augments PDF data | Medium | Maps Convey 640 columns (county, legal_description, applicant, case_number) to mineral export |
| OCR error correction via PDF | Convey 640 has OCR errors; PDF text is cleaner — auto-corrects names | High | Fuzzy match respondent names between PDF and CSV, use PDF as ground truth |
| Address standardization | Cleaner addresses improve CRM import quality | Low | Reuses existing address_parser.py standardization |
| Multi-respondent row expansion | Single CSV row with multiple names → separate mineral export rows | Medium | Reuses existing split_multiple_names logic from Extract |
| STR field mapping | Section-Township-Range data from Convey 640 → mineral export Notes field | Low | Direct column mapping from CSV to export |
| Case number tracking | OCC case number from header/CSV → export for future reference | Low | New field — track application ID for compliance |
| Applicant name extraction | Identifies who filed the application (operator context) | Medium | New — header parsing for "Applicant:" field |
| County auto-population | Convey 640 or PDF header county → auto-fills County field in export | Low | Direct mapping to existing mineral export County column |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| AI-powered OCR correction | PDF text extraction via PyMuPDF is sufficient for OCC filings | Use existing PyMuPDF extraction — filings are born-digital PDFs with clean text |
| Automatic Convey 640 download | Third-party tool, user already has file locally | Require manual CSV/Excel upload — no scraping/API integration |
| Batch processing (multiple ECF filings at once) | Adds UI complexity, rare use case (one filing per well unit) | Process one filing per upload — user re-uploads for additional filings |
| GoHighLevel direct send from ECF results | Existing GHL Prep workflow handles this | Export to mineral format → use existing GHL Prep tool for import |
| Convey 640 format validation | Unknown CSV schema, varies by vendor version | Accept any CSV/Excel with reasonable column names — best-effort parsing |
| Real-time RRC data lookup for ECF respondents | RRC API is for proration, not party contact info | Extract contact data only — no RRC integration in Extract tool |
| Duplicate respondent detection across filings | No persistence of historical respondent data | Single-filing scope — duplicates within one filing only (if any) |
| Address geocoding/validation | Defer to optional enrichment services (Google Maps API) | Basic address parsing only — no API calls during extraction |

## Feature Dependencies

```
ECF PDF upload → PDF text extraction (PyMuPDF)
PDF text extraction → Respondent list parsing
Respondent list parsing → Entry number detection
Respondent list parsing → Name extraction → Entity type detection
Respondent list parsing → Address extraction
PDF header extraction → Metadata fields (county, case#, applicant)

Convey 640 upload (optional) → CSV/Excel parsing (pandas)
CSV parsing → Column mapping (county, STR, case_number, respondents)
CSV respondent data → Merge with PDF data (PDF wins)
Merge logic → Fuzzy name matching (if names differ)

Merged data → Mineral export mapping (50+ columns)
Mineral export → CSV/Excel export
```

## MVP Recommendation

Prioritize (in order):

1. **ECF PDF respondent list extraction** — Core feature, table stakes
2. **Numbered entry parsing** — Required pattern for ECF filings
3. **PDF header metadata extraction** — County, case number, applicant (differentiator)
4. **Convey 640 CSV/Excel upload (optional)** — User expects accelerator path
5. **PDF-authoritative merge logic** — Correct OCR errors, fill gaps
6. **Mineral export output** — Standard format for downstream GHL Prep workflow
7. **Dual-file upload UI** — PDF required, CSV optional

Defer:

- **Fuzzy name matching for OCR correction** — Complex, start with exact match, flag mismatches
- **STR field mapping** — Low value, defer to v2 if users request it
- **Address geocoding** — Use existing optional enrichment services
- **Multi-respondent row expansion** — Depends on Convey 640 format (unknown schema)

## Implementation Notes

### ECF PDF Structure (Based on Research)

OCC multiunit horizontal well applications follow a standard format:
- **Header section:** Applicant name, county, legal description, case number
- **Exhibit A:** Numbered respondent list (parties being notified)
  - Format: Entry number (1, 2, 3...) followed by name and mailing address
  - Example: "1. D.J. Lane, P.O. Box 123, City, State ZIP"
  - May include entity names: "Michael J. Weeks, Trustee"
- **Service requirements:** First class US mail to all respondents

### Convey 640 CSV/Excel Structure (Inferred from Context)

Convey 640 is a third-party tool that scrapes OCC filing data. Expected columns:
- **Metadata:** county, legal_description, applicant, case_number
- **Respondent data:** Numbered entries with names and addresses (often OCR'd with errors)
- **Property data:** Section-Township-Range (STR), lease info

**Key challenge:** OCR errors in respondent names and addresses. PDF is cleaner (born-digital text).

### Merge Strategy

1. **Parse PDF respondent list** → authoritative names + addresses
2. **Parse Convey 640 CSV (if provided)** → metadata (county, STR, case#) + respondent data
3. **Match by entry number** (1:1 mapping between PDF and CSV rows)
4. **Use PDF for names/addresses** (always — PDF is source of truth)
5. **Use CSV for metadata** (county, case#, STR) — augments PDF header data
6. **Flag mismatches** — if entry counts differ or names don't fuzzy-match

### Mineral Export Mapping

| ECF/Convey Field | Mineral Export Column | Notes |
|------------------|----------------------|-------|
| Respondent name | Full Name | From PDF (cleaned) |
| First/middle/last/suffix | First Name, Middle Name, Last Name, Suffix | Parsed from PDF name |
| Mailing address | Primary Address 1 | From PDF |
| Mailing address 2 | Primary Address 2 | From PDF (apt, suite, etc.) |
| City | Primary Address City | From PDF |
| State | Primary Address State | From PDF |
| ZIP | Primary Address Zip | From PDF |
| Entity type | Owner Type | Detected from PDF name |
| County (header/CSV) | County | From PDF header OR Convey 640 |
| Case number (header/CSV) | Notes/Comments | Append "Case #: 123456" |
| Legal description (CSV) | Notes/Comments | Append STR or legal description |
| Applicant (header) | Notes/Comments | Append "Applicant: Company Name" |

### UI Flow

1. **Upload screen:** "Upload ECF PDF (required)" + "Upload Convey 640 CSV/Excel (optional)"
2. **Processing:** Extract PDF → Parse CSV (if provided) → Merge → Export
3. **Results table:** Show respondent entries with columns: #, Full Name, Owner Type, Address, City, State, ZIP, Status
4. **Export options:** CSV, Excel (mineral format with 50+ columns)
5. **Metadata display:** Show detected county, case number, applicant above results table

### Existing Infrastructure to Reuse

| Component | Location | Purpose |
|-----------|----------|---------|
| PDF extraction | services/extract/pdf_extractor.py | PyMuPDF text extraction |
| Name parsing | services/extract/name_parser.py | Parse first/middle/last/suffix, detect entity type |
| Address parsing | services/extract/address_parser.py | Parse address, city, state, ZIP |
| Entity detection | services/extract/entity_detector.py | Detect Individual, Trust, LLC, Estate, etc. |
| Export service | services/extract/export_service.py | CSV/Excel export with mineral format |
| Format detection | services/extract/format_detector.py | Detect PDF layout patterns |
| FileUpload component | frontend/components/FileUpload.tsx | Drag-drop upload with validation |
| Mineral export columns | services/shared/export_utils.py | MINERAL_EXPORT_COLUMNS (50+ fields) |
| Pandas CSV/Excel | services/title/csv_processor.py | Parse CSV/Excel files |

### New Components Required

| Component | Purpose | Complexity |
|-----------|---------|------------|
| ECF format detector | Detect ECF filing format (numbered respondent list) | Medium |
| Numbered entry parser | Extract entry number + name/address blocks | Medium |
| PDF header parser | Extract county, case#, applicant from header text | Medium |
| Convey 640 CSV parser | Map CSV columns to respondent data + metadata | Medium |
| Merge service | Combine PDF and CSV data (PDF authoritative) | High |
| Dual-file upload UI | Accept PDF (required) + CSV (optional) | Medium |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| ECF PDF structure | **MEDIUM** | Based on OCC filing examples from WebSearch, actual PDF samples needed |
| Convey 640 schema | **LOW** | No public documentation found, inferred from project context only |
| PDF text quality | **HIGH** | OCC filings are born-digital PDFs with clean text (not scanned) |
| Merge strategy | **MEDIUM** | PDF-authoritative approach is standard, fuzzy matching adds complexity |
| Mineral export mapping | **HIGH** | MINERAL_EXPORT_COLUMNS format is well-defined and tested |
| Existing infrastructure reuse | **HIGH** | Extract tool has all core parsing components already built |

## Sources

Research findings based on:
- [BEFORE THE CORPORATION COMMISSION OF THE STATE OF OKLAHOMA](https://imaging.occ.ok.gov/AP/CaseFiles/occ30451709.pdf) — OCC multiunit well application example
- [What is a Pooling Application before the Oklahoma Corporation Commission?](https://winblad.law.com/pooling/) — OCC pooling process background
- [OAC 165:5 CORPORATION COMMISSION](https://oklahoma.gov/content/dam/ok/en/occ/documents/ajls/jls-courts/rules/2023/current-rules/chapter-05-rules-effective-10-01-2023.pdf) — Respondent list requirements
- [Strategies for Reducing and Correcting OCR Errors](https://link.springer.com/chapter/10.1007/978-3-642-20227-8_1) — PDF/OCR merge strategies
- [Extracting data from PDFs: A comprehensive guide](https://www.nutrient.io/blog/pdf-data-extraction-developer-guide/) — PDF text extraction techniques
- Existing Extract tool codebase (models/extract.py, services/extract/, frontend/pages/Extract.tsx)
