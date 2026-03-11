# Project Research Summary

**Project:** Table Rock Tools — ECF/Convey 640 Extraction for Extract Tool
**Domain:** OCC multiunit horizontal well application PDF parsing with optional CSV/Excel metadata merge
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

ECF/Convey 640 integration is a natural extension of the existing Extract tool, requiring no new dependencies or architectural changes. The project adds ECF PDF format parsing for Oklahoma Corporation Commission multiunit well applications, with optional Convey 640 CSV/Excel merge for metadata enrichment. All capabilities exist in the current stack: PyMuPDF handles PDF text extraction, pandas processes CSV/Excel files, and existing name/address/entity parsers handle respondent data. The integration follows the established tool-per-module pattern with format detection driving parser selection.

The recommended approach is a three-phase build: (1) PDF-only ECF extraction with header metadata, (2) Convey 640 CSV/Excel parsing with normalization, (3) PDF-authoritative merge logic with fuzzy matching. This order validates parsing independently before introducing merge complexity. The critical insight is that PDF is source of truth for respondent names/addresses, while CSV provides accelerator data for county, legal description, and case numbers that augments PDF header extraction.

Key risks center on data quality and parsing accuracy: multi-line address preservation in PDF extraction, ZIP code leading-zero loss in Excel imports, OCR error contamination from CSV data, and entity type misclassification for deceased parties and trusts. These are mitigated through explicit dtype enforcement, line-aware parsing, strict merge precedence (PDF over CSV), and enhanced entity detection patterns. The architecture minimizes risk by reusing production-validated Extract tool parsers rather than building from scratch.

## Key Findings

### Recommended Stack

**NO NEW DEPENDENCIES REQUIRED.** All ECF/Convey 640 capabilities exist in the current Table Rock Tools stack. This is a feature addition using existing infrastructure, not a technology integration project.

**Core technologies (already installed):**
- **PyMuPDF (fitz) >=1.23.0**: Multi-column PDF text extraction — current version 1.27.2 (Mar 2026) handles 2-3 column ECF layouts identical to existing OCC Exhibit A PDFs
- **pandas >=2.1.0**: CSV/Excel processing — existing delimiter detection, flexible column mapping, and row processing handle variable Convey 640 formats
- **openpyxl >=3.1.0**: Excel read/write via pandas — no changes needed for .xlsx/.xls files
- **python-multipart**: FastAPI multipart/form-data uploads — already supports dual-file uploads (PDF + CSV)

**Reusable existing infrastructure:**
- PDF extractor, name parser, address parser, entity detector (services/extract/)
- CSV processor with column mapping (services/title/)
- Legal description parser (services/proration/)
- Mineral export service with 53-column format (services/extract/export_service.py)
- Dual-file upload component (frontend/components/FileUpload.tsx)

**Critical version note:** No upgrades required. Current pandas >=2.1.0 constraint already allows 3.x (latest 3.0.1). PyMuPDF 1.27.2 is latest stable. All dependencies are production-validated.

### Expected Features

ECF/Convey 640 feature set extends existing Extract tool patterns rather than introducing new categories.

**Must have (table stakes):**
- ECF PDF text extraction — core functionality, PDF is authoritative source
- Numbered entry parsing — ECF filings use "1. Name\nAddress" format
- Respondent name/address parsing — expected from existing Extract tool capabilities
- Entity type detection — Individual, Trust, LLC, Estate classification
- PDF header metadata extraction — county, legal description, applicant, case number
- Mineral export output — 53-column format matching existing tools
- Dual-file upload UI — PDF required, CSV/Excel optional
- Entry flagging for low confidence — warnings when parsing is uncertain

