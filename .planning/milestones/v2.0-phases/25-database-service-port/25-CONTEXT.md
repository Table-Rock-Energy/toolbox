# Phase 25: Database Service Port - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Replace every Firestore service function with a PostgreSQL equivalent using SQLAlchemy async sessions. Delete firestore_service.py and all Firestore imports/dependencies. RRC background worker must use sync SQLAlchemy sessions (runs outside event loop). All existing tests must pass with PostgreSQL as sole database. firebase-admin package has zero remaining import sites.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key decisions from research and prior phases:
- Use FastAPI Depends() with async generator for session lifecycle (from Pitfall 2 in PITFALLS.md)
- RRC background worker needs SEPARATE sync Session factory (existing pattern: _get_sync_firestore_client)
- Set pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True
- Keep JSONB for RRC raw_data fields (don't normalize)
- Revenue statement rows: parent RevenueStatement row first (FK), then insert each RevenueRow
- 13 Firestore collections → 17 PostgreSQL tables (models from Phase 22)
- db_service.py should mirror firestore_service.py function signatures for easy swap
- Update all service imports from firestore_service to db_service
- Delete firestore_service.py last after all imports are updated

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/firestore_service.py` — source of truth for function signatures (~40 functions, 13 collections)
- `backend/app/services/db_service.py` — may already exist with some PostgreSQL functions
- `backend/app/models/db_models.py` — all 17 SQLAlchemy models (Phase 22)
- `backend/app/core/database.py` — async engine, session factory
- `backend/app/services/rrc_background.py` — background worker using sync Firestore client

### Established Patterns
- Firestore: lazy init with _db global, batch commits every 500 docs
- PostgreSQL equivalent: async session per request via Depends(), session.add_all() for bulk

### Integration Points
- Every API route file imports from firestore_service (extract, title, proration, revenue, ghl_prep, ghl, enrichment, ai_validation, admin, history, etl)
- rrc_background.py uses _get_sync_firestore_client() — needs sync SQLAlchemy equivalent
- storage_service.py uses Firestore for some metadata — check and port
- config.py has FIRESTORE_ENABLED toggle — remove after port

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
