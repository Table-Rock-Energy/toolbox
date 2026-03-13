---
phase: 06-rrc-ghl-fixes
plan: 02
subsystem: ui
tags: [react, ghl, pydantic]

requires:
  - phase: none
    provides: existing GHL send modal
provides:
  - Renamed Campaign Name label to Campaign Tag with tooltip
  - Deprecated smart_list_name backend field
affects: [ghl]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - frontend/src/components/GhlSendModal.tsx
    - backend/app/models/ghl.py

key-decisions:
  - "Label rename only — campaign_name CSV field and GHL custom field unchanged"
  - "Tooltip explains SmartList must be created manually by filtering on tag"

patterns-established: []

requirements-completed: [GHL-01, GHL-02]

duration: 5min
completed: 2026-03-13
---

# Plan 06-02: GHL Campaign Tag Rename Summary

**Renamed GHL modal field from "Campaign Name" to "Campaign Tag" with SmartList tooltip, deprecated smart_list_name**

## Performance

- **Duration:** 5 min
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 2

## Accomplishments
- Field label renamed to "Campaign Tag" to accurately reflect it sets a GHL tag
- Info icon with tooltip explaining SmartList creation workflow
- Backend smart_list_name field marked deprecated

## Task Commits

1. **Task 1: Rename label + tooltip** - `979dcb9` (feat)
2. **Task 2: Deprecate backend field** - `16c2b78` (chore)
3. **Task 3: Human verification** - approved (no commit needed)

## Files Created/Modified
- `frontend/src/components/GhlSendModal.tsx` - Label rename, tooltip, removed SmartList from confirmation
- `backend/app/models/ghl.py` - smart_list_name marked deprecated=True

## Decisions Made
- campaign_name CSV column and GHL custom field are unaffected — they flow separately from CSV data
- The modal field was always setting a tag, so "Campaign Tag" is more accurate than "Campaign Name"

## Deviations from Plan
None.

## Issues Encountered
None.

## Next Phase Readiness
- GHL label fix complete

---
*Phase: 06-rrc-ghl-fixes*
*Completed: 2026-03-13*