**Should have (competitive):**
- Convey 640 CSV/Excel upload (optional) — users expect to leverage existing data
- PDF-authoritative merge — when PDF and CSV disagree, PDF wins (corrects OCR errors)
- Convey 640 metadata enrichment — CSV provides county, STR, case number to augment PDF
- Address standardization — cleaner addresses improve downstream CRM import
- Case number tracking — OCC application ID for compliance reference
- County auto-population — metadata from PDF header or CSV fills County field

**Defer (v2+):**
- Fuzzy name matching for OCR correction — start with exact match, flag mismatches
- STR field mapping to dedicated column — append to Notes/Comments initially
- Multi-respondent row expansion — depends on Convey 640 schema (unknown)
- Address geocoding/validation — use existing optional enrichment services
- Batch processing (multiple ECF filings) — process one filing per upload

### Architecture Approach

ECF/Convey 640 integration fits naturally into existing Extract tool architecture as parser diversification rather than structural redesign. Format detection drives parser selection: `detect_format()` identifies ECF format via header patterns, routes to new `ecf_parser.py` for PDF processing and optional `convey640_parser.py` for CSV. Merge happens in dedicated `ecf_merge_service.py` that combines parsed outputs with explicit precedence rules (PDF for names/addresses, CSV for metadata). All parsers output uniform `PartyEntry` model extended with optional fields (case_number, legal_description, county), maintaining backward compatibility. Export layer maps enriched entries to existing `MINERAL_EXPORT_COLUMNS` format.

**Major components:**
1. **ECF Parser** (new: `ecf_parser.py`) — Parse ECF PDF Exhibit A respondent list using existing pdf_extractor, name_parser, address_parser utilities
2. **ECF Metadata Extractor** (new: `ecf_metadata_extractor.py`) — Extract county, case number, applicant, legal description from PDF header text
3. **Convey 640 Parser** (new: `convey640_parser.py`) — Parse CSV/Excel with flexible column mapping, extract metadata + respondent data
4. **Merge Service** (new: `ecf_merge_service.py`) — Combine PDF entries (source of truth) with CSV metadata, handle mismatches via fuzzy matching
5. **Format Detector** (extended: `format_detector.py`) — Add ECF_EXHIBIT_A enum value and detection patterns
6. **Upload Endpoint** (modified: `api/extract.py`) — Accept optional csv_file parameter, route ECF format to merge pipeline
7. **Export Service** (extended: `export_service.py`) — Map ECF metadata (county, case_number, legal_description) to mineral export columns
8. **PartyEntry Model** (extended: `models/extract.py`) — Add optional ECF metadata fields while maintaining backward compatibility
9. **Frontend Extract Page** (modified: `Extract.tsx`) — Conditional second FileUpload for CSV when ECF format selected, display metadata panel
10. **Dual-File Upload UI** (reused: `FileUpload.tsx`) — Show two instances conditionally, no component changes needed

**Integration principle:** Reuse > extend > create new. Prefer existing parsers, extend models with optional fields, create new only for ECF-specific logic (numbered entry parsing, metadata extraction, merge).

### Critical Pitfalls

Research identified 10 critical pitfalls ranked by impact. Top 5 require preventative design decisions before implementation:

1. **Multi-Line Address Parsing with Inconsistent Line Breaks** — PDF text extraction may not preserve line breaks, causing name fragments to bleed into address fields. Prevention: line-aware parsing that treats each `\n` as parsing boundary, validate street patterns don't match within names (<10 chars before pattern), flag suspicious entity type mismatches (Individual when "Trust" keyword present). Address in Phase 1 parser implementation.

2. **Convey 640 Line Number Contamination in Name Fields** — OCR exports embed entry numbers in names ("1. John Smith"), preventing string matching. Prevention: strip entry number patterns (`^\s*(U\s*)?\d+\.\s*`) before any comparison, normalize both PDF and CSV names for matching, separate entry number into dedicated field. Address in Phase 2 CSV parsing before Phase 3 merge.

