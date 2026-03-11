# Codebase Concerns

**Analysis Date:** 2026-03-10

## Tech Debt

**Dead PostgreSQL Code Path:**
- Issue: A full SQLAlchemy/PostgreSQL data layer exists (`db_service.py`, `db_models.py`, `database.py`) but is disabled by default (`database_enabled: bool = False`). Firestore is the actual database. This unused code adds 1,268+ lines of dead weight.
- Files: `backend/app/services/db_service.py` (763 lines), `backend/app/models/db_models.py` (505 lines), `backend/app/core/database.py`
- Impact: Confuses developers about which persistence layer to use. SQLAlchemy imports and models must be kept in sync with Firestore schema but serve no purpose. Increases dependency footprint.
- Fix approach: Remove `db_service.py`, `db_models.py`, `database.py`, and the `database_enabled`/`database_url` config. Remove `sqlalchemy`, `asyncpg`, `psycopg2` from `requirements.txt`. Remove conditional DB init from `backend/app/main.py` lines 129-136.

**Deprecated FastAPI Lifecycle Events:**
- Issue: `@app.on_event("startup")` and `@app.on_event("shutdown")` are deprecated in recent FastAPI. Should use the `lifespan` context manager pattern.
- Files: `backend/app/main.py` (lines 103, 143)
- Impact: Will produce deprecation warnings and eventually break on a FastAPI upgrade.
- Fix approach: Replace with `@asynccontextmanager async def lifespan(app)` and pass to `FastAPI(lifespan=lifespan)`.

**`datetime.utcnow()` Usage (Deprecated in Python 3.12+):**
- Issue: At least 20+ occurrences of `datetime.utcnow()` which is deprecated. Should use `datetime.now(timezone.utc)`.
- Files: `backend/app/services/firestore_service.py`, `backend/app/services/db_service.py`, `backend/app/services/etl/entity_registry.py`, `backend/app/services/proration/rrc_county_download_service.py`
- Impact: Deprecation warnings; `utcnow()` returns naive datetimes (no tzinfo), which can cause subtle timezone bugs.
- Fix approach: Global find-and-replace `datetime.utcnow()` with `datetime.now(timezone.utc)`. Ensure `from datetime import timezone` is imported.

**Monolithic Frontend Page Components:**
- Issue: Tool pages are extremely large single-file components with mixed concerns (state, UI, API calls, data transformation).
- Files: `frontend/src/pages/Proration.tsx` (1,636 lines), `frontend/src/pages/Title.tsx` (1,468 lines), `frontend/src/pages/AdminSettings.tsx` (1,376 lines), `frontend/src/pages/Revenue.tsx` (1,373 lines), `frontend/src/pages/Extract.tsx` (1,249 lines)
- Impact: Hard to maintain, test, or reason about. Adding features to any tool page means editing a 1,000+ line file.
- Fix approach: Extract custom hooks (e.g., `useProration`, `useRevenue`) for state/API logic. Break UI into sub-components per tool section.

**Broad Exception Catching:**
- Issue: 189 occurrences of `except Exception` across 45 Python files. Many catch-all handlers silently swallow errors with just a log warning.
- Files: Throughout `backend/app/` -- particularly `backend/app/core/auth.py`, `backend/app/services/storage_service.py`, `backend/app/main.py`
- Impact: Masks bugs. Errors in authentication, storage, and data processing are silently ignored, making debugging production issues difficult.
- Fix approach: Narrow exception types where possible. At minimum, ensure all catch-all blocks log at ERROR level with stack traces (`logger.exception()`).

## Security Considerations

**Core Tool Endpoints Have No Authentication:**
- Risk: The primary tool endpoints (Extract, Title, Proration, Revenue, GHL Prep) have zero auth middleware. Any unauthenticated request to `/api/extract/upload`, `/api/revenue/upload`, etc. is processed.
- Files: `backend/app/api/extract.py`, `backend/app/api/title.py`, `backend/app/api/proration.py`, `backend/app/api/revenue.py`, `backend/app/api/ghl_prep.py`
- Current mitigation: Cloud Run is publicly accessible (`--allow-unauthenticated` in deploy.yml). Frontend sends auth tokens but backend does not verify them on these routes. Only GHL, admin, enrichment, and ETL routes use `Depends(require_auth)` or `Depends(require_admin)`.
- Recommendations: Add `Depends(require_auth)` to all upload and export endpoints. The `get_current_user` dependency already exists and returns `None` for unauthenticated requests -- switch to `require_auth` which raises 401.

