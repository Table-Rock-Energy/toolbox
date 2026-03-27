---
phase: 29-firebase-config-cleanup
plan: 01
subsystem: infra
tags: [dockerfile, config, pydantic-settings, cleanup]

requires:
  - phase: 28-security-headers
    provides: working deployment pipeline
provides:
  - Clean Dockerfile without dead Firebase ARGs
  - Configurable DEFAULT_ADMIN_EMAIL env var with fallback default
affects: [deployment, admin-management]

tech-stack:
  added: []
  patterns:
    - "Admin email from Pydantic Settings instead of hardcoded constant"

key-files:
  created: []
  modified:
    - Dockerfile
    - backend/app/core/config.py
    - backend/app/core/auth.py
    - backend/app/api/admin.py
    - backend/scripts/create_admin.py

key-decisions:
  - "Default admin email stored as Pydantic Settings field with env var override (DEFAULT_ADMIN_EMAIL)"

patterns-established:
  - "Configurable defaults: use Settings fields with env var overrides instead of module-level constants"

requirements-completed: [CLEAN-02, CLEAN-03]

duration: 3min
completed: 2026-03-27
---

# Phase 29 Plan 01: Firebase Config Cleanup Summary

**Removed 7 dead VITE_FIREBASE_* Docker ARGs and extracted hardcoded admin email to configurable DEFAULT_ADMIN_EMAIL setting**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T13:40:51Z
- **Completed:** 2026-03-27T13:44:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Dockerfile reduced by 16 lines, no more dead Firebase build args
- Admin email configurable via DEFAULT_ADMIN_EMAIL env var across auth.py, admin.py, create_admin.py
- Fallback default preserved as james@tablerocktx.com in config.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove Firebase ARGs from Dockerfile** - `aad5570` (chore)
2. **Task 2: Extract admin email to config setting** - `68d614b` (refactor)

## Files Created/Modified
- `Dockerfile` - Removed 7 VITE_FIREBASE_* ARGs and multi-line build command
- `backend/app/core/config.py` - Added default_admin_email setting
- `backend/app/core/auth.py` - Replaced DEFAULT_ADMIN_EMAIL constant and hardcoded email with settings.default_admin_email
- `backend/app/api/admin.py` - Replaced hardcoded email in remove_user with settings.default_admin_email
- `backend/scripts/create_admin.py` - Replaced 4 hardcoded email references with settings.default_admin_email

## Decisions Made
- Default admin email stored as Pydantic Settings field (maps to DEFAULT_ADMIN_EMAIL env var) rather than module-level constant

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Dockerfile clean for deployment
- Admin email configurable without code changes
- All existing tests unaffected (test fixtures use hardcoded emails intentionally)

---
*Phase: 29-firebase-config-cleanup*
*Completed: 2026-03-27*