3. **ZIP Code Data Type Loss in Excel Import** — Northeast US ZIP codes (02101) lose leading zeros when Excel converts to integer. Prevention: force `dtype={'zip': str}` in pandas, validate state-ZIP correlation (MA/CT/RI/NH/VT/ME should start with 0), pad to 5 digits if 4 detected. Address in Phase 2 CSV ingestion.

4. **Entity Type Detection Failure for Deceased Parties** — Entries like "John Smith, Deceased" misclassified as Individual instead of Estate. Prevention: reorder detection to check Estate patterns before Individual fallback, add deceased-specific patterns (`, Deceased`, `Estate of`, `c/o [Name], Executor`), two-pass detection (extract annotations first). Address in Phase 1 entity detection.

5. **Merge Logic Choosing CSV Over PDF for Name Data** — Naive merge (`csv_value or pdf_value`) prefers CSV when both exist, propagating OCR errors. Prevention: explicit precedence (`pdf_value if pdf_value is not None else csv_value`), ALWAYS use PDF for names/addresses (CSV only for metadata), add merge audit logging to track source per field. Address in Phase 3 merge service implementation.

**Additional pitfalls to monitor:**
- Name parser failure on Mc/Mac/O' prefixes (Phase 1 enhancement)
- Trustee name conflation with trust entity name (Phase 1 entity-aware parsing)
- PDF format variation across OCC filing dates (Phase 1 format detection robustness)
- Case metadata extraction failure from PDF header (Phase 1 parallel track)
- Low merge match rate from overly strict matching (Phase 3 fuzzy matching tuning)

## Implications for Roadmap

Based on research, suggested phase structure follows dependency order: validate PDF parsing independently, add CSV processing, integrate merge logic, polish frontend.

### Phase 1: ECF PDF Parsing (Backend Foundation)
**Rationale:** Core extraction capability must work independently before adding CSV complexity. PDF is source of truth, so this phase delivers complete feature without CSV merge. Validates parsing patterns against actual ECF filings before merge dependency.

**Delivers:**
- ECF format detection and numbered entry parsing
- Respondent name/address extraction with entity type detection
- PDF header metadata extraction (county, legal description, applicant, case number)
- Entry flagging for low confidence parses
- Mineral export output with ECF metadata

**Addresses features:**
- ECF PDF text extraction (table stakes)
- Numbered entry parsing (table stakes)
- Respondent name/address parsing (table stakes)
- Entity type detection (table stakes)
- PDF header metadata extraction (table stakes)
- Mineral export output (table stakes)

