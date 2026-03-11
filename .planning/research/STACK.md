# Technology Stack — ECF/Convey 640 Extraction

**Project:** Table Rock Tools — Extract Tool (ECF/Convey 640 Format)
**Researched:** 2026-03-11

## Summary

**NO NEW DEPENDENCIES REQUIRED.** All capabilities for ECF PDF parsing and Convey 640 CSV/Excel merge exist in the current stack. This is a feature addition using existing infrastructure.

## Validated Current Stack

### Core Dependencies (Already Installed)

| Technology | Current Version | Purpose | Why Sufficient |
|------------|----------------|---------|----------------|
| PyMuPDF (fitz) | >=1.23.0 | PDF text extraction | Latest is 1.27.2 (Mar 2026). Existing multi-column extraction already handles 2-3 column layouts. `extract_text_from_pdf()` with column-aware sorting is production-validated for OCC Exhibit A PDFs. |
| pdfplumber | >=0.10.0 | Fallback PDF extraction | Production fallback for PyMuPDF. No changes needed. |
| pandas | >=2.1.0 | CSV/Excel processing | Latest is 3.0.1 (Jan 2026). Current constraint (>=2.1.0) allows 3.x. Existing CSV delimiter detection, column mapping, and row processing in `title/csv_processor.py` handles variable column formats. |
| openpyxl | >=3.1.0 | Excel read/write | Latest is 3.1.5. Used via pandas ExcelWriter for mineral export. No changes needed. |
| python-multipart | >=0.0.6 | File upload handling | FastAPI dependency for multipart/form-data uploads. Already handles dual-file uploads. |

### Existing Infrastructure (Reusable)

