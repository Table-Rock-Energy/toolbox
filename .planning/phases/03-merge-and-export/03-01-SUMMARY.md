---
phase: 03-merge-and-export
plan: 01
subsystem: api
tags: [merge, entry-matching, dataclass, pydantic, tdd]

requires:
  - phase: 01-ecf-pdf-parsing
    provides: ECFParseResult dataclass with PartyEntry list
  - phase: 02-convey-640-processing
    provides: Convey640ParseResult dataclass with PartyEntry list
provides:
  - merge_entries() pure function combining PDF + CSV parse results
  - MergeResult dataclass with entries, metadata, warnings
affects: [03-merge-and-export (plans 02+), frontend-integration]

tech-stack:
  added: []
  patterns: [entry-number matching, PDF-precedence merge, model_copy for immutability]

key-files:
  created:
    - backend/app/services/extract/merge_service.py
    - backend/tests/test_merge_service.py
  modified: []

key-decisions:
  - "Fallback threshold set at 50% match rate -- below this, per-entry merge skipped but metadata still merged"
  - "CSV-only entries included with flagged=True rather than silently dropped"
  - "well_name always from PDF only (CSV does not have it)"

patterns-established:
  - "Merge pattern: PDF wins contact fields, CSV fills blanks via _fill_blanks()"
  - "Metadata merge: pdf_value or csv_value for all fields except well_name"

requirements-completed: [MRG-01, MRG-02, MRG-03, MRG-04]

duration: 4min
completed: 2026-03-12
---

# Phase 3 Plan 01: Merge Service Summary

**Pure merge function combining ECF PDF + Convey 640 CSV entries via entry-number matching with PDF precedence and >50% fallback mode**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T15:07:49Z
- **Completed:** 2026-03-12T15:12:09Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- merge_entries() merges PDF and optional CSV parse results with PDF as source of truth
- Entry-number matching with exact string comparison
- _fill_blanks() populates empty PDF contact fields from CSV without mutation
- >50% unmatched triggers fallback to PDF-only mode (metadata still merged)
- CSV-only entries included with flagged=True and descriptive flag_reason
- 20 tests covering MRG-01 through MRG-04 plus edge cases

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests** - `d180296` (test)
2. **TDD GREEN: Implementation** - `e0ea0f8` (feat)

_TDD plan: tests written first, then implementation to pass all tests._

## Files Created/Modified
- `backend/app/services/extract/merge_service.py` - Pure merge function with MergeResult dataclass
- `backend/tests/test_merge_service.py` - 20 tests covering all merge behaviors

## Decisions Made
- Fallback threshold at 50% match rate (below this, per-entry merge skipped but metadata still merged)
- CSV-only entries included with flagged=True rather than silently dropped
- well_name always from PDF only (CSV does not have it)
- model_copy used throughout to avoid mutating input objects

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Test for exact string matching (case-sensitive entry numbers) needed extra matched entries to avoid triggering the >50% fallback threshold with only 1 PDF entry. Adjusted test fixture to include 3 entries with 2 matching.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- MergeResult ready for downstream export service (Plan 02) and API endpoint wiring (Plan 03)
- Imports from ecf_parser and convey640_parser verified working

---
*Phase: 03-merge-and-export*
*Completed: 2026-03-12*
