# Phase 22: Database Models & Schema - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Extend SQLAlchemy models to cover all 13 Firestore collections and initialize Alembic migration tooling. Add 3 new models (AppConfig, UserPreference, RRCCountyStatus) and auth columns (password_hash, role, scope, tools) to existing User model. Generate initial Alembic migration that creates all tables.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to incorporate:
- PyJWT + pwdlib[bcrypt] for password hashing (FastAPI official recommendation)
- AppConfig as key/JSONB table (replaces Firestore app_config collection)
- UserPreference as user_id FK + JSONB data (replaces Firestore user_preferences collection)
- RRCCountyStatus for county download tracking (replaces Firestore rrc_county_status collection)
- Use Alembic async template (`alembic init --template async`)
- 10 of 13 models already exist in db_models.py — extend, don't rewrite

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/db_models.py` — 10 existing SQLAlchemy models (User, Job, ExtractEntry, TitleEntry, ProrationRow, RevenueStatement, RevenueRow, RRCOilProration, RRCGasProration, AuditLog)
- `backend/app/core/database.py` — async engine, session factory, init_db()
- `backend/app/services/firestore_service.py` — source of truth for collection schemas (13 collections, ~40 functions)

### Established Patterns
- SQLAlchemy 2.0 style with `mapped_column()` and type annotations
- Async engine with `asyncpg` driver
- `Base = declarative_base()` shared across all models

### Integration Points
- `database.py` init_db() needs to work with Alembic
- New models must use same Base for auto-migration generation
- User model changes must be backwards-compatible with existing auth.py until Phase 23

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
