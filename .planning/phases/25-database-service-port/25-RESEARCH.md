# Phase 25: Database Service Port - Research

**Researched:** 2026-03-25
**Domain:** SQLAlchemy async/sync service layer replacing Firestore
**Confidence:** HIGH

## Summary

Phase 25 replaces every Firestore call site with PostgreSQL equivalents via `db_service.py`, then deletes `firestore_service.py`. The existing `db_service.py` already has ~60% of the needed functions ported (jobs, entries, RRC upserts, audit logs). The remaining gap is: RRC county status CRUD, RRC metadata cache, RRC sync job tracking, GHL connection CRUD, app config get/set, user preferences get/set, `delete_job` with cascade, `lookup_rrc_by_lease_number`, and the full `lookup_rrc_acres` returning a dict (current version returns a tuple). Additionally, `rrc_background.py` uses a synchronous Firestore client that must become a sync SQLAlchemy session. Several services (`connection_service.py`, `bulk_send_service.py`, `ingestion.py`, `enrichment.py`, `admin.py`) use raw `get_firestore_client()` and must be rewritten to use `db_service` functions.

There are 35 import sites of `firestore_service` across 14 files. All must be updated. The `rrc_background.py` file is the highest-risk change because it runs in a daemon thread outside the async event loop and needs a separate sync engine.

**Primary recommendation:** Complete `db_service.py` with all missing functions first, then swap imports file-by-file (starting with simple ones like `admin.py` config/prefs), then tackle `rrc_background.py` last. Delete `firestore_service.py` as the final step.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation choices are at Claude's discretion (infrastructure phase).