**User Check Endpoint Has No Authentication:**
- Risk: The `/api/admin/users/{email}/check` endpoint is unauthenticated. Anyone can enumerate which emails are in the allowlist.
- Files: `backend/app/api/admin.py` (line 311)
- Current mitigation: None. The endpoint returns allowlist status, role, and tool access for any queried email.
- Recommendations: This endpoint is called by `AuthContext.tsx` before auth is fully established (to check if a signed-in user is allowed). Consider moving this check to the token verification flow in `get_current_user` instead.

**CORS Allows All Origins in Production:**
- Risk: `allow_origins=["*"]` is set with no environment-based restriction. Combined with `allow_credentials=True`, this could enable cross-site request forgery from any domain.
- Files: `backend/app/main.py` (line 51)
- Current mitigation: None. The comment says "In production, specify allowed origins" but this was never done.
- Recommendations: Set `allow_origins=["https://tools.tablerocktx.com"]` in production. Use an env var to allow `*` only in development.

**RRC SSL Verification Disabled:**
- Risk: SSL certificate verification is completely disabled for RRC downloads (`verify=False`, `CERT_NONE`). Suppresses all SSL warnings globally via `urllib3.disable_warnings()`.
- Files: `backend/app/services/proration/rrc_data_service.py` (lines 18, 43, 75)
- Current mitigation: This is a known requirement due to RRC's outdated SSL. The custom `RRCSSLAdapter` attempts to use compatible ciphers.
- Recommendations: Scope the `disable_warnings` call to only the RRC session context rather than disabling globally. Pin the RRC certificate if possible.

**Encryption Falls Back to Plaintext:**
- Risk: When `ENCRYPTION_KEY` is not configured, API keys and credentials stored in Firestore are saved in plaintext with only a log warning.
- Files: `backend/app/services/shared/encryption.py` (lines 44-46)
- Current mitigation: Warning logged. The encryption module gracefully handles pre-encryption values during migration.
- Recommendations: Require `ENCRYPTION_KEY` in production. Fail loudly rather than silently storing secrets in plaintext.

**Frontend Allows Access When Backend Is Down:**
- Risk: If the backend is unreachable during auth check, `AuthContext.tsx` returns `true` for authorization (line 55: `return true` in the catch block).
- Files: `frontend/src/contexts/AuthContext.tsx` (line 55)
- Current mitigation: None. This was added for dev convenience but runs in production.
- Recommendations: Return `false` in the catch block for production. Use an environment check.

## Performance Bottlenecks

**DataFrame `iterrows()` on Large RRC Datasets:**
- Problem: RRC oil/gas data (potentially 100k+ rows) is processed using `df.iterrows()`, the slowest way to iterate a pandas DataFrame.
- Files: `backend/app/services/proration/rrc_data_service.py` (lines 296, 325, 601, 663), `backend/app/services/proration/csv_processor.py` (line 125), `backend/app/services/title/excel_processor.py` (lines 238, 283, 408)
- Cause: `iterrows()` creates a new Series for each row, has Python-level overhead per row.
- Improvement path: Use `df.itertuples()` (5-10x faster) or vectorized pandas operations where possible. For the lookup table construction in `_load_lookup()`, use `df.groupby()` with aggregation.

**In-Memory RRC Data Caching Without Size Limits:**
- Problem: The entire RRC oil and gas DataFrames plus a combined lookup dict are cached in memory on the global `rrc_data_service` singleton with no eviction policy.
- Files: `backend/app/services/proration/rrc_data_service.py` (lines 92-98)
- Cause: Class-level caches (`_oil_df`, `_gas_df`, `_combined_lookup`) persist for the lifetime of the process.
- Improvement path: With Cloud Run scaling to 0, this is partially mitigated (cache rebuilds on cold start). However, during active use, two large DataFrames plus a dict of all records can consume significant memory on a 1Gi instance. Consider using a TTL cache or loading only needed districts.

**Synchronous RRC Downloads Block the Event Loop:**
- Problem: `download_oil_data()` and `download_gas_data()` use synchronous `requests.Session` with 900-second timeouts, but are called from async route handlers.
- Files: `backend/app/services/proration/rrc_data_service.py` (lines 100-150, 152-202)
- Cause: Using `requests` (sync) instead of `httpx` (async). The async handler likely calls these in a thread via background task, but the `sync_to_database` method uses `await` suggesting mixed sync/async.
- Improvement path: Use `httpx.AsyncClient` for RRC downloads, or ensure all sync calls are wrapped in `asyncio.to_thread()`.

## Fragile Areas

