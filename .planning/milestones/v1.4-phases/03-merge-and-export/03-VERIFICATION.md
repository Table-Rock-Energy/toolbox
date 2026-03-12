---
phase: 03-merge-and-export
verified: 2026-03-12T16:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 3: Merge and Export Verification Report

**Phase Goal:** When both PDF and CSV are provided, the system merges them with PDF as source of truth and exports to mineral format with maximum field coverage
**Verified:** 2026-03-12
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PDF contact fields (name, address, city, state, ZIP, entity type) always win over CSV values in merged output | VERIFIED | `_fill_blanks()` only overwrites when PDF field is None/empty; 3 TestPdfWinsContactFields tests pass |
| 2 | CSV metadata (county, STR, case number, applicant) fills gaps in PDF metadata | VERIFIED | `_merge_metadata()` uses `pdf_value or csv_value` for all metadata fields; 4 TestCsvMetadataEnriches tests pass |
| 3 | Entries are matched by exact entry_number string match | VERIFIED | `csv_by_entry.pop(pdf_entry.entry_number, None)` with case-sensitive dict lookup; `test_exact_string_match` confirms "1A" != "1a" |
| 4 | CSV-only entries (no PDF match) are included with flagged=True and descriptive flag_reason | VERIFIED | `flag_reason="No PDF match -- data from Convey 640 only (may contain OCR errors)"` set on remaining `csv_by_entry` values; `test_csv_only_entries_flagged` passes |
| 5 | When >50% of entries are unmatched, merge falls back to PDF-only mode with warning | VERIFIED | `_MIN_MATCH_RATE = 0.5` threshold; fallback skips per-entry merge; `test_fallback_when_over_50_percent_unmatched` and `test_fallback_still_merges_metadata` pass |
| 6 | PDF-only mode (csv_result=None) returns PDF entries and metadata unchanged | VERIFIED | Early return with `list(pdf_result.entries)` and `pdf_result.metadata.model_copy()`; `test_csv_none_returns_pdf_unchanged` passes |
| 7 | Upload endpoint accepts optional csv_file and triggers merge when ECF format + CSV provided | VERIFIED | `csv_file: Optional[UploadFile] = File(None, ...)` in `upload_pdf()`; merge branch at lines 110-119 of extract.py |
| 8 | Merged results export to mineral CSV/Excel with Notes/Comments containing legal description, applicant, and well name | VERIFIED | `_format_metadata_note()` builds pipe-separated string; appended to `row["Notes/Comments"]` with "; " separator; 5 TestMergeExport + 3 TestMetadataNotes tests pass |
| 9 | Export endpoints accept case_metadata for Notes/Comments population | VERIFIED | `to_csv()`, `to_excel()`, `_entries_to_dataframe()` all accept `case_metadata: CaseMetadata | None = None`; both export routes pass `request.case_metadata` through |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/extract/merge_service.py` | Pure merge function with MergeResult dataclass | VERIFIED | 156 lines; exports `merge_entries`, `MergeResult`; imports `ECFParseResult` and `Convey640ParseResult` |
| `backend/tests/test_merge_service.py` | TDD tests covering all merge behaviors | VERIFIED | 419 lines (exceeds 100-line minimum); 30 tests in 7 test classes |
| `backend/app/api/extract.py` | Upload endpoint with csv_file param and merge integration | VERIFIED | `csv_file` param present; merge branch wired for ECF format; export endpoints pass `case_metadata` |
| `backend/app/services/extract/export_service.py` | Export with metadata-to-notes logic | VERIFIED | `_format_metadata_note` helper present; `case_metadata` param on `to_csv`, `to_excel`, `_entries_to_dataframe` |
| `backend/app/models/extract.py` | ExportRequest with case_metadata field | VERIFIED | `case_metadata: Optional[CaseMetadata] = Field(None, ...)` present in `ExportRequest` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `merge_service.py` | `ecf_parser.py` | imports ECFParseResult | VERIFIED | `from app.services.extract.ecf_parser import ECFParseResult` at line 14 |
| `merge_service.py` | `convey640_parser.py` | imports Convey640ParseResult | VERIFIED | `from app.services.extract.convey640_parser import Convey640ParseResult` at line 13 |
| `api/extract.py` | `merge_service.py` | imports merge_entries | VERIFIED | Lazy import `from app.services.extract.merge_service import merge_entries` inside ECF branch |
| `api/extract.py` | `convey640_parser.py` | imports parse_convey640 | VERIFIED | Lazy import `from app.services.extract.convey640_parser import parse_convey640` inside ECF branch |
| `export_service.py` | `models/extract.py` | imports CaseMetadata | VERIFIED | `from app.models.extract import CaseMetadata, PartyEntry` at line 9 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MRG-01 | 03-01-PLAN.md | PDF is source of truth for names and addresses | SATISFIED | `_fill_blanks()` never overwrites populated PDF fields; `TestPdfWinsContactFields` (3 tests) all pass |
| MRG-02 | 03-01-PLAN.md | CSV metadata enriches the merged result | SATISFIED | `_merge_metadata()` uses `or` logic; `TestCsvMetadataEnriches` (4 tests) all pass including well_name PDF-only rule |
| MRG-03 | 03-01-PLAN.md | Entries matched between PDF and CSV by entry number | SATISFIED | Dict-based exact string matching; `TestEntryNumberMatching` (3 tests) all pass |
| MRG-04 | 03-01-PLAN.md | Mismatched entries flagged for user review | SATISFIED | CSV-only entries flagged with reason; warnings include count summary; `TestMismatchWarnings` (4 tests) all pass |
| EXP-01 | 03-02-PLAN.md | Merged results export to mineral export CSV format | SATISFIED | `to_csv()` accepts merged entries + `case_metadata`; uses `MINERAL_EXPORT_COLUMNS` from `shared/export_utils.py`; `TestMergeExport` tests pass |
| EXP-02 | 03-02-PLAN.md | Merged results export to mineral export Excel format | SATISFIED | `to_excel()` accepts same `case_metadata` param; `test_excel_with_case_metadata_same_as_csv` passes |
| EXP-03 | 03-02-PLAN.md | County, case number, applicant, and legal description populate appropriate mineral export fields | SATISFIED | County in dedicated `County` column; applicant + legal description in Notes/Comments via `_format_metadata_note`; `TestMetadataNotes::test_all_fields_populated` confirms county/case_number excluded from notes |

All 7 requirement IDs from both PLANs (MRG-01 through MRG-04, EXP-01 through EXP-03) are satisfied.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no stub return values, no empty implementations found in any modified files.

### Human Verification Required

None. All phase behaviors are verifiable programmatically. The export format (mineral CSV column layout) is validated by the existing test fixtures and `MINERAL_EXPORT_COLUMNS` constant from `shared/export_utils.py`.

### Test Suite Results

```
30 passed in 0.04s
```

Full test run: 30/30 tests pass across all 7 test classes:
- `TestPdfWinsContactFields` (3)
- `TestCsvMetadataEnriches` (4)
- `TestEntryNumberMatching` (3)
- `TestMismatchWarnings` (4)
- `TestEdgeCases` (6)
- `TestMergeExport` (5)
- `TestMetadataNotes` (3)
- `TestExportRequestModel` (2)

---

_Verified: 2026-03-12_
_Verifier: Claude (gsd-verifier)_
