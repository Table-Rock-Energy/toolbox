---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: ECF Extraction
status: completed
stopped_at: Completed 03-02-PLAN.md
last_updated: "2026-03-12T15:28:06.146Z"
last_activity: 2026-03-12 — Completed Plan 03-02
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 7
  completed_plans: 7
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-11)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results. Everything else is secondary to parsing accuracy and data integrity.
**Current focus:** Phase 3 - Merge and Export

## Current Position

Phase: 3 of 4 (Merge and Export)
Plan: 2 of 2 in current phase (COMPLETE)
Status: Plan 03-02 complete
Last activity: 2026-03-12 — Completed Plan 03-02

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 8 min
- Total execution time: 0.95 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 04-frontend-integration | 2 | 17 min | 9 min |
| 01-ecf-pdf-parsing | 2 | 18 min | 9 min |
| 02-convey-640-processing | 1 | 6 min | 6 min |
| 03-merge-and-export | 2 | 16 min | 8 min |

## Accumulated Context

### Decisions

- [Milestone]: ECF extraction integrates into existing Extract tool as new format mode
- [Milestone]: PDF is source of truth for respondent data; CSV optional accelerator
- [Milestone]: Convey 640 metadata (county, STR, case#) maps to mineral export fields
- [Roadmap]: Phases 1 and 2 are independent — can execute in parallel if desired
- [04-01]: ECF option added to both collapsed and expanded panel dropdowns for consistency
- [04-01]: CSV file cleared via useEffect on formatHint change rather than inline handler
- [Phase 04-02]: Case metadata panel uses subtle blue background to distinguish from results table
- [Phase 04-02]: Mineral export modal auto-populates county for ECF, starts empty for other formats
- [01-01]: Built dedicated ecf_parser.py module rather than extending existing parser.py
- [01-01]: ECF entity classification handles "deceased" case-insensitively (existing ESTATE_PATTERN requires comma prefix)
- [01-01]: Entry number regex requires uppercase letter after number-dot to distinguish from street addresses
- [01-02]: ECF parser skips post-processing name parse loop since it handles parse_name internally
- [01-02]: Export filtering uses section_type presence as guard -- only activates when entries have section_type set
- [02-01]: Single parser module (convey640_parser.py) following ECF parser pattern
- [02-01]: Trust grantor extraction: AS TRUSTEE OF pattern takes priority over keyword-based extraction
- [02-01]: Entity type detection runs before joint name splitting to prevent splitting LLC/Corp names on &
- [02-01]: DECEASED marker overrides entity type to ESTATE regardless of other entity indicators
- [03-01]: Fallback threshold at 50% match rate -- below this, per-entry merge skipped but metadata still merged
- [03-01]: CSV-only entries included with flagged=True rather than silently dropped
- [03-01]: well_name always from PDF only (CSV does not have it)
- [03-02]: County and case_number excluded from Notes/Comments (they have dedicated columns)
- [03-02]: Metadata note appended with '; ' separator to preserve existing entry notes
- [03-02]: Non-ECF formats safely ignore csv_file parameter

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: Fuzzy matching deferred to v2 — Phase 3 merge uses entry-number matching only

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|

## Session Continuity

Last session: 2026-03-12T15:24:21Z
Stopped at: Completed 03-02-PLAN.md
Resume file: .planning/phases/03-merge-and-export/03-02-SUMMARY.md
