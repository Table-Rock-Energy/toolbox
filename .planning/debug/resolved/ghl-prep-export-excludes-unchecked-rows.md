---
status: resolved
trigger: "ghl-prep-export-excludes-unchecked-rows"
created: 2026-03-04T00:00:00Z
updated: 2026-03-04T00:00:00Z
---

## Current Focus

hypothesis: Fix applied - filter sortedRows instead of baseRows
test: TypeScript compilation check
expecting: Code compiles without errors
next_action: Request human verification of the fix

## Symptoms

expected: When rows are unchecked in the GHL Prep data table, exporting to CSV should exclude those unchecked rows
actual: All rows appear in the exported CSV regardless of checkbox state
errors: No error messages — it silently includes all rows
reproduction: Upload a CSV to GHL Prep → uncheck some rows → export CSV → unchecked rows still present in output
started: Just added the row exclusion feature in quick task 1 (commit 1799d31)

## Eliminated

## Evidence

- timestamp: 2026-03-04T00:00:00Z
  checked: frontend/src/pages/GhlPrep.tsx handleExport function (lines 277-319)
  found: Frontend filters rows using excludedRows Set BUT uses wrong index space
  implication: The excludedRows Set contains indices from sortedRows (visual display indices), but it's filtering baseRows (original result.rows) using those indices

- timestamp: 2026-03-04T00:00:00Z
  checked: Line 284-286 in GhlPrep.tsx
  found: `const baseRows = showIndividualsOnly ? filteredRows : result.rows` then `baseRows.filter((_, i) => !excludedRows.has(i))`
  implication: When user unchecks row 3 in the sorted/filtered table, excludedRows has index 3. But row 3 in baseRows (result.rows) is a different row than row 3 in sortedRows!

- timestamp: 2026-03-04T00:00:00Z
  checked: Lines 179-185 in GhlPrep.tsx
  found: `toggleRow(index)` operates on index from sortedRows map callback (line 774)
  implication: excludedRows indices are based on sortedRows positions, not result.rows positions

- timestamp: 2026-03-04T00:00:00Z
  checked: backend/app/api/ghl_prep.py lines 125-142
  found: Backend simply accepts rows array and exports it - no filtering logic
  implication: Backend is working correctly - it's the frontend sending the wrong rows

## Resolution

root_cause: Frontend index mismatch - excludedRows Set stores indices from sortedRows (display order after sorting/filtering), but handleExport filters baseRows (original result.rows) using those same indices. This causes wrong rows to be excluded or no exclusion at all when indices don't align.

fix: Changed both handleExport and GhlSendModal to filter sortedRows directly instead of baseRows. This ensures the excluded row indices (which correspond to visual display positions) are applied to the correct rows.

verification: TypeScript compilation passed without errors. Ready for human verification - upload CSV, uncheck specific rows, export, verify those rows are excluded from output.

files_changed:
  - frontend/src/pages/GhlPrep.tsx: Fixed handleExport (line 285) and GhlSendModal rows prop (line 829) to use sortedRows instead of baseRows
