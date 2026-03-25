---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Full On-Prem Migration
status: Ready to execute
stopped_at: Completed 22-01-PLAN.md
last_updated: "2026-03-25T19:18:40.069Z"
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 2
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results.
**Current focus:** Phase 22 — Database Models & Schema

## Current Position

Phase: 22 (Database Models & Schema) — EXECUTING
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

### Pending Todos

None.

### Blockers/Concerns

- [v1.6]: EnrichmentToolbar component still exported from barrel (unused, cleanup candidate)
- [v2.0]: Firestore implicit schemas -- audit during DB phases for fields not in SQLAlchemy models

## Session Continuity

Last session: 2026-03-25T19:18:40.067Z
Stopped at: Completed 22-01-PLAN.md
Resume file: None
