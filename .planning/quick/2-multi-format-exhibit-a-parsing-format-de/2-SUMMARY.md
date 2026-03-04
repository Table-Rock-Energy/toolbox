---
phase: quick-2
plan: 01
subsystem: extract
tags: [parsing, multi-format, pdf, pdfplumber]
dependency_graph:
  requires: []
  provides: [multi-format-exhibit-a-parsing, format-detection, table-parsing]
  affects: [extract-tool, extract-api, extract-frontend]
tech_stack:
  added: []
  patterns: [strategy-pattern-for-parsers, format-auto-detection]
key_files:
  created:
    - backend/app/services/extract/format_detector.py
    - backend/app/services/extract/table_parser.py
  modified:
    - backend/app/services/extract/parser.py
    - backend/app/services/extract/pdf_extractor.py
    - backend/app/models/extract.py
    - backend/app/api/extract.py
    - frontend/src/pages/Extract.tsx
decisions:
  - "Used pdfplumber extract_tables() for table-format PDFs, PyMuPDF for free-text"
  - "Quality score uses weighted average of flag ratio, address ratio, name quality, and count ratio"
  - "Table parsers do inline name parsing; free-text parsers do it after extraction in API layer"
metrics:
  duration: "~5 minutes"
  completed: "2026-03-04"
---

# Quick Task 2: Multi-Format Exhibit A Parsing Summary

Format auto-detection with strategy routing for 4 Exhibit A layouts (Devon table, Mewbourne split-address table, Coterra two-column list, and existing free-text), plus quality scoring and manual format override UI.

## What Was Built

### Backend: Format Detection (`format_detector.py`)
- `ExhibitFormat` enum with 5 values: `FREE_TEXT_NUMBERED`, `TABLE_ATTENTION`, `TABLE_SPLIT_ADDR`, `FREE_TEXT_LIST`, `UNKNOWN`
- `detect_format()` uses text heuristics (header keywords, section markers) with pdfplumber table detection as fallback
- `compute_quality_score()` returns 0.0-1.0 based on flag ratio, address completeness, name validity, and expected count

### Backend: Table Parser (`table_parser.py`)
- `parse_table_pdf()` handles TABLE_ATTENTION (Devon: Name/Attention/Address1/Address2) and TABLE_SPLIT_ADDR (Mewbourne: No./Name/Addr1/Addr2/City/State/Zip)
- Attention column mapped to notes as "c/o {attention}"
- Curative Parties section detected and entries flagged accordingly
- Header row detection and empty row skipping built in

### Backend: Parser Improvements
- `parser.py`: Handles "RESPONDENTS WITH ADDRESS UNKNOWN" header by auto-prefixing subsequent entry numbers with "U"
- `pdf_extractor.py`: Added `detect_column_count()` for 2-vs-3 column detection, `extract_text_from_pdf()` accepts optional `num_columns`
- `_clean_exhibit_text()`: Skips "RESPONDENTS WITH ADDRESS UNKNOWN" header line

### Backend: API Routing
- Upload endpoint accepts `format_hint` query parameter for manual override
- Routes to `parse_table_pdf()` for table formats, `parse_exhibit_a()` with 2-column extraction for FREE_TEXT_LIST, existing flow for FREE_TEXT_NUMBERED
- Populates `format_detected`, `quality_score`, `format_warning` on response
- Warning set when quality < 0.5

### Frontend: Format UI
- Format selector dropdown (Auto-detect + 4 options) in upload area (both panel states)
- Detected format shown in results header with human-readable name
- Color-coded confidence percentage (green >= 75%, yellow >= 50%, red < 50%)
- Yellow warning banner when low quality detected, suggesting manual format selection

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 5692e08 | Backend format detection, table parser, API routing |
| 2 | 5548810 | Frontend format selector and quality indicator |

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- All Python files compile without errors
- TypeScript compiles without errors (`tsc --noEmit`)
- Ruff lint passes on all modified Python files
- ESLint passes on Extract.tsx

## Self-Check: PASSED
