---
phase: 27-storage-dependency-cleanup
plan: 02
subsystem: database
tags: [firestore, postgresql, migration, sqlalchemy, cli]

requires:
  - phase: 22-database-models
    provides: SQLAlchemy models for all tables
  - phase: 25-firestore-removal
    provides: PostgreSQL as sole database backend
provides:
  - One-time Firestore-to-PostgreSQL migration script with CLI interface
  - Per-collection migration handlers for all 16 Firestore collections
  - Batch processing for large RRC datasets
affects: [deployment, production-cutover]

tech-stack:
  added: [firebase-admin (one-time migration dep), google-cloud-firestore (one-time migration dep)]
  patterns: [standalone CLI migration script, batch insert with progress logging]

key-files:
  created:
    - backend/scripts/migrate_firestore_to_postgres.py
  modified: []

key-decisions:
  - "firebase-admin and google-cloud-firestore are NOT in requirements.txt -- one-time pip install for migration only"
  - "Sync psycopg2 engine for migration (not asyncpg) -- standalone CLI script, no async needed"
  - "Revenue rows migrated from both inline array and subcollection paths"

patterns-established:
  - "Migration script pattern: argparse CLI + per-collection handler functions + summary table"

requirements-completed: [DB-04]

duration: 2min
completed: 2026-03-25
---

# Phase 27 Plan 02: Firestore-to-PostgreSQL Migration Script Summary

**Standalone CLI migration script with 16 collection handlers, batch processing for RRC data, dry-run mode, and per-table count verification**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-25T22:50:06Z
- **Completed:** 2026-03-25T22:52:34Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created 928-line migration script covering all 16 Firestore collections
- Batch processing (500 at a time) for large RRC oil/gas proration tables
- CLI with --service-account, --database-url, --dry-run, and --collections flags
- Per-table count verification summary with Firestore vs PostgreSQL row counts

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Firestore-to-PostgreSQL migration script** - `26e6ed1` (feat)

## Files Created/Modified
- `backend/scripts/migrate_firestore_to_postgres.py` - One-time migration CLI script with per-collection handlers, safe type converters, batch insert for large tables, and verification summary

## Decisions Made
- firebase-admin and google-cloud-firestore are one-time dependencies documented in script header comments, not added to requirements.txt
- Used sync psycopg2 engine (not asyncpg) since the script is a standalone CLI, not part of the async app
- Revenue statement rows checked in both inline array and Firestore subcollection paths to handle either storage pattern
- User password_hash skipped during migration (users will re-register with local JWT auth)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Migration script ready for production use when Firestore service account key is available
- Run with: `pip install firebase-admin google-cloud-firestore psycopg2-binary` then execute the script
- Recommend --dry-run first to verify Firestore connectivity and collection counts

---
*Phase: 27-storage-dependency-cleanup*
*Completed: 2026-03-25*
