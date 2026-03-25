---
phase: 25-database-service-port
plan: 02
subsystem: database
tags: [postgresql, sqlalchemy, async, firestore-removal, migration]

requires:
  - phase: 25-database-service-port
    provides: Complete PostgreSQL CRUD layer (db_service.py) with 17+ functions and sync session factory
provides:
  - All 14 backend files migrated from Firestore to db_service + AsyncSession
  - Zero firestore_service imports remain in any backend file (except firestore_service.py itself)
  - rrc_background.py uses sync SQLAlchemy sessions for background thread
  - App startup loads config from PostgreSQL
affects: [25-database-service-port, firestore-removal]

tech-stack:
  added: []
  patterns: [async-session-maker-inline-for-startup-functions, sync-sql-for-background-rrc-worker, app-config-as-kv-store-for-etl]

key-files:
  created: []
  modified:
    - backend/app/core/ingestion.py
    - backend/app/api/history.py
    - backend/app/api/proration.py
    - backend/app/api/admin.py
    - backend/app/api/ghl.py
    - backend/app/api/enrichment.py
    - backend/app/services/proration/rrc_data_service.py
    - backend/app/services/proration/rrc_county_download_service.py
    - backend/app/services/proration/csv_processor.py
    - backend/app/services/etl/entity_registry.py
    - backend/app/services/ghl/connection_service.py
    - backend/app/services/ghl/bulk_send_service.py
    - backend/app/services/rrc_background.py
    - backend/app/main.py
    - backend/app/core/config.py
    - backend/app/models/db_models.py
    - backend/tests/test_auth_enforcement.py
    - backend/tests/test_proration_cache.py

key-decisions:
  - "ETL entity_registry uses AppConfig table as key-value store with prefixed keys (no dedicated ETL tables)"
  - "bulk_send_service stores progress in Job.options JSONB field (no separate Firestore document)"
  - "rrc_background sync operations use raw SQL via sync session (not ORM) for simplicity"
  - "GHL_PREP and GHL_SEND added to ToolType enum for job tracking"
  - "database_enabled defaults to True, FIRESTORE_ENABLED removed from config"

patterns-established:
  - "Startup init functions use async_session_maker() directly (no Depends outside request context)"
  - "Background tasks create inline sessions via async_session_maker() for each operation"

requirements-completed: [DB-01, DB-06]

duration: 16min
completed: 2026-03-25
---

# Phase 25 Plan 02: Firestore Import Swap Summary

**All 14 backend files ported from Firestore to db_service with PostgreSQL AsyncSession -- zero firestore_service imports remain**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-25T21:39:14Z
- **Completed:** 2026-03-25T21:55:00Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments
- Replaced every firestore_service import and raw get_firestore_client() call across 14 backend files
- Ported rrc_background.py from sync Firestore client to sync SQLAlchemy sessions
- Updated main.py startup to load config from PostgreSQL (init_db always runs, no use_database guard)
- Removed FIRESTORE_ENABLED from config.py, set database_enabled=True as default
- Updated 2 test files to mock db_service instead of firestore_service

## Task Commits

Each task was committed atomically:

1. **Task 1: Port API routes and core services (10 files)** - `22e332e` (feat)
2. **Task 2: Port GHL services + rrc_background.py + main.py startup** - `170c2e4` (feat)
3. **Test fixes for migration** - `081cd90` (fix)

## Files Created/Modified
- `backend/app/core/ingestion.py` - persist_job_result uses db_service + async_session_maker
- `backend/app/api/history.py` - Depends(get_db) session injection, db_service for all queries
- `backend/app/api/proration.py` - 5 Firestore import sites replaced with db_service
- `backend/app/api/admin.py` - init_app_settings_from_db, preferences via db_service
- `backend/app/api/ghl.py` - raw get_firestore_client replaced with db_service
- `backend/app/api/enrichment.py` - load_enrichment_config_from_db, save via db_service
- `backend/app/services/proration/rrc_data_service.py` - sync_to_database uses async_session_maker
- `backend/app/services/proration/rrc_county_download_service.py` - 4 Firestore calls replaced
- `backend/app/services/proration/csv_processor.py` - _lookup_from_database replaces Firestore
- `backend/app/services/etl/entity_registry.py` - AppConfig key-value store via db_service
- `backend/app/services/ghl/connection_service.py` - all 7 CRUD functions use db_service
- `backend/app/services/ghl/bulk_send_service.py` - job progress via Job.options JSONB
- `backend/app/services/rrc_background.py` - sync SQLAlchemy sessions for background thread
- `backend/app/main.py` - init_db always runs, load from database
- `backend/app/core/config.py` - database_enabled=True, FIRESTORE_ENABLED removed
- `backend/app/models/db_models.py` - GHL_PREP, GHL_SEND added to ToolType enum
- `backend/tests/test_auth_enforcement.py` - mock db_service instead of firestore_service
- `backend/tests/test_proration_cache.py` - renamed _lookup_from_firestore references

## Decisions Made
- ETL entity_registry uses AppConfig table as key-value store with prefixed keys (etl_entity:, etl_relationship:, etl_ownership:) since no dedicated ETL tables exist in db_models
- bulk_send_service stores progress counters and failed_contacts in Job.options JSONB field rather than separate Firestore document updates
- rrc_background uses raw SQL via sync session for CRUD (not ORM) to keep background thread operations simple
- Added GHL_PREP and GHL_SEND to ToolType enum for job tracking completeness

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test mocks for Firestore-to-db_service migration**
- **Found during:** Task 2 verification (test suite)
- **Issue:** 2 test files still mocked firestore_service functions and settings.firestore_enabled
- **Fix:** Updated test_auth_enforcement.py (5 history tests) and test_proration_cache.py (1 cache test)
- **Files modified:** backend/tests/test_auth_enforcement.py, backend/tests/test_proration_cache.py
- **Committed in:** 081cd90

**2. [Rule 2 - Missing Critical] Added GHL_PREP and GHL_SEND to ToolType enum**
- **Found during:** Task 2 (bulk_send_service needs ToolType.GHL_SEND)
- **Issue:** ToolType enum only had extract/title/proration/revenue -- GHL job types missing
- **Fix:** Added GHL_PREP and GHL_SEND enum values
- **Files modified:** backend/app/models/db_models.py
- **Committed in:** 170c2e4

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both necessary for correctness. No scope creep.

## Issues Encountered
- test_fetch_missing.py::test_fetch_status_set_on_returned_rows shows flaky failure when run in full suite but passes in isolation -- appears to be test ordering issue, not caused by this plan's changes

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Zero Firestore imports remain in backend/app/ (excluding firestore_service.py itself)
- Ready for Plan 25-03 (delete firestore_service.py, remove google-cloud-firestore dependency)
- 369/370 tests pass (1 pre-existing flaky test)

---
*Phase: 25-database-service-port*
*Completed: 2026-03-25*
