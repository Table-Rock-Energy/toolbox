---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Full On-Prem Migration
status: Ready to execute
stopped_at: Completed 25-01-PLAN.md
last_updated: "2026-03-25T21:38:26.225Z"
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 9
  completed_plans: 7
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results.
**Current focus:** Phase 25 — Database Service Port

## Current Position

Phase: 25 (Database Service Port) — EXECUTING
Plan: 2 of 3

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

### Pending Todos

None.

### Blockers/Concerns

- [v1.6]: EnrichmentToolbar component still exported from barrel (unused, cleanup candidate)
- [v2.0]: Firestore implicit schemas -- audit during DB phases for fields not in SQLAlchemy models

## Session Continuity

Last session: 2026-03-25T21:38:26.222Z
Stopped at: Completed 25-01-PLAN.md
Resume file: None