**Avoids pitfalls:**
- Multi-line address parsing (#1) — line-aware extraction from start
- Entity type detection failure (#4) — Estate patterns before Individual fallback
- Name parser Mc/Mac/O' failures (#6) — prefix preservation rules
- Trustee/trust name conflation (#7) — entity-first parsing priority
- PDF format variation (#8) — test with filings from 2020-2026
- Case metadata extraction failure (#9) — separate header parser track

**Architecture components:**
- `ecf_parser.py` (new)
- `ecf_metadata_extractor.py` (new)
- `format_detector.py` (extend with ECF_EXHIBIT_A)
- `models/extract.py` (extend PartyEntry with optional metadata fields)

**Research flag:** LOW — ECF format structure is well-documented through OCC examples, parser reuses validated Extract tool infrastructure. Test with sample PDFs spanning multiple years to confirm format stability.

---

### Phase 2: Convey 640 CSV/Excel Processing
**Rationale:** CSV parsing must happen independently to validate normalization, column mapping, and data quality before merge. ZIP code and entry number handling are table-stakes for merge success; validate here first.

**Delivers:**
- CSV/Excel file upload and format detection
- Flexible column mapping for Convey 640 schema variations
- Entry number normalization (strip line number contamination)
- ZIP code leading-zero preservation
- Metadata extraction (county, legal description, case number, applicant)
- Respondent data parsing with address standardization

**Addresses features:**
- Convey 640 CSV/Excel upload (should-have)
- Address standardization (should-have)

**Avoids pitfalls:**
- Line number contamination (#2) — strip patterns before any processing
- ZIP code data type loss (#3) — dtype enforcement + state-ZIP correlation check

**Architecture components:**
- `convey640_parser.py` (new)
- Pandas CSV/Excel processing (reuse existing patterns from title/csv_processor.py)

**Research flag:** MEDIUM — Convey 640 schema is unknown (no public documentation). Requires sample CSV/Excel files from users to validate column mapping. Likely need iterative tuning based on real data.

---

### Phase 3: PDF-CSV Merge Logic
**Rationale:** Merge is highest complexity and depends on validated parsers from Phases 1-2. Fuzzy matching requires tuning against real data pairs. Merge precedence rules are critical to avoid OCR error propagation.

**Delivers:**
- PDF-authoritative merge service
- Fuzzy name matching for OCR error detection
- Entry-by-entry merge with explicit precedence (PDF for names/addresses, CSV for metadata)
- Match statistics and unmatched entry reporting
- Merge audit trail (track source per field)
- Conflict resolution logging

**Addresses features:**
- PDF-authoritative merge (should-have)
- Convey 640 metadata enrichment (should-have)
- County auto-population (should-have)
- Case number tracking (should-have)

**Avoids pitfalls:**
- Merge choosing CSV over PDF (#5) — explicit precedence rules
- Low merge match rate (#10) — multi-strategy matching (exact, fuzzy, position-based)

**Architecture components:**
- `ecf_merge_service.py` (new)
- Integration with `api/extract.py` upload endpoint

**Research flag:** HIGH — Fuzzy matching thresholds require empirical tuning. Need 5-10 real PDF+CSV pairs to calibrate similarity thresholds, test match rates, validate precedence rules. Plan for iteration based on match statistics.

---

### Phase 4: Frontend Dual-File Upload
**Rationale:** Backend merge must be stable before adding UI complexity. Conditional upload UI depends on format selection, metadata display needs merge output structure.

**Delivers:**
- ECF format selector in Extract page
- Conditional second FileUpload for CSV/Excel (optional)
- Dual-file FormData upload to backend
- ECF metadata display panel (county, case number, applicant, legal description)
- Match statistics display (matched/unmatched counts)
- Export with enriched metadata

**Addresses features:**
- Dual-file upload UI (table stakes)
- Entry flagging for low confidence (table stakes)

**Avoids pitfalls:**
- UX pitfalls: no merge preview, silent failures, cryptic flagging

**Architecture components:**
- `Extract.tsx` (modify for conditional upload + metadata display)
- `FileUpload.tsx` (reuse, no changes)

**Research flag:** LOW — Standard React patterns, FileUpload already supports multi-file. UI design is straightforward once backend API is stable.

---

### Phase 5: Polish and Validation (Optional)
**Rationale:** Post-MVP enhancements based on user feedback and production usage patterns.

**Delivers:**
- Merge preview before commit (side-by-side PDF vs CSV comparison)
- Manual match override UI (link PDF entry to CSV row)
- Enhanced flagging reasons (specific validation failures)
- Match confidence scoring
- Export validation summary

**Addresses:** UX improvements identified in pitfalls research

**Research flag:** LOW — Standard UI patterns, defer until user feedback validates need

---

### Phase Ordering Rationale

**Why this order:**
1. **Phase 1 validates core parsing** before merge complexity — PDF parsing must work independently since PDF-only mode is complete feature
2. **Phase 2 isolates CSV data quality issues** before introducing merge logic — ZIP code and entry number handling are foundational
3. **Phase 3 depends on validated parsers** from 1+2 — fuzzy matching can only be tuned with real parsed data
4. **Phase 4 needs stable backend API** before UI work — conditional upload and metadata display depend on merge output structure
5. **Phase 5 defers UX polish** until production usage validates priorities

**Why this grouping:**
- **Backend foundation first** (Phases 1-3) enables API testing via Swagger before frontend work
- **Parser separation** (PDF vs CSV vs merge) allows independent testing and debugging
- **Progressive enhancement** — each phase delivers usable functionality (PDF-only → CSV-only → merged → UI)

**How this avoids pitfalls:**
- Testing parsers independently catches data quality issues (pitfalls #1-4) before merge
- Merge logic isolated in Phase 3 allows precedence rule validation without parser bugs (pitfall #5)
- Backend stability before frontend prevents UI rework when merge logic changes
- Format detection in Phase 1 enables early testing across filing date ranges (pitfall #8)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (Convey 640 CSV):** Unknown schema requires sample files from users. Column mapping patterns may need iteration based on real data variations. Budget 2-3 sample files for validation.
- **Phase 3 (Merge Logic):** Fuzzy matching thresholds require empirical tuning. Need 5-10 PDF+CSV pairs to calibrate similarity scores, validate match rates >75%, test conflict resolution. Budget research spike for algorithm selection (Levenshtein vs Jaro-Winkler vs phonetic).

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (ECF PDF):** Reuses production-validated Extract tool parsers. PyMuPDF extraction is well-documented and tested. Format detection patterns from existing OCC Exhibit A work.
- **Phase 4 (Frontend):** Standard React patterns, existing FileUpload component supports required functionality. No novel UI patterns.
- **Phase 5 (Polish):** Deferred UX enhancements based on established patterns (side-by-side comparison, manual overrides).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | All dependencies exist in current codebase. PyMuPDF 1.27.2 (Mar 2026) and pandas 3.0.1 (Jan 2026) are latest stable. No version upgrades or new packages required. Validated through direct requirements.txt analysis. |
| Features | **MEDIUM** | Table stakes and differentiators validated through Extract tool patterns. Unknown: Convey 640 schema variations (no public docs). Need sample files to confirm column mappings and OCR error patterns. ECF PDF structure validated via OCC filing examples. |
| Architecture | **HIGH** | Direct codebase analysis confirms reusability. Extract tool architecture already handles multiple formats via format detection. Merge pattern follows standard data integration practices (explicit precedence, audit logging). Component boundaries clear. |
| Pitfalls | **HIGH** | Pitfall research based on PDF parsing studies (2026), CSV data quality literature, fuzzy matching algorithms, and name parsing edge cases. ZIP code leading-zero loss is documented Excel behavior. Entity detection patterns tested in existing Extract tool. |

**Overall confidence:** HIGH

### Gaps to Address

**Gap 1: Convey 640 schema variations**
- **Issue:** No public documentation for Convey 640 export format. Column names, data types, and structure inferred from project context only.
- **Resolution:** Obtain 2-3 sample Convey 640 CSV/Excel files from users before Phase 2 implementation. Validate column mapping assumptions, identify OCR error patterns, confirm metadata field presence.
- **Impact:** Medium — affects Phase 2 parser flexibility and Phase 3 merge matching. Does not block Phase 1 (PDF-only mode).

**Gap 2: ECF PDF format variation over time**
- **Issue:** OCC may change filing templates across years. Research found examples from 2024 but format stability 2020-2026 not confirmed.
- **Resolution:** Collect ECF PDF samples spanning 2020-2026 before Phase 1 implementation. Test format detection and parser robustness across date ranges. Add version detection if significant variations found.
- **Impact:** Medium — affects Phase 1 parser design. Can start with recent format (2024+) and extend backward if needed.

**Gap 3: Fuzzy matching threshold calibration**
- **Issue:** Optimal similarity threshold (85%? 90%? 95%?) for PDF-CSV name matching unknown without empirical testing.
- **Resolution:** Phase 3 research spike with 5-10 real PDF+CSV pairs. Calculate match rates at different thresholds, validate false positive/negative rates, tune algorithm choice.
- **Impact:** High for Phase 3 — merge success depends on threshold tuning. Does not block Phases 1-2.

**Gap 4: Mineral export column mapping for ECF metadata**
- **Issue:** Unknown which specific columns in MINERAL_EXPORT_COLUMNS should receive case_number, legal_description, applicant. Research shows "Notes/Comments" as likely target but not confirmed.
- **Resolution:** Review MINERAL_EXPORT_COLUMNS definition in export_utils.py, confirm with downstream GHL Prep tool requirements. Validate County field exists and is appropriate for county metadata.
- **Impact:** Low — affects Phase 1 export logic but straightforward to adjust. Mineral format is well-defined.

**Gap 5: Entry number mismatch handling**
- **Issue:** PDF entry numbers may not align with CSV entry numbers (renumbering, ADDRESS UNKNOWN section differences). Unclear if position-based matching should override number-based matching.
- **Resolution:** Test with sample files that have misaligned numbering. Implement multi-strategy matching: (1) exact number match, (2) position-based match, (3) fuzzy name match. Report statistics to user for review.
- **Impact:** Medium for Phase 3 — affects merge logic complexity. Can start with exact match and extend.

## Sources

### Primary (HIGH confidence)
- **Existing codebase analysis** (`backend/requirements.txt`, `services/extract/`, `services/title/`, `frontend/components/FileUpload.tsx`) — Direct verification of reusable components, validated patterns, and mineral export format
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) — Latest version 1.27.2 (March 2026), multi-column text extraction capabilities
- [pandas 3.0.1 Documentation](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) — Released January 21, 2026, CSV/Excel processing features
- [BEFORE THE CORPORATION COMMISSION OF THE STATE OF OKLAHOMA](https://imaging.occ.ok.gov/AP/CaseFiles/occ30451709.pdf) — OCC multiunit well application example showing ECF format structure
- [OAC 165:5 CORPORATION COMMISSION](https://oklahoma.gov/content/dam/ok/en/occ/documents/ajls/jls-courts/rules/2023/current-rules/chapter-05-rules-effective-10-01-2023.pdf) — Respondent list requirements and filing format specifications

### Secondary (MEDIUM confidence)
- [A Comparative Study of PDF Parsing Tools](https://arxiv.org/html/2410.09871v1) — Layout preservation and multi-column extraction challenges
- [Excel Import Errors and Fixes](https://flatfile.com/blog/the-top-excel-import-errors-and-how-to-fix-them/) — Data type coercion problems (ZIP code leading zeros)
- [Working with Leading Zeros in Northeast ZIP Codes](https://help.littlegreenlight.com/article/53-working-with-leading-zeros-in-northeast-zip-codes) — ZIP code formatting solutions
- [Fuzzy String Matching in Python Tutorial](https://www.datacamp.com/tutorial/fuzzy-string-python) — Levenshtein, Jaro-Winkler algorithm overview
- [Deep Dive into String Similarity](https://medium.com/data-science-collective/deep-dive-into-string-similarity-from-edit-distance-to-fuzzy-matching-theory-and-practice-in-68e214c0cb1d) — Similarity threshold selection and false positive prevention
- [Why Mac and Mc Surnames Contain Second Capital Letter](https://www.todayifoundout.com/index.php/2014/02/mac-mc-surnames-often-contain-second-capital-letter/) — Celtic name prefix patterns

### Tertiary (LOW confidence — needs validation)
- **Convey 640 schema** — Inferred from project context only, no public documentation found. Requires sample files for validation.
- [What is a Pooling Application before the Oklahoma Corporation Commission?](https://winblad.law.com/pooling/) — Background on OCC pooling process, but limited filing format details
- [Strategies for Reducing and Correcting OCR Errors](https://link.springer.com/chapter/10.1007/978-3-642-20227-8_1) — General PDF/OCR merge strategies, not ECF-specific

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
