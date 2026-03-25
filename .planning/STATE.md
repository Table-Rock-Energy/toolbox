---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Full On-Prem Migration
status: active
stopped_at: null
last_updated: "2026-03-25"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results.
**Current focus:** v2.0 Full On-Prem Migration — remove all Google cloud dependencies.

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-25 — Milestone v2.0 started

## Accumulated Context

### Decisions

- Remove Firestore entirely (no toggle) — PostgreSQL is the only database
- Admin-only user creation (no self-registration)
- One-time migration script for Firestore→PostgreSQL
- Do NOT touch Dockerfile, docker-compose, or CI/CD

### Pending Todos

None.

### Blockers/Concerns

- [v1.6]: EnrichmentToolbar component still exported from barrel (unused, cleanup candidate)

## Session Continuity

Last session: 2026-03-25
Stopped at: Defining requirements for v2.0
Resume file: None
