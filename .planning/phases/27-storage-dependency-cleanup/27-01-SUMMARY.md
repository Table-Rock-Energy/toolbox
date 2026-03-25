---
phase: 27-storage-dependency-cleanup
plan: 01
subsystem: infra
tags: [storage, gcs, local-filesystem, cleanup]

requires:
  - phase: 25-firestore-removal
    provides: PostgreSQL as primary database
provides:
  - Local-only storage_service.py with no GCS dependency
  - Clean requirements.txt without google-cloud-storage
  - Renamed admin settings endpoint (api-config)
  - Disabled Cloud Run CI/CD workflow
affects: [28-firebase-dependency-cleanup]

tech-stack:
  added: []
  patterns: [local-filesystem-only storage, storage_* config prefix]

key-files:
  created: []
  modified:
    - backend/app/services/storage_service.py
    - backend/app/core/config.py
    - backend/requirements.txt
    - backend/app/api/admin.py
    - backend/tests/test_auth_enforcement.py
    - backend/tests/test_pipeline.py
    - frontend/src/pages/AdminSettings.tsx
    - frontend/src/contexts/OperationContext.tsx
    - .github/workflows/deploy.yml.disabled
    - backend/app/services/firestore_service.py
    - backend/app/services/rrc_background.py

key-decisions:
  - "Renamed gcs_project_id to gcp_project_id (Firestore client still needs it)"
  - "Kept Google Cloud API key UI labels (still valid for Gemini/Maps APIs)"

patterns-established:
  - "storage_* prefix for storage folder config fields"
  - "api-config endpoint name for unified AI/Maps/batch settings"

requirements-completed: [STOR-01, STOR-02, CLEAN-01]

duration: 6min
completed: 2026-03-25
---

# Phase 27 Plan 01: Storage & Dependency Cleanup Summary

**Local-only StorageService with all GCS code paths removed, google-cloud-storage dependency stripped, admin endpoint renamed to api-config, Cloud Run CI/CD disabled**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T22:49:57Z
- **Completed:** 2026-03-25T22:55:51Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Rewrote storage_service.py to local-filesystem-only (removed ~150 lines of GCS code)
- Removed google-cloud-storage from requirements.txt
- Renamed admin settings endpoint from /settings/google-cloud to /settings/api-config
- Disabled Cloud Run deploy.yml by renaming to .disabled

## Task Commits

Each task was committed atomically:

1. **Task 1: Strip GCS from storage_service.py, config.py, and requirements.txt** - `396dd73` (feat)
2. **Task 2: Update all consumers, rename admin endpoint, disable CI/CD** - `b0c493b` (feat)

## Files Created/Modified
- `backend/app/services/storage_service.py` - Local-only storage service (removed all GCS imports, methods, branching)
- `backend/app/core/config.py` - Removed gcs_bucket_name, gcs_project_id, use_gcs; added gcp_project_id; renamed folder fields
- `backend/requirements.txt` - Removed google-cloud-storage dependency
- `backend/app/api/admin.py` - Renamed GoogleCloudSettings* to ApiSettings*, endpoint to api-config
- `backend/tests/test_auth_enforcement.py` - Updated endpoint URL in auth test
- `backend/tests/test_pipeline.py` - Updated model import name in batch test
- `frontend/src/pages/AdminSettings.tsx` - Updated interface, state vars, fetch URLs, handler names
- `frontend/src/contexts/OperationContext.tsx` - Updated batch config fetch URL
- `.github/workflows/deploy.yml.disabled` - Renamed from deploy.yml
- `backend/app/services/firestore_service.py` - Updated gcs_project_id to gcp_project_id
- `backend/app/services/rrc_background.py` - Updated gcs_project_id to gcp_project_id

## Decisions Made
- Renamed gcs_project_id to gcp_project_id (not removed entirely) because Firestore client still needs it during the migration period
- Kept Google Cloud API key labels in AdminSettings UI since they still refer to valid Google API keys for Gemini/Maps

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed gcs_project_id references in Firestore clients**
- **Found during:** Task 2 verification
- **Issue:** firestore_service.py and rrc_background.py referenced settings.gcs_project_id which was removed in Task 1
- **Fix:** Added gcp_project_id field to config.py, updated both Firestore client references
- **Files modified:** backend/app/core/config.py, backend/app/services/firestore_service.py, backend/app/services/rrc_background.py
- **Verification:** Python import check passed
- **Committed in:** b0c493b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix to prevent import errors. No scope creep.

## Issues Encountered
None

## Known Stubs
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Storage is fully local, ready for remaining dependency cleanup
- Firestore and Firebase dependencies remain (separate cleanup phases)

---
*Phase: 27-storage-dependency-cleanup*
*Completed: 2026-03-25*
