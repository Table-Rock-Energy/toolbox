---
phase: 23-auth-backend
plan: 01
subsystem: auth
tags: [jwt, pyjwt, pwdlib, bcrypt, fastapi, postgresql, sqlalchemy]

requires:
  - phase: 22-database-models
    provides: User model with password_hash, role, scope, tools columns; async_session_maker
provides:
  - JWT-based auth middleware replacing Firebase token verification
  - Password hashing via pwdlib[bcrypt]
  - JWT token create/decode helpers in core/security.py
  - DB-backed user lookup in get_current_user
  - Async set_user_password using PostgreSQL
  - JWT_SECRET_KEY fail-fast startup check
affects: [23-auth-backend, 24-auth-frontend, 25-firebase-removal]

tech-stack:
  added: [pwdlib, bcrypt]
  patterns: [JWT decode in auth middleware, DB user lookup via async_session_maker, dual-path admin check]

key-files:
  created: [backend/app/core/security.py]
  modified: [backend/app/core/auth.py, backend/app/core/config.py, backend/app/api/ghl.py, backend/app/api/admin.py, backend/app/main.py, backend/requirements.txt, backend/tests/test_auth_enforcement.py]

key-decisions:
  - "BcryptHasher explicit instantiation (PasswordHash.recommended() requires argon2)"
  - "is_user_admin keeps JSON allowlist check (intentional dual-path until Phase 25)"
  - "require_admin checks user dict role with james@ fallback (DB path)"

patterns-established:
  - "JWT auth: decode_access_token in core/security.py, DB lookup in get_current_user"
  - "Password management: async set_user_password writes hash to PostgreSQL User model"

requirements-completed: [AUTH-03]

duration: 20min
completed: 2026-03-25
---

# Phase 23 Plan 01: JWT Auth Middleware Summary

**JWT-based auth middleware replacing Firebase token verification, with pwdlib password hashing, DB user lookup, and SSE token validation**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-25T19:48:05Z
- **Completed:** 2026-03-25T20:08:26Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Created security module with password hashing (pwdlib/bcrypt) and JWT token helpers (PyJWT)
- Rewrote auth.py to verify JWT tokens and look up users in PostgreSQL instead of Firebase
- Fixed SSE endpoint, admin password flows, and startup checks for JWT

## Task Commits

Each task was committed atomically:

1. **Task 1: Create security module and add JWT config settings** - `77a0cc3` (feat)
2. **Task 2: Rewrite auth.py, fix SSE auth, fix admin password, add startup check** - `256c275` (feat)

## Files Created/Modified
- `backend/app/core/security.py` - Password hashing (pwdlib/bcrypt) and JWT token create/decode helpers
- `backend/app/core/config.py` - Added jwt_secret_key, jwt_algorithm, jwt_expire_minutes settings
- `backend/app/core/auth.py` - JWT decode replaces Firebase verify, DB user lookup, async set_user_password
- `backend/app/api/ghl.py` - SSE auth uses decode_access_token instead of Firebase
- `backend/app/api/admin.py` - set_user_password calls are now awaited (async)
- `backend/app/main.py` - JWT_SECRET_KEY fail-fast check, removed init_allowlist_from_firestore
- `backend/requirements.txt` - Added pwdlib[bcrypt]>=0.2.0
- `backend/tests/test_auth_enforcement.py` - Updated test_no_dev_mode_bypass to remove Firebase mock

## Decisions Made
- Used `BcryptHasher()` explicit instantiation instead of `PasswordHash.recommended()` because recommended() requires argon2 which is not installed
- Kept is_user_admin with JSON allowlist check (intentional dual-path during migration, Phase 25 unifies)
- require_admin checks `user.get("role") == "admin"` from JWT-decoded user dict with james@ email fallback

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PasswordHash.recommended() requiring argon2**
- **Found during:** Task 1 (security module creation)
- **Issue:** `PasswordHash.recommended()` requires argon2 module which is not installed
- **Fix:** Used explicit `PasswordHash((BcryptHasher(),))` instantiation
- **Files modified:** backend/app/core/security.py
- **Committed in:** 77a0cc3

**2. [Rule 1 - Bug] Fixed test_no_dev_mode_bypass patching removed function**
- **Found during:** Task 2 (test suite verification)
- **Issue:** Test patched `get_firebase_app` which no longer exists in auth.py
- **Fix:** Removed the patch -- invalid JWT tokens naturally fail decode and return 401
- **Files modified:** backend/tests/test_auth_enforcement.py
- **Committed in:** 256c275

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- JWT auth middleware is in place, ready for Plan 02 (login/me endpoints + seed script)
- Existing test suite passes (357 tests, 0 failures)
- Allowlist functions preserved for admin.py compatibility during migration

---
*Phase: 23-auth-backend*
*Completed: 2026-03-25*
