---
phase: 08-ghl-prep-tool
plan: 01
subsystem: ghl-prep
tags: [backend, csv-transformation, api]
completed: 2026-02-26

dependency_graph:
  requires: []
  provides: [ghl-prep-backend]
  affects: [toolbox-api]

tech_stack:
  added:
    - pandas (CSV processing)
    - json (stdlib, campaign extraction)
  patterns:
    - FastAPI router with ingestion helpers
    - Pydantic models with Field descriptors
    - pandas DataFrame transformations
    - fire-and-forget Firestore persistence

key_files:
  created:
    - toolbox/backend/app/models/ghl_prep.py
    - toolbox/backend/app/services/ghl_prep/__init__.py
    - toolbox/backend/app/services/ghl_prep/transform_service.py
    - toolbox/backend/app/services/ghl_prep/export_service.py
    - toolbox/backend/app/api/ghl_prep.py
  modified:
    - toolbox/backend/app/main.py
    - toolbox/backend/app/core/ingestion.py

decisions:
  - what: "Skip entry persistence for ghl_prep transformations"
    rationale: "Transformed rows are ephemeral (user downloads immediately), only job metadata needs persistence"
    alternative: "Save all transformed rows to Firestore"
    chosen_because: "Reduces storage costs and follows the pattern that transformations != entities"
  - what: "Use pandas for all CSV operations"
    rationale: "Consistent with existing toolbox patterns, handles encoding issues, preserves column order"
    alternative: "Use csv stdlib module"
    chosen_because: "Pandas provides robust CSV handling with automatic type inference and encoding fallback"
  - what: "Title-case with special prefix handling (Mc/Mac/O')"
    rationale: "Common names like McDonald and O'Brien must be formatted correctly for professional output"
    alternative: "Simple str.title() without special cases"
    chosen_because: "Users specifically requested proper name formatting for GoHighLevel imports"

metrics:
  duration: 297
  tasks: 2
  commits: 2
  files_created: 5
  files_modified: 2
  lines_added: 476
---

# Phase 08 Plan 01: GHL Prep Backend Summary

**One-liner:** Complete GHL Prep backend with CSV transformation (title-casing with Mc/Mac/O' handling, campaign JSON extraction, phone mapping, contact owner column) and API endpoints.

## What Was Built

Built the complete backend for the GHL Prep tool, which transforms Mineral export CSVs into GoHighLevel-ready import files. The implementation provides:

1. **Pydantic Models** (ghl_prep.py): `TransformResult`, `UploadResponse`, `ExportRequest` with full field documentation
2. **Transformation Service** (transform_service.py): Four transformations applied to CSV data:
   - Title-casing for name/address fields with intelligent prefix handling (Mc → McDonald, Mac → MacArthur, O' → O'Brien)
   - Uppercase suffix preservation (LLC, LP, Inc, Jr, Sr, II, III, IV)
   - Campaign JSON extraction (array with unit_name → plain text)
   - Phone 1 → Phone column mapping
   - Contact Owner column addition if missing
3. **Export Service** (export_service.py): CSV generation and filename suffix logic
4. **API Routes** (ghl_prep.py):
   - POST /api/ghl-prep/upload (accepts CSV, returns transformed data)
   - POST /api/ghl-prep/export/csv (generates downloadable CSV)
   - GET /api/ghl-prep/health (health check)
5. **Integration**: Router registered in main.py, ingestion.py updated to skip entry persistence for ghl_prep

## Key Features

- **All original columns preserved**: Transformation is non-destructive, adds/modifies in-place
- **Encoding fallback**: UTF-8 with automatic latin-1 fallback for problematic files
- **Transformation counts**: Tracks how many values were changed for each transformation type
- **Warnings**: Reports missing columns (Campaigns, Phone 1, Contact Owner) without failing
- **Fire-and-forget persistence**: Job metadata saved to Firestore for observability without blocking response

## Technical Highlights

**Title-casing algorithm**:
```python
# Handles: "JOHN MCDONALD" → "John McDonald"
#          "MARY O BRIEN" → "Mary O'Brien"
#          "ACME OIL LLC" → "Acme Oil LLC"
result = text.title()
result = re.sub(r'\bMc([a-z])', lambda m: f"Mc{m.group(1).upper()}", result)
result = re.sub(r"\bO'([a-z])", lambda m: f"O'{m.group(1).upper()}", result)
# Preserve uppercase suffixes...
```

**Campaign extraction with JSON fallback**:
```python
# Tries JSON parsing, falls back to raw value if not valid JSON
data = json.loads(text)
if isinstance(data, list) and data[0].get("unit_name"):
    return data[0]["unit_name"]
```

## Deviations from Plan

None - plan executed exactly as written.

## Testing

All automated verification tests passed:
- ✅ `title_case_name('JOHN MCDONALD')` → `'John McDonald'`
- ✅ `title_case_name('MARY O BRIEN')` → `"Mary O'Brien"`
- ✅ `title_case_name('ACME OIL LLC')` → `'Acme Oil LLC'`
- ✅ `transform_csv()` with sample data produces correct title-casing, campaign extraction, phone mapping, and contact owner addition
- ✅ Router has expected routes (`/upload`, `/export/csv`, `/health`)
- ✅ Router registered in main.py with `/api/ghl-prep` prefix
- ✅ All modules import successfully

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 4218f1c | feat(08-01): add GHL Prep models and transformation service | ghl_prep.py, transform_service.py, __init__.py |
| f0070fd | feat(08-01): add GHL Prep API routes and export service | ghl_prep.py (api), export_service.py, main.py, ingestion.py |

## Next Steps

Plan 08-02 will add the frontend React component to complete the GHL Prep tool UI.

## Self-Check: PASSED

**Created files verified:**
```bash
✅ toolbox/backend/app/models/ghl_prep.py
✅ toolbox/backend/app/services/ghl_prep/__init__.py
✅ toolbox/backend/app/services/ghl_prep/transform_service.py
✅ toolbox/backend/app/services/ghl_prep/export_service.py
✅ toolbox/backend/app/api/ghl_prep.py
```

**Modified files verified:**
```bash
✅ toolbox/backend/app/main.py (ghl_prep_router imported and registered)
✅ toolbox/backend/app/core/ingestion.py (ghl_prep handling added)
```

**Commits verified:**
```bash
✅ 4218f1c exists: feat(08-01): add GHL Prep models and transformation service
✅ f0070fd exists: feat(08-01): add GHL Prep API routes and export service
```

All files created, all commits recorded, all verifications passed.
