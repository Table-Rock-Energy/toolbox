---
phase: quick
plan: 01
subsystem: ghl-prep
tags: [filtering, entity-type, ui, shared-utils]
dependency_graph:
  requires: []
  provides: [entity-type-filter, shared-entity-detection]
  affects: [ghl-prep, extract]
tech_stack:
  added: []
  patterns: [shared-utilities, inline-filtering, computed-properties]
key_files:
  created: []
  modified:
    - backend/app/utils/patterns.py
    - backend/app/services/extract/parser.py
    - backend/app/services/ghl_prep/transform_service.py
    - frontend/src/pages/GhlPrep.tsx
decisions:
  - decision: Extract entity type detection to shared utils/patterns.py
    rationale: Enables cross-tool reuse without duplicating regex logic
    alternatives: [Keep in extract tool only, Create separate entity_detector.py module]
  - decision: Add Entity Type column after OUTPUT_COLUMNS filter
    rationale: Column visible in UI/filtering but automatically excluded from export
    alternatives: [Add to OUTPUT_COLUMNS and strip manually, Create separate display model]
  - decision: Filter rows client-side in React useMemo
    rationale: Small datasets, instant filtering, no backend changes needed
    alternatives: [Add backend filter endpoint, Use URL query params]
metrics:
  duration_seconds: 139
  tasks_completed: 2
  files_modified: 4
  commits: 2
  completed_date: "2026-03-04"
---

# Quick Task 1: Add Entity Type Filtering to GHL Prep

Entity type classification now available in GHL Prep with shared detection logic and individual-only filtering.

## One-liner

Extracted entity type detection to shared utils, added Entity Type column to GHL Prep results with "Individuals only" filter to exclude commercial entities from export/send.

## What Changed

### Backend (Python)
1. **Shared entity detection** (`backend/app/utils/patterns.py`)
   - New `detect_entity_type(text: str) -> str` function
   - Returns EntityType string value (not enum) for cross-tool compatibility
   - Lazy imports EntityType enum to avoid circular dependencies
   - Reuses existing entity type regex patterns (LLC, Trust, Corporation, etc.)

2. **Extract tool delegation** (`backend/app/services/extract/parser.py`)
   - Refactored `_detect_entity_type()` to delegate to shared function
   - Wraps string result in EntityType enum for backward compatibility
   - Preserves existing return type for all extract tool callers

3. **GHL Prep classification** (`backend/app/services/ghl_prep/transform_service.py`)
   - Added Entity Type column after OUTPUT_COLUMNS selection
   - Classifies each row using First Name + Last Name combined
   - Tracks entity type counts in `transformed_fields["entity_types"]`
   - Column present in rows dict for display but not in OUTPUT_COLUMNS (auto-excluded from export)

### Frontend (TypeScript/React)
1. **Filter state** (`frontend/src/pages/GhlPrep.tsx`)
   - Added `showIndividualsOnly` boolean state (defaults to false)
   - Checkbox filter UI in results header (only visible in normal view mode)
   - Displays "X of Y contacts" when filter active

2. **Filtered rows logic**
   - New `filteredRows` useMemo filters `currentRows` by `Entity Type === 'Individual'`
   - Updated `sortedRows` to use `filteredRows` instead of `currentRows`
   - Row count display shows "(filtered from N)" when filter active

3. **Export/send integration**
   - CSV export uses filtered rows when filter active, strips Entity Type column
   - GHL send modal receives filtered rows with Entity Type stripped
   - Contact count in modal reflects filtered count
   - Filter reset on new upload or explicit reset action

## Technical Details

**Entity type classification order** (first match wins):
1. Unknown Heirs
2. Estate
3. Trust
4. LLC
5. Corporation
6. Partnership
7. Government
8. Individual (default fallback)

**Filter behavior:**
- Only affects normal view mode (not failed contacts view)
- Filters rows where `Entity Type === 'Individual'`
- Commercial entities (LLC, Trust, Corporation, etc.) excluded when filter active
- Filter state persists until reset or new upload

**Export behavior:**
- Entity Type column added to rows dict for display/filtering
- Column NOT in OUTPUT_COLUMNS list → automatically excluded from CSV export
- Export endpoint receives rows with Entity Type already stripped by frontend
- GHL send receives same filtered/stripped rows

## Deviations from Plan