| Component | Location | Capability | How ECF/Convey 640 Uses It |
|-----------|----------|------------|---------------------------|
| PDF extractor | `services/extract/pdf_extractor.py` | Multi-column text extraction, exhibit detection, column count auto-detection | **Reuse as-is.** ECF PDFs are 2-3 column Exhibit A lists — same as existing OCC format. |
| CSV processor | `services/title/csv_processor.py` | Delimiter detection (`_detect_delimiter`), column mapping (`_identify_columns`), row processing | **Adapt pattern.** Convey 640 has known columns (County, STR, Applicant, Case#, Respondent data). Copy logic for flexible column mapping. |
| Excel processor | `services/title/excel_processor.py` | Excel file reading via pandas | **Reuse as-is.** `pd.read_excel()` handles .xlsx/.xls. |
| Name parser | `services/extract/name_parser.py` | Parse names into first/middle/last/suffix, detect entity type | **Reuse as-is.** Same parsing needs for ECF respondent names. |
| Address parser | `services/extract/address_parser.py` | Parse addresses, extract city/state/zip, handle PO Box | **Reuse as-is.** Same parsing needs for ECF addresses. |
| Entity detector | `services/title/entity_detector.py` | Detect Individual/Trust/LLC/Estate/Corporation from text | **Reuse as-is.** Same entity types in ECF respondents. |
| Export service | `services/extract/export_service.py` | Generate mineral export CSV/Excel with `MINERAL_EXPORT_COLUMNS` | **Reuse as-is.** ECF output uses same 53-column mineral format. |
| Legal description parser | `services/proration/legal_description_parser.py` | Extract Block/Section/Abstract from legal text | **Extend.** Add County extraction (already in Convey 640 as column). STR parsing may need township/range patterns. |
| File upload component | `frontend/components/FileUpload.tsx` | Drag-drop multi-file upload with validation | **Reuse.** Already supports `multiple={true}`. UI pattern: show two file slots (PDF required, CSV optional). |

## What NOT to Add

| Technology | Why NOT Needed |
|------------|----------------|
| PyPDF2 / pypdf | PyMuPDF already handles all PDF text extraction needs. PyPDF2 is slower and less capable for multi-column layouts. |
| tabula-py / camelot-py | Table extraction libraries. ECF PDFs are text-based lists, not complex tables. PyMuPDF text extraction is sufficient. |
| OpenCV / pytesseract | OCR libraries. ECF PDFs are digitally generated (not scanned), so OCR is unnecessary. Revenue tool already has optional OCR for scanned documents; not needed here. |
| xlrd / xlwt | Legacy Excel libraries. openpyxl via pandas handles all modern Excel needs. |
| csvkit | CSV utilities. pandas delimiter detection and column mapping are sufficient. |
| polars / duckdb | Alternative data processing. pandas is already installed and validated for CSV/Excel. No performance bottleneck for single-file processing. |
| regex library (3rd-party) | Python's built-in `re` module handles all pattern matching needs. `utils/patterns.py` already has extensive regex patterns. |

## Integration Points

### Backend (FastAPI)

**Router:** `api/extract.py`
- Add `format` parameter to upload endpoint (detect ECF vs standard Exhibit A)
- Add optional `convey_file` parameter for dual-file upload
- Reuse existing `ExtractionResult` and `PartyEntry` models

**Models:** `models/extract.py`
- No changes needed — `PartyEntry` already has all fields (name, address, entity type, notes)
- Optional: Add `case_metadata` field to `ExtractionResult` for county/legal/applicant/case# (defer until phase implementation)

**Service:** `services/extract/`
- New file: `ecf_parser.py` — ECF-specific header extraction (county, legal description, applicant, case number)
- New file: `convey_processor.py` — Parse Convey 640 CSV/Excel with column mapping
- New file: `merge_service.py` — Merge PDF respondent data with Convey 640 metadata (PDF is source of truth for names/addresses)
- Reuse: `pdf_extractor.py`, `name_parser.py`, `address_parser.py`, `export_service.py`

### Frontend (React)

**Page:** `pages/Extract.tsx`
- Add format selector radio buttons: "Standard Exhibit A" vs "ECF Multiunit Application"
- Conditional dual-file upload UI when ECF selected:
  - Slot 1: "ECF PDF (Required)" — `.pdf` only
  - Slot 2: "Convey 640 CSV/Excel (Optional)" — `.csv, .xlsx, .xls`
- Reuse existing `FileUpload` component with `multiple={true}`
- Pass both files in single multipart/form-data request

**Components:** No new components needed
- `FileUpload.tsx` already handles multi-file drag-drop
- `DataTable.tsx` already displays results with filtering
- `Modal.tsx` already handles export configuration

## Recommended Approach

### Phase 1: PDF-Only ECF Extraction
1. Add ECF format detection in `format_detector.py` (look for "MULTIUNIT" or case number pattern in header)
2. Create `ecf_parser.py` to extract case metadata from PDF header
3. Reuse `pdf_extractor.extract_party_list()` for respondent text
4. Reuse `parser.parse_entries()` for numbered entry parsing
5. Map to mineral export with case metadata in County/Campaign Name fields

### Phase 2: Convey 640 Merge
1. Create `convey_processor.py` to parse CSV/Excel with flexible column mapping
2. Create `merge_service.py` to:
   - Match PDF respondents to Convey 640 rows by name fuzzy match
   - Use PDF names/addresses as source of truth (correct OCR errors)
   - Pull county/STR/applicant/case# from Convey 640 metadata
   - Fill mineral export fields with maximum coverage

### Phase 3: Frontend Dual Upload
1. Add format selector to Extract page
2. Show two file slots when ECF selected
3. Send both files in single request (FastAPI handles multipart with multiple files)
4. Display merged results with case metadata

## Version Updates Needed

**NONE.** All dependencies are current and sufficient.

**Optional future consideration:** Upgrade pandas to 3.0.1 for performance improvements, but current >=2.1.0 constraint already permits 3.x. No code changes required (pandas 3.0 maintains backward compatibility for basic DataFrame operations).

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| PDF extraction | **HIGH** | PyMuPDF 1.27.2 is current (Mar 2026). Existing `pdf_extractor.py` handles multi-column OCC PDFs in production. ECF PDFs are same format (2-3 columns, numbered entries, Exhibit A section). |
| CSV/Excel processing | **HIGH** | pandas 3.0.1 is current (Jan 2026). Existing `csv_processor.py` handles delimiter detection and flexible column mapping. Convey 640 has known column names (easier than title opinion CSVs already processed). |
| Name/address parsing | **HIGH** | Existing parsers validated on OCC Exhibit A data. ECF respondents have identical format (name on line 1, address on lines 2-3). |
| Entity detection | **HIGH** | Same entity types (Individual, Trust, LLC, Estate, etc.) in ECF as existing formats. |
| Mineral export | **HIGH** | `MINERAL_EXPORT_COLUMNS` already defined. ECF data maps to same fields. |
| Frontend file upload | **MEDIUM** | `FileUpload.tsx` supports multi-file. Need UI pattern for "PDF required, CSV optional" — implementation detail, not stack limitation. |

## Sources

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) — Latest version 1.27.2, March 2026
- [PyMuPDF PyPI](https://pypi.org/project/PyMuPDF/) — Version history and installation
- [pandas 3.0.1 Documentation](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) — Released January 21, 2026
- [pandas.read_excel Documentation](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html) — CSV/Excel reading
- [openpyxl Documentation](https://openpyxl.readthedocs.io/en/latest/) — Latest version 3.1.5
- Existing codebase: `backend/requirements.txt`, `services/extract/`, `services/title/`, `utils/patterns.py`, `frontend/components/FileUpload.tsx`