**RRC Data Pipeline:**
- Files: `backend/app/services/proration/rrc_data_service.py`, `backend/app/services/proration/rrc_county_download_service.py`, `backend/app/services/rrc_background.py`
- Why fragile: Depends on scraping a Texas state government website that uses outdated SSL, session-based CSV downloads, and specific HTML form parameters. Any change to the RRC website breaks the entire proration tool.
- Safe modification: Test against the live RRC site before deploying changes. The `create_rrc_session()` function contains all SSL workarounds -- modify there first.
- Test coverage: Zero automated tests.

**Auth System with Dual Storage:**
- Files: `backend/app/core/auth.py`
- Why fragile: Allowlist is stored in both a local JSON file (`data/allowed_users.json`) and Firestore. On startup, Firestore is the source of truth, but writes go to both. A race condition or Firestore failure can cause the local file and Firestore to diverge. The fire-and-forget `loop.create_task()` pattern (line 71) means Firestore writes can silently fail.
- Safe modification: Always test with Firestore available. Check that `_persist_allowlist_to_firestore` logs confirm successful writes.
- Test coverage: Zero automated tests.

**Revenue PDF Parsers:**
- Files: `backend/app/services/revenue/enverus_parser.py` (707 lines), `backend/app/services/revenue/energylink_parser.py`, `backend/app/services/revenue/energytransfer_parser.py`
- Why fragile: PDF parsing relies on exact text layout, column positions, and formatting. A new PDF template version from any revenue source (EnergyLink, Energy Transfer, Enverus) will likely break parsing silently -- producing wrong data rather than errors.
- Safe modification: Always test with real PDFs from each revenue source. Keep sample PDFs in `test-data/revenue/`.
- Test coverage: Zero automated tests.

## Test Coverage Gaps

**No Test Suite Exists:**
- What's not tested: Everything. There are zero test files in the entire codebase despite `pytest` being listed as a dependency and `make test` being a documented command.
- Files: No `tests/` directory, no `test_*.py` files, no `conftest.py` anywhere.
- Risk: Any change to business logic (PDF parsing, RRC data processing, NRA calculations, revenue statement extraction) can introduce regressions undetected. The calculation-heavy proration service and parsing-heavy extract/revenue services are highest risk.
- Priority: **High** -- Start with unit tests for:
  1. `backend/app/services/proration/csv_processor.py` (NRA calculations)
  2. `backend/app/services/extract/parser.py` (party extraction)
  3. `backend/app/services/revenue/` parsers (revenue statement extraction)
  4. `backend/app/core/auth.py` (allowlist logic)

**No Frontend Tests:**
- What's not tested: All React components and pages.
- Files: `frontend/src/` -- no `*.test.tsx` or `*.spec.tsx` files.
- Risk: UI regressions, broken form submissions, export download failures.
- Priority: Medium -- Focus on critical user flows (file upload, data export).

## Dependencies at Risk

**No CI Lint/Type-Check Gate:**
- Risk: The deploy workflow (`deploy.yml`) does not run linting, type checking, or tests before deploying. Every push to `main` goes directly to production.
- Files: `.github/workflows/deploy.yml`
- Impact: Broken code can be deployed to production without any automated safety net.
- Migration plan: Add a `test` job that runs `make lint`, `npx tsc --noEmit`, and `make test` before the deploy step. Use `needs: test` on the deploy job.

**Uvicorn Single Worker in Production:**
- Risk: The Dockerfile CMD runs `uvicorn` with default settings (1 worker). Under concurrent load, a single worker with async handlers that call synchronous code (RRC downloads, pandas operations) will block.
- Files: `Dockerfile` (line 66)
- Impact: Long-running operations (RRC download with 900s timeout) block the entire server for all users.
- Migration plan: Use `gunicorn` with `uvicorn.workers.UvicornWorker` and multiple workers, or ensure all blocking calls use `asyncio.to_thread()`.

## Missing Critical Features

**No Request Rate Limiting:**
- Problem: No rate limiting on any API endpoint. An attacker or misbehaving client can flood the upload endpoints with large PDF files.
- Blocks: Production hardening.
- Files: `backend/app/main.py` -- no rate limiting middleware configured.
- Recommendation: Add `slowapi` or a simple middleware-based rate limiter, especially on upload endpoints.

**No Structured Logging / Request Tracing:**
- Problem: Logging uses basic `logging.basicConfig` with no request IDs, no structured JSON output, and no correlation between frontend actions and backend processing.
- Blocks: Debugging production issues across distributed Cloud Run instances.
- Files: `backend/app/main.py` (lines 35-38)
- Recommendation: Add request ID middleware, use JSON structured logging for production.

---

*Concerns audit: 2026-03-10*