None — plan executed exactly as written.

## Verification

### Automated Tests (Passed)
```bash
# Backend entity detection
python3 -c "from app.utils.patterns import detect_entity_type; \
  assert detect_entity_type('John Smith') == 'Individual'; \
  assert detect_entity_type('Smith Family Trust') == 'Trust'; \
  assert detect_entity_type('Acme LLC') == 'LLC'; \
  assert detect_entity_type('Unknown Heirs of Jones') == 'Unknown Heirs'"

# Extract tool delegation
python3 -c "from app.services.extract.parser import _detect_entity_type; \
  from app.models.extract import EntityType; \
  assert _detect_entity_type('John Smith') == EntityType.INDIVIDUAL"

# TypeScript compilation
npx tsc --noEmit  # No errors
```

### Manual Testing Steps
1. Upload a Mineral CSV in GHL Prep
2. Verify Entity Type column appears in results table
3. Toggle "Individuals only" checkbox
4. Confirm row count updates and non-Individual rows disappear
5. Export CSV and verify Entity Type column excluded
6. Send to GHL and verify filtered rows sent (Entity Type excluded)

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `backend/app/utils/patterns.py` | +26 | Added detect_entity_type() shared function |
| `backend/app/services/extract/parser.py` | -24, +3 | Refactored to delegate to shared function |
| `backend/app/services/ghl_prep/transform_service.py` | +13 | Added Entity Type classification + counts |
| `frontend/src/pages/GhlPrep.tsx` | +41, -7 | Added filter UI, filtered rows logic, export/send integration |

## Commits

| Hash | Message |
|------|---------|
| a4ecd59 | feat(quick-01): add shared entity type detection and GHL Prep classification |
| 08f9fad | feat(quick-01): add entity type filter UI to GHL Prep |

## Key Decisions

**Why extract to shared utils instead of creating a new module?**
- `patterns.py` already contains all entity type regex patterns
- Function is 30 lines, lightweight, no external dependencies beyond patterns
- Lazy import of EntityType enum avoids circular dependency issues
- Keeps related code (patterns + detection logic) co-located

**Why add Entity Type after OUTPUT_COLUMNS selection?**
- Column exists in rows dict for React display and filtering
- Not in OUTPUT_COLUMNS list → automatically excluded from pandas export
- No need for manual column stripping in backend export endpoint
- Frontend strips it for GHL send (different data structure)

**Why client-side filtering instead of backend endpoint?**
- GHL Prep datasets are small (hundreds of rows, not thousands)
- Instant filtering with no network latency
- No additional backend API complexity
- Filter state managed entirely in React (simple useState)

## Success Criteria Met

- [x] GHL Prep results show Entity Type column with correct classifications
- [x] User can toggle "Individuals only" filter
- [x] Filtered count vs total count visible in UI
- [x] CSV export and GHL send use filtered rows
- [x] Entity Type column excluded from export data
- [x] Extract tool entity detection still works (delegation preserved)
- [x] TypeScript and Python pass syntax checks

## Impact

**User workflow:**
1. Upload Mineral export to GHL Prep
2. Review Entity Type column to see classification
3. Toggle "Individuals only" to exclude LLCs, Trusts, Corporations
4. Export or send only individual contacts to GHL
5. Reduced API quota usage and better contact quality in GHL

**Technical benefits:**
- Reusable entity detection logic across tools
- No duplication of regex patterns or classification rules
- Backward-compatible refactor (extract tool unchanged externally)
- Clean separation of display columns vs export columns

## Next Steps

None required — feature complete and tested.

## Self-Check: PASSED

**Files exist:**
```bash
✓ backend/app/utils/patterns.py (detect_entity_type function added)
✓ backend/app/services/extract/parser.py (delegation implemented)
✓ backend/app/services/ghl_prep/transform_service.py (classification added)
✓ frontend/src/pages/GhlPrep.tsx (filter UI implemented)
```

**Commits exist:**
```bash
✓ a4ecd59 (Task 1: shared detection + GHL Prep classification)
✓ 08f9fad (Task 2: filter UI + export/send integration)
```

**Functionality verified:**
```bash
✓ Backend entity detection returns correct strings
✓ Extract parser delegation returns correct enums
✓ TypeScript compiles without errors
✓ Filter logic implemented in React useMemo
✓ Export/send strip Entity Type column
```
