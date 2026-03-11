---
phase: 02-encryption-hardening
plan: 01
subsystem: auth
tags: [fernet, encryption, api-keys, firestore, startup-validation]

# Dependency graph
requires:
  - phase: 01-auth-cors
    provides: environment field on Settings, CORS/auth middleware
provides:
  - Startup ENCRYPTION_KEY validation (production crash guard)
  - Hardened encrypt_value/decrypt_value with production-safe failure modes
  - Encrypt-on-save / decrypt-on-read at admin settings storage boundary
affects: [03-test-suite]

# Tech tracking
tech-stack:
  added: []
  patterns: [storage-boundary-encryption, fail-fast-startup-validation]

key-files:
  created: []
  modified:
    - backend/app/main.py
    - backend/app/services/shared/encryption.py
    - backend/app/api/admin.py

key-decisions:
  - "Production encrypt_value raises ValueError on failure instead of silent plaintext fallback"
  - "Production decrypt_value returns None on failure so feature appears unconfigured (admin re-enters key)"
  - "Encrypt/decrypt happens at storage boundary (save/load), not at runtime config level"

patterns-established:
  - "Storage-boundary encryption: encrypt before JSON/Firestore write, decrypt after read"
  - "Fail-fast startup: production requires critical env vars or SystemExit(1)"

requirements-completed: [ENC-01, ENC-02]

# Metrics
duration: 2min
completed: 2026-03-11
---

# Phase 2 Plan 1: Encryption Hardening Summary

**Startup ENCRYPTION_KEY guard with storage-boundary encrypt/decrypt for admin API keys using Fernet**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-11T13:14:00Z
- **Completed:** 2026-03-11T13:16:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Production startup crashes with SystemExit(1) when ENCRYPTION_KEY is missing, with key generation command in error message
- encrypt_value raises ValueError in production on failure; decrypt_value returns None in production on failure
- All admin API keys (gemini, google_maps, pdl, searchbug) encrypted at storage boundary via _SENSITIVE_FIELDS list
- Pre-encryption plaintext values pass through unchanged (migration-safe)
- Dev mode preserves existing plaintext fallback with warning logs

## Task Commits

Each task was committed atomically:

1. **Task 1: Startup ENCRYPTION_KEY validation and hardened encrypt/decrypt** - `7f5620b` (feat)
2. **Task 2: Encrypt-on-save and decrypt-on-read at settings storage boundary** - `6e40ee6` (feat)

## Files Created/Modified
- `backend/app/main.py` - Added ENCRYPTION_KEY startup guard (production crash, dev warning)
- `backend/app/services/shared/encryption.py` - Hardened encrypt_value (raise in prod) and decrypt_value (return None in prod)
- `backend/app/api/admin.py` - Added _SENSITIVE_FIELDS, _encrypt_settings/_decrypt_settings helpers, modified save/load/init functions

## Decisions Made
- encrypt_value raises ValueError in production on failure to prevent silent plaintext storage
- decrypt_value returns None (not raw ciphertext) in production on failure so the feature appears unconfigured and admin can re-enter the key
- Encryption applied at save/load boundary rather than inside individual endpoint handlers -- cleaner separation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. ENCRYPTION_KEY is already documented in CLAUDE.md environment variables.

## Next Phase Readiness
- Encryption hardening complete, ready for test suite phase
- All 17 existing backend tests continue to pass

---
*Phase: 02-encryption-hardening*
*Completed: 2026-03-11*
