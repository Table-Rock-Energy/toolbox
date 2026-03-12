---
phase: 02-convey-640-processing
plan: 01
subsystem: api
tags: [pandas, csv, excel, name-parsing, pydantic, dataclass]

# Dependency graph
requires:
  - phase: 01-ecf-pdf-parsing
    provides: "PartyEntry, CaseMetadata, EntityType models and detect_entity_type/parse_name utilities"
provides:
  - "Convey640ParseResult dataclass with entries (list[PartyEntry]) and metadata (CaseMetadata)"
  - "parse_convey640(file_bytes, filename) public API for CSV/Excel parsing"
  - "Name normalization pipeline (entry numbers, CLO/ELO, C/O, A/K/A, NEE, NOW, DECEASED)"
  - "ZIP code preservation (float-to-string, leading zero padding)"
  - "Case number normalization (numeric to CD format)"
affects: [03-pdf-csv-merge, 02-convey-640-processing]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Name normalization pipeline with ordered transformations", "dtype=str CSV/Excel reading for data preservation"]

key-files:
  created:
    - backend/app/services/extract/convey640_parser.py
    - backend/tests/test_convey640_parser.py
  modified: []

key-decisions:
  - "Single parser module (convey640_parser.py) following ECF parser pattern"
  - "Trust grantor extraction: AS TRUSTEE OF pattern takes priority over keyword-based extraction"
  - "Entity type detection runs before joint name splitting to prevent splitting LLC/Corp names on &"
  - "DECEASED marker overrides entity type to ESTATE regardless of other entity indicators"

patterns-established:
  - "Name normalization pipeline: ordered regex transforms (entry number -> care-of -> aka -> nee -> now -> deceased -> entity type -> trust grantor -> joint split -> parse_name)"
  - "Postal code normalization: float-string to zero-padded 5-digit with flagging for anomalies"

requirements-completed: [CSV-01, CSV-02, CSV-03, CSV-04]

# Metrics
duration: 6min
completed: 2026-03-12
---

# Phase 2 Plan 01: Convey 640 CSV/Excel Parser Summary

**Convey 640 CSV/Excel parser with 11-step name normalization pipeline producing identical PartyEntry + CaseMetadata types as ECF PDF parser**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-12T12:48:55Z
- **Completed:** 2026-03-12T12:54:51Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments
- 35 passing tests covering all CSV-01 through CSV-04 requirements
- Complete name normalization pipeline handling deceased, joint names, trusts, CLO/ELO care-of, NOW married names, NEE maiden names, A/K/A aliases, and C/O patterns
- ZIP code preservation with leading zero padding and anomaly flagging
- Case number normalization from numeric format to CD format
- Schema validation with clear error messages for invalid files

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests** - `3777ddb` (test)
2. **GREEN: Parser implementation** - `dd144d1` (feat)

_No refactoring needed -- code is clean and follows established patterns._

## Files Created/Modified
- `backend/app/services/extract/convey640_parser.py` - Convey 640 CSV/Excel parser with name normalization pipeline, schema validation, metadata extraction, ZIP code preservation
- `backend/tests/test_convey640_parser.py` - 35 tests across 6 test classes covering CSV-01 through CSV-04 requirements

## Decisions Made
- Single parser module following ECF parser pattern (single file, ~300 lines of logic)
- Trust grantor extraction uses two strategies: "AS TRUSTEE OF" pattern (trustee is grantor) and keyword-based extraction (text before TRUST keyword is grantor)
- Entity type detection runs before joint name splitting to prevent splitting business names like "2WOOD OIL & GAS LLC" on &
- DECEASED marker overrides entity type to ESTATE regardless of other entity indicators in the name

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Parser returns identical types (PartyEntry + CaseMetadata) to ECF PDF parser
- Ready for Phase 3 merge to consume both PDF and CSV results
- `parse_convey640` and `Convey640ParseResult` exported for integration into upload endpoint

---
*Phase: 02-convey-640-processing*
*Completed: 2026-03-12*