### Claude's Discretion
All implementation choices are at Claude's discretion. Key decisions from research and prior phases:
- Use FastAPI Depends() with async generator for session lifecycle (from Pitfall 2 in PITFALLS.md)
- RRC background worker needs SEPARATE sync Session factory (existing pattern: _get_sync_firestore_client)
- Set pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True
- Keep JSONB for RRC raw_data fields (don't normalize)
- Revenue statement rows: parent RevenueStatement row first (FK), then insert each RevenueRow
- 13 Firestore collections -> 17 PostgreSQL tables (models from Phase 22)
- db_service.py should mirror firestore_service.py function signatures for easy swap
- Update all service imports from firestore_service to db_service
- Delete firestore_service.py last after all imports are updated

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | PostgreSQL is the sole database -- no Firestore code in any request path | Complete function gap analysis identifies all 35 import sites across 14 files; all must be ported |
| DB-05 | Every firestore_service.py function has a working PostgreSQL equivalent in db_service.py | Gap analysis below shows 15 missing functions in db_service.py that must be added |
| DB-06 | firestore_service.py deleted and all Firestore imports/dependencies removed from codebase | Import audit identifies every file; firebase-admin in requirements.txt; google.cloud.firestore in 2 files |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Use `python3` not `python` on macOS
- Backend patterns: async route handlers, `logger = logging.getLogger(__name__)` per module
- Pydantic models with Field(...) for required fields
- Firestore batch commit every 500 docs -> SQLAlchemy `session.add_all()` + `flush()` for bulk
- `from __future__ import annotations` used in services
- Lazy imports for database to avoid initialization errors
- Background tasks: run in separate thread with synchronous client
- Run tests with `make test` or `cd backend && pytest -v`

## Function Gap Analysis

### Already in db_service.py (DONE)
| Function | Notes |
|----------|-------|
| `get_or_create_user` | Takes `db: AsyncSession` as first arg |
| `get_user_by_email` | Already exists |
| `create_job` | Typed with `ToolType` enum |
| `update_job_status` | Typed with `JobStatus` enum |
| `get_job` | Already exists |
| `get_job_with_entries` | Bonus -- selectinload for all entry types |
| `get_user_jobs` | Already exists with offset param |
| `get_recent_jobs` | Already exists |
| `save_extract_entries` | Already exists |
| `get_extract_entries` | Already exists |
| `save_title_entries` | Already exists |
| `get_title_entries` | Already exists |
| `save_proration_rows` | Already exists |
| `get_proration_rows` | Already exists |
| `save_revenue_statement` | Already exists (auto-increment ID, not SHA256) |
| `get_revenue_statements` | Already exists with selectinload |
| `upsert_rrc_oil_record` | Already exists |
| `upsert_rrc_gas_record` | Already exists |
| `start_rrc_sync` | Already exists (returns RRCDataSync model) |
| `complete_rrc_sync` | Already exists |
| `get_rrc_data_status` | Already exists |
| `create_audit_log` | Already exists |
| `get_job_statistics` | Bonus -- not in firestore_service |

### Missing from db_service.py (MUST ADD)
| Function | Firestore Source | SQLAlchemy Model | Complexity |
|----------|-----------------|------------------|------------|
| `delete_job` | Lines 172-207 | Job + cascade deletes | Low (cascade handles entries) |
| `lookup_rrc_acres` (dict return) | Lines 548-599 | RRCOilProration + RRCGasProration | Med (current returns tuple, Firestore returns dict with operator/lease_name/etc) |
| `lookup_rrc_by_lease_number` | Lines 602-649 | RRCOilProration + RRCGasProration | Med (cross-district search) |
| `get_rrc_cached_status` | Lines 655-677 | RRCMetadata | Low |
| `update_rrc_metadata_counts` | Lines 680-698 | RRCMetadata | Low (merge=True -> upsert) |
| `get_counties_status` | Lines 831-855 | RRCCountyStatus | Low (batch read by keys) |
| `update_county_status` | Lines 858-869 | RRCCountyStatus | Low (upsert by key) |
| `get_all_tracked_county_keys` | Lines 872-879 | RRCCountyStatus | Low |
| `get_stale_counties` | Lines 882-928 | RRCCountyStatus | Med (date logic) |
| `get_config_doc` | Lines 969-973 | AppConfig | Low |
| `set_config_doc` | Lines 976-980 | AppConfig | Low |
| `get_user_preferences` | Lines 988-993 | UserPreference | Low |
| `set_user_preferences` | Lines 996-1002 | UserPreference | Low (upsert by user email) |

### Services Using Raw get_firestore_client() (MUST REWRITE)
These files bypass `firestore_service.py` and use the Firestore client directly. They need full rewrites to use `db_service` functions or direct SQLAlchemy queries.

| File | Functions Affected | Approach |
|------|-------------------|----------|
| `ghl/connection_service.py` | All 7 functions (CRUD + validate) | Add GHL connection CRUD to db_service.py, rewrite connection_service to use it |
| `ghl/bulk_send_service.py` | 5 direct Firestore calls (job tracking) | Replace with db_service RRC sync job functions or similar |
| `api/ghl.py` | 1 call (line 365) | Replace with db_service |
| `api/enrichment.py` | 2 calls (lines 119, 152) | Replace with db_service config functions |
| `etl/entity_registry.py` | 1 call (line 35) | Replace with db_service or direct SQLAlchemy |

### rrc_background.py -- Sync Session Required
The background worker runs in a `threading.Thread` and uses `_get_sync_firestore_client()`. Must be converted to sync SQLAlchemy.

**Pattern:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

def get_sync_engine():
    sync_url = settings.database_url.replace("+asyncpg", "")
    return create_engine(
        sync_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
    )

sync_session_factory = sessionmaker(bind=get_sync_engine())

def get_sync_session() -> Session:
    return sync_session_factory()
```

**Functions to port synchronously in rrc_background.py:**
- `create_rrc_sync_job` -> sync insert into `rrc_sync_jobs`
- `update_rrc_sync_job` -> sync update `rrc_sync_jobs`
- `add_step` -> sync update steps JSONB array
- `get_rrc_sync_job` (async) -> use async db_service
- `get_active_rrc_sync_job` (async) -> use async db_service

## Import Site Audit

Complete list of files requiring import changes (35 import sites, 14 files):

| File | Import Count | Type of Access |
|------|-------------|----------------|
| `core/ingestion.py` | 2 | `create_job`, `update_job_status`, `save_*_entries`, `save_revenue_statement` |
| `api/history.py` | 5 | `firestore_service as db` (uses get_user_jobs, get_recent_jobs, get_job, delete_job) |
| `api/proration.py` | 5 | RRC status, county status, stale counties, upsert_rrc_oil_record |
| `api/admin.py` | 4 | `set_config_doc`, `get_config_doc`, `get_user_preferences`, `set_user_preferences` |
| `api/ghl.py` | 1 | Raw `get_firestore_client()` |
| `api/enrichment.py` | 2 | Raw `get_firestore_client()` for config |
| `services/rrc_background.py` | 3 | `update_rrc_metadata_counts` + 2x `get_firestore_client` |
| `services/ghl/connection_service.py` | 6 | Raw `get_firestore_client()` throughout |
| `services/ghl/bulk_send_service.py` | 5 | Raw `get_firestore_client()` for job progress |
| `services/proration/rrc_data_service.py` | 1 | `upsert_rrc_oil_record`, `upsert_rrc_gas_record`, `start_rrc_sync`, `complete_rrc_sync` |
| `services/proration/rrc_county_download_service.py` | 4 | `get_stale_counties`, `update_county_status`, `upsert_rrc_oil_record` |
| `services/proration/csv_processor.py` | 2 | `lookup_rrc_acres`, `lookup_rrc_by_lease_number` |
| `services/etl/entity_registry.py` | 1 | Raw `get_firestore_client()` |
| `tests/test_fetch_missing.py` | 3 (mock patches) | `firestore_service.lookup_rrc_acres`, `lookup_rrc_by_lease_number` |
| `tests/test_auth_enforcement.py` | 5 (mock patches) | `firestore_service.get_user_jobs`, `get_recent_jobs`, `get_job`, `delete_job` |

## Architecture Patterns

### Session Lifecycle Pattern
Already established in `database.py`:
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Signature Compatibility Strategy
The existing `db_service.py` takes `db: AsyncSession` as the first parameter. The Firestore functions do NOT take a session (they use a global client). Two approaches for the swap:

**Approach A (recommended): Dependency injection at call sites.**
Each API route gets `db: AsyncSession = Depends(get_db)` and passes it to `db_service` functions. This is already the pattern in `db_service.py`.

For services that call Firestore functions deep in the call chain (like `csv_processor.py` calling `lookup_rrc_acres`), the session must be threaded through or obtained via `async_session_maker()` directly.

**Approach B: Module-level session factory (for deep call chains).**
For services NOT called from route handlers (like `rrc_data_service.sync_to_database`), create sessions inline:
```python
async with async_session_maker() as session:
    _, is_new, is_updated = await db_service.upsert_rrc_oil_record(session, ...)
    await session.commit()
```

### Bulk Operations
Firestore batches at 500 docs. SQLAlchemy equivalent:
```python
for i, entry_data in enumerate(entries):
    db.add(Model(**entry_data))
    if (i + 1) % 500 == 0:
        await db.flush()
await db.flush()  # final batch
```
The existing `db_service.py` already does `db.add()` in a loop then `db.flush()` -- this is fine since SQLAlchemy batches the INSERT statements efficiently.

### GHL Bulk Send Service Pattern
`bulk_send_service.py` uses raw Firestore to track GHL send job progress (5 calls). These track a GHL bulk send job, NOT an RRC sync job. Need a new pattern:
- Option 1: Reuse the existing `jobs` table with tool="ghl"
- Option 2: Add GHL-specific progress tracking functions to `db_service.py`
- Recommendation: Use the existing `jobs` table -- it already has `status`, `total_count`, `success_count`, `error_count`, `options` (JSONB for extra data)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session lifecycle | Manual open/close/commit | `get_db()` dependency already in `database.py` | Prevents connection leaks |
| Upsert logic | Manual SELECT + INSERT/UPDATE | `merge()` or existing check-then-update pattern | Already proven in db_service.py |
| Cascade deletes | Manual deletion of entries per job | SQLAlchemy `cascade="all, delete-orphan"` already on Job relationships | One `session.delete(job)` handles all entries |
| Sync engine for threads | Sharing async engine across threads | Separate `create_engine()` with `postgresql://` scheme | Prevents event loop conflicts |

## Common Pitfalls

### Pitfall 1: lookup_rrc_acres Return Type Mismatch
**What goes wrong:** The Firestore version returns a dict with `acres`, `type`, `operator`, `lease_name`, etc. The existing db_service version returns `tuple[Optional[float], Optional[str]]` (just acres and well_type). Call sites in `csv_processor.py` and `api/proration.py` expect the dict format.
**How to avoid:** Rewrite `lookup_rrc_acres` in db_service to return the same dict structure as the Firestore version. Check all call sites.

### Pitfall 2: rrc_data_service.sync_to_database Creates Its Own Event Loop
**What goes wrong:** `rrc_background.py` calls `asyncio.run(rrc_data_service.sync_to_database("oil"))`. The sync_to_database function uses Firestore async functions. After the port, it will use db_service async functions which need an AsyncSession from a pool tied to the main event loop.
**How to avoid:** Two options: (a) Make `sync_to_database` accept a session factory parameter and create sessions within the new event loop created by `asyncio.run()`. (b) Rewrite sync_to_database to use the sync session directly. Option (a) is simpler since `asyncio.run()` creates a fresh event loop -- just ensure the async engine is created within that loop, or pass a sync session.

### Pitfall 3: GHL bulk_send_service Uses Firestore for Real-Time Progress
**What goes wrong:** The SSE endpoint reads GHL send job progress from Firestore. If progress writes go to PostgreSQL but the SSE reads still expect Firestore, the progress stream shows stale data.
**How to avoid:** Port both the write side (bulk_send_service.py) and read side (api/ghl.py SSE endpoint) together.

### Pitfall 4: main.py Startup Loads Config from Firestore
**What goes wrong:** `init_app_settings_from_firestore()` and `load_enrichment_config_from_firestore()` are called at startup. These must be ported to load from PostgreSQL instead.
**How to avoid:** Replace these startup calls with PostgreSQL-based equivalents using `async_session_maker()` directly (no Depends() at startup).

### Pitfall 5: Tests Mock firestore_service Import Paths
**What goes wrong:** `test_auth_enforcement.py` has 5 patches and `test_fetch_missing.py` has 3 patches targeting `app.services.firestore_service.*`. After deletion, these break.
**How to avoid:** Update mock targets to `app.services.db_service.*` with matching function signatures. The mock return values may need adjustment (Firestore returns dicts, db_service returns SQLAlchemy models).

### Pitfall 6: user_name Missing from db_service.create_job
**What goes wrong:** Firestore's `create_job` accepts `user_name` parameter. The db_service version does NOT have this parameter. The Job model does not have a `user_name` column. Call sites that pass `user_name` will break.
**How to avoid:** Either add `user_name` to the Job model or remove it from call sites (it can be derived from the user_id FK relationship).

## Recommended Porting Order

1. **Add missing functions to db_service.py** -- all 15 functions listed above
2. **Add sync session factory to database.py** -- for rrc_background.py
3. **Port simple config/prefs** -- `admin.py` (config_doc, user_preferences)
4. **Port ingestion.py** -- swap firestore imports to db_service
5. **Port history.py** -- swap `firestore_service as db` to `db_service`
6. **Port proration routes** -- `api/proration.py`, `csv_processor.py`, `rrc_county_download_service.py`
7. **Port rrc_data_service.py** -- sync_to_database function
8. **Port rrc_background.py** -- sync Firestore client to sync SQLAlchemy
9. **Port GHL services** -- `connection_service.py`, `bulk_send_service.py`, `api/ghl.py`
10. **Port enrichment.py** -- config loading
11. **Port etl/entity_registry.py** -- raw Firestore client usage
12. **Port main.py startup** -- replace Firestore config loading
13. **Update tests** -- mock targets from firestore_service to db_service
14. **Delete firestore_service.py** -- verify zero imports remain
15. **Remove firebase-admin from requirements.txt** -- verify no `google.cloud.firestore` imports
16. **Remove FIRESTORE_ENABLED from config.py** -- clean up toggle

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && pytest -v -x` |
| Full suite command | `cd backend && pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | No Firestore imports in codebase | grep audit | `grep -r "firestore_service" backend/app/ --include="*.py"` returns empty | N/A (grep check) |
| DB-05 | All db_service functions work | unit | `cd backend && pytest tests/test_db_service.py -x` | Wave 0 |
| DB-06 | firestore_service.py deleted | filesystem | `test ! -f backend/app/services/firestore_service.py` | N/A (file check) |
| DB-06 | firebase-admin has no imports | grep audit | `grep -r "firebase_admin\|from google.cloud import firestore" backend/ --include="*.py"` returns empty | N/A (grep check) |
| DB-05 | Existing tests pass | integration | `cd backend && pytest -v` | Yes |

### Sampling Rate
- **Per task commit:** `cd backend && pytest -v -x`
- **Per wave merge:** `cd backend && pytest -v`
- **Phase gate:** Full suite green + grep audits show zero Firestore references

### Wave 0 Gaps
- [ ] `tests/test_db_service.py` -- unit tests for the 15 new db_service functions (covers DB-05)
- [ ] Update `tests/test_auth_enforcement.py` mock targets from `firestore_service` to `db_service`
- [ ] Update `tests/test_fetch_missing.py` mock targets from `firestore_service` to `db_service`

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `firestore_service.py` (1003 lines, 14 collections, ~30 functions)
- Direct codebase analysis of `db_service.py` (763 lines, ~23 functions already ported)
- Direct codebase analysis of `db_models.py` (669 lines, 17 models including all previously-missing ones)
- Direct codebase analysis of `database.py` (83 lines, async engine + session factory + get_db dependency)
- Direct codebase analysis of `rrc_background.py` (358 lines, sync Firestore client pattern)
- Grep audit of all `firestore_service` import sites (35 sites, 14 files)

### Secondary (MEDIUM confidence)
- PITFALLS.md research (Pitfall 2: session lifecycle, Pitfall 4: RRC background worker)
- FEATURES.md research (Firestore collection to PostgreSQL mapping)
- CONTEXT.md decisions (pool settings, JSONB for raw_data, session lifecycle pattern)

## Metadata

**Confidence breakdown:**
- Function gap analysis: HIGH - direct line-by-line comparison of both files
- Import audit: HIGH - grep search of entire backend
- Architecture patterns: HIGH - existing code already establishes the patterns
- Pitfalls: HIGH - based on direct code analysis of call sites and return types

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable -- infrastructure migration, no external API changes)
