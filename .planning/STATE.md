---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Full On-Prem Migration
status: Ready to execute
stopped_at: Completed 26-01-PLAN.md
last_updated: "2026-03-25T22:24:28.210Z"
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 11
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results.
**Current focus:** Phase 26 — AI Provider Swap

## Current Position

Phase: 26 (AI Provider Swap) — EXECUTING
Plan: 2 of 2

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: --
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

## Accumulated Context

| Phase 22-01 P01 | 2min | 1 tasks | 2 files |
| Phase 22 P02 | 2min | 2 tasks | 5 files |
| Phase 23 P01 | 20min | 2 tasks | 8 files |
| Phase 23 P02 | 13min | 2 tasks | 6 files |
| Phase 24 P01 | 3min | 2 tasks | 4 files |
| Phase 24 P02 | 4min | 2 tasks | 12 files |
| Phase 25 P01 | 13min | 2 tasks | 2 files |
| Phase 25 P02 | 16 | 2 tasks | 18 files |
| Phase 25 P03 | 6min | 2 tasks | 24 files |
| Phase 26-ai-provider-swap P01 | 3min | 1 tasks | 6 files |

### Decisions

- Remove Firestore entirely (no toggle) -- PostgreSQL is the only database
- Admin-only user creation (no self-registration)
- PyJWT + pwdlib[bcrypt] for auth (FastAPI official recommendations)
- openai SDK for LM Studio (OpenAI-compatible API)
- Alembic for migrations (not create_all)
- 24-hour JWT expiry, no refresh tokens (small internal team)
- Do NOT touch Dockerfile, docker-compose, or CI/CD
- [Phase 22-01]: String columns for role/status fields instead of PostgreSQL Enum types
- [Phase 22-01]: User.id gets uuid4 default callable for local auth
- [Phase 22]: env.py overrides sqlalchemy.url from app settings (single source of truth for DB URL)
- [Phase 22]: init_db() guarded by alembic_version table check (safe coexistence with Alembic)
- [Phase 23]: BcryptHasher explicit instantiation (PasswordHash.recommended() requires argon2)
- [Phase 23]: is_user_admin keeps JSON allowlist check (dual-path until Phase 25)
- [Phase 23]: require_admin checks user dict role with james@ email fallback
- [Phase 23]: Auth router mounted without router-level auth (login is public)
- [Phase 23]: LoginResponse includes full UserProfile with is_admin flag
- [Phase 24]: getToken is synchronous (localStorage read) -- no async for token access
- [Phase 24]: 401 handler clears session immediately, no retry (no refresh tokens)
- [Phase 24]: LocalUser keeps photoURL/displayName for Sidebar compatibility
- [Phase 24]: authHeaders is synchronous in all files (localStorage read)
- [Phase 24]: Password minimum raised from 6 to 8 chars in Settings UI to match backend
- [Phase 25]: lookup_rrc_acres returns dict (not tuple) matching Firestore shape for drop-in replacement
- [Phase 25]: Sync engine pool_size=2 for conservative background thread usage
- [Phase 25]: ETL entity_registry uses AppConfig table as key-value store with prefixed keys
- [Phase 25]: bulk_send_service stores progress in Job.options JSONB field
- [Phase 25]: database_enabled defaults to True, FIRESTORE_ENABLED removed from config
- [Phase 25]: Mock db_service.lookup_rrc_acres with session parameter to match PostgreSQL signature
- [Phase 25]: Purge all Firestore references from comments and docstrings (not just imports)
- [Phase 26]: openai SDK for LM Studio (OpenAI-compatible API, same SDK)
- [Phase 26]: Gemini legacy fallback in factory until Plan 02 removes it
- [Phase 26]: No rate limiting for local LM Studio inference

### Pending Todos

None.

### Blockers/Concerns

- [v1.6]: EnrichmentToolbar component still exported from barrel (unused, cleanup candidate)
- [v2.0]: Firestore implicit schemas -- audit during DB phases for fields not in SQLAlchemy models

## Session Continuity

Last session: 2026-03-25T22:24:28.208Z
Stopped at: Completed 26-01-PLAN.md
Resume file: None
