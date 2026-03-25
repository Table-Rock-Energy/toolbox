# Domain Pitfalls

**Domain:** On-prem migration of Firebase Auth, Firestore, GCS, and Gemini in an existing FastAPI+React application
**Researched:** 2026-03-25
**Confidence:** HIGH (based on direct codebase analysis + known patterns)

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or extended downtime.

### Pitfall 1: Firestore Nested Documents and Arrays Flattened Incorrectly to SQL

**What goes wrong:** Firestore stores revenue statement `rows` as a nested array inside the statement document (see `save_revenue_statement` in `firestore_service.py` lines 376-432). The migration script flattens these into a separate `revenue_rows` table but loses the ordering, or silently drops rows that have `None` values in fields that become NOT NULL columns. The RRC `raw_data` field (JSONB in the existing SQLAlchemy model) contains arbitrary dict structures that vary between oil and gas records -- a naive migration that tries to normalize these breaks lookups.

**Why it happens:** Firestore is schemaless. The same collection can have documents with different field sets. The existing `firestore_service.py` stores `rows` as a list-of-dicts inside the `revenue_statements` document. The SQLAlchemy `RevenueStatement` model stores rows as a separate `RevenueRow` table with a foreign key. The migration must decompose nested data correctly.

**Consequences:** Revenue data appears incomplete after migration. Users export CSVs with missing rows. The revenue tool reports fewer rows than previously shown. RRC lookups return `None` for records that existed in Firestore.

**Prevention:**
- Write the migration script to explicitly handle the `rows` array: iterate each statement document, create the parent `RevenueStatement` row first (to get the FK), then insert each row element as a `RevenueRow`.
- For RRC data, keep `raw_data` as JSONB (already in the model) -- do NOT try to normalize it into columns.
- Add a count-verification step: after migration, compare document counts per collection vs row counts per table. Log mismatches.
- The revenue statement uses a deterministic SHA256 ID (`statement_id = hashlib.sha256(composite.encode()).hexdigest()[:20]`). The SQLAlchemy model uses auto-increment integer IDs. Either change the PG model to use string IDs or maintain a mapping during migration.

**Detection:** Post-migration smoke test: for each tool, load the 3 most recent jobs and compare entry counts against Firestore.

**Phase:** DB migration phase. Must be addressed in the Firestore-to-PostgreSQL migration script (DB-04).

---

### Pitfall 2: Async SQLAlchemy Session Lifecycle Leaks and Deadlocks

**What goes wrong:** The current Firestore service uses a single global `AsyncClient` (`_db`) that is thread-safe and connection-pooled by the Google SDK. Replacing it with SQLAlchemy async sessions requires explicit session lifecycle management. If sessions aren't properly scoped (opened per-request, closed after), you get connection pool exhaustion under load, or worse, uncommitted transactions that block other queries.

**Why it happens:** The codebase has 30+ call sites that do `from app.services.firestore_service import ...` with lazy imports inside functions. Each currently gets the global client. If the PostgreSQL replacement follows the same pattern with `async_sessionmaker`, developers naturally write `session = get_session()` without `async with` and forget to commit/close. The RRC background worker (`rrc_background.py`) is especially dangerous -- it runs in a separate thread and uses `asyncio.run()` to call async functions, which creates a NEW event loop and a new session that shares the same connection pool.

**Consequences:** After a few RRC sync operations or busy upload periods, the app hangs. All API requests block waiting for a connection from the exhausted pool. Only a restart fixes it.

**Prevention:**
- Use FastAPI's `Depends()` with an async generator that yields a session and guarantees cleanup:
  ```python
  async def get_db() -> AsyncGenerator[AsyncSession, None]:
      async with async_session_factory() as session:
          try:
              yield session
              await session.commit()
          except Exception:
              await session.rollback()
              raise
  ```
- For the RRC background worker: create a SEPARATE sync `Session` factory (like the existing `_get_sync_firestore_client()` pattern). Do NOT share the async pool.
- Set `pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800` explicitly on the engine. The default `pool_size=5` with no overflow will deadlock under concurrent batch operations.
- Add `pool_pre_ping=True` to handle dropped connections (critical for Docker where PG might restart).

**Detection:** Monitor connection pool stats at `/api/health`. Add `engine.pool.status()` to the health check.

**Phase:** DB migration phase (DB-01, DB-05). The session management pattern must be established before any service is ported.

---

### Pitfall 3: JWT Token Shape Differs from Firebase Token -- Frontend Breaks Silently

**What goes wrong:** The frontend `AuthContext.tsx` currently uses Firebase's `User` object which has properties like `user.email`, `user.displayName`, `user.photoURL`, `user.getIdToken()`, `user.uid`. The new JWT auth returns a plain object from `/api/auth/me` with different property names. Components that access `user.displayName` or `user.photoURL` get `undefined` instead of `null`, causing blank names in the UI rather than a visible error. The `getIdToken()` method disappears entirely since JWT tokens are stored in memory/localStorage.

**Why it happens:** Firebase's `User` type is a rich object with methods. A local JWT auth returns a plain data object. TypeScript interfaces may be updated for `AuthContextType` but individual components that destructure `user` directly from the Firebase `User` type will silently fail because the property names change (e.g., `displayName` vs `display_name`, `photoURL` vs `photo_url`).

**Consequences:** The UI shows blank user names, missing avatars, and the Settings page looks broken. The `AdminSettings.tsx` and `Settings.tsx` pages reference Firebase-specific properties. The 401 token refresh handler (`api.setUnauthorizedHandler`) currently calls `auth.currentUser.getIdToken(true)` which no longer exists.

**Prevention:**
- Define a `LocalUser` interface that maps to the JWT payload/me response. Update `AuthContextType` to use `LocalUser` instead of Firebase's `User`.
- The new auth context should store the JWT token in state and provide `getToken(): string | null` (synchronous, not async like `getIdToken()`).
- The 401 handler should attempt a token refresh via `/api/auth/refresh` endpoint, not Firebase.
- Search for all files importing from `firebase/auth` or `../lib/firebase` (currently 4 files: `AuthContext.tsx`, `AdminSettings.tsx`, `Settings.tsx`, `firebase.ts`). All must be updated.
- Remove the `firebase.ts` lib file LAST, after all imports are removed, to get clean TypeScript errors.

**Detection:** Run `npx tsc --noEmit` after the auth migration. Any reference to removed Firebase types will error.

**Phase:** Auth phase (AUTH-05, AUTH-06). Frontend auth context must be rewritten before Firebase packages are removed.

---

### Pitfall 4: RRC Background Worker Cannot Use Async SQLAlchemy Sessions

**What goes wrong:** The `rrc_background.py` spawns a daemon thread (`threading.Thread`) and uses `asyncio.run()` to call async Firestore functions from within the thread. If the PostgreSQL replacement uses only async sessions tied to the main event loop, `asyncio.run()` creates a new event loop in the thread but the session factory's connection pool was created on the main loop. This causes `RuntimeError: Event loop is closed` or `attached to a different loop` errors.

**Why it happens:** The existing code already handles this correctly for Firestore by using a separate synchronous `firestore.Client`. The same pattern MUST be replicated for PostgreSQL: the background worker needs its own synchronous `Session` (not `AsyncSession`).

**Consequences:** RRC bulk download/sync silently fails. The job shows "downloading_oil" forever because the sync step crashes. Users see a stuck progress indicator.

**Prevention:**
- Create a `get_sync_session()` factory using `create_engine` (not `create_async_engine`) with `sessionmaker` (not `async_sessionmaker`). Use this exclusively in `rrc_background.py`.
- The sync engine should use the same `DATABASE_URL` but with `postgresql://` scheme (not `postgresql+asyncpg://`). Strip the `+asyncpg` part: `sync_url = settings.database_url.replace("+asyncpg", "")`.
- Keep the existing thread-based architecture. Do NOT try to make it fully async -- the RRC download uses `requests` (synchronous HTTP) with a custom SSL adapter that cannot be easily converted to `httpx`.

**Detection:** Test the full RRC download flow end-to-end after migration. Check the job reaches "complete" status.

**Phase:** DB migration phase (DB-05). Must be addressed when porting `rrc_background.py` from Firestore to PostgreSQL.

---

### Pitfall 5: LM Studio Response Format Differences Break JSON Parsing

**What goes wrong:** The Gemini provider uses `response_mime_type="application/json"` and `response_json_schema=RESPONSE_SCHEMA` to guarantee structured JSON output. LM Studio's OpenAI-compatible API does not support `response_format` with a JSON schema for most models, or supports it inconsistently. The model returns markdown-wrapped JSON (````json\n{...}\n````), or adds conversational text before/after the JSON, or returns a slightly different schema structure.

**Why it happens:** Gemini's structured output is enforced at the API level (constrained decoding). OpenAI's `response_format: { type: "json_object" }` only hints -- it doesn't enforce a schema. LM Studio passes this through to the underlying model which may or may not respect it. Smaller local models (7B-13B) are especially unreliable with complex JSON schemas.

**Consequences:** Every AI cleanup/validation call fails with `json.JSONDecodeError`. The enrichment pipeline reports 0 suggestions. Users think AI is broken.

**Prevention:**
- In the OpenAI-compatible provider, wrap JSON parsing with a fallback:
  1. Try `json.loads(response.choices[0].message.content)`
  2. If that fails, try stripping markdown code fences: `re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)`
  3. If that fails, try extracting the first `{...}` block with regex
  4. If all fail, return empty suggestions list (graceful degradation, not a crash)
- Set `temperature=0.1` (already done for Gemini, replicate for OpenAI provider).
- Include "Return ONLY valid JSON with no additional text" in the system prompt for the OpenAI provider.
- Test with the specific LM Studio model before going live. Different models have wildly different JSON compliance.

**Detection:** Add a `json_parse_failures` counter to the AI status endpoint. If it exceeds a threshold, surface a warning in the admin panel.

**Phase:** AI migration phase (AI-01, AI-02). Must be handled when implementing the OpenAI-compatible provider.

---

### Pitfall 6: Allowlist and Config Data Lost During Migration

**What goes wrong:** The auth allowlist is stored in TWO places: Firestore (`app_config/allowed_users`) and a local JSON file (`data/allowed_users.json`). The Firestore version is the source of truth, with the local file as a cache. User preferences (`user_preferences` collection), GHL connections (`ghl_connections` with encrypted tokens), and app config (`app_config` collection) are Firestore-only with no local fallback. If the migration script only handles the "obvious" collections (jobs, entries, RRC data), these config collections get silently lost.

**Why it happens:** The migration checklist focuses on the high-volume data collections. Config/settings collections are small and easy to overlook. The GHL connections are especially tricky because they contain Fernet-encrypted API tokens that must be migrated as-is (they're encrypted with `ENCRYPTION_KEY` which stays the same).

**Consequences:** After migration: all users except the hardcoded default (`james@tablerocktx.com`) lose access. GHL connections disappear. User preferences (batch size, theme, etc.) reset. Admin has to re-add every user manually.

**Prevention:**
- The migration script must explicitly handle ALL Firestore collections. Full list from `firestore_service.py`:
  - `users` -- map to `users` table
  - `jobs` -- map to `jobs` table
  - `extract_entries`, `title_entries`, `proration_rows`, `revenue_statements` -- map to respective tables
  - `rrc_oil_proration`, `rrc_gas_proration` -- map to RRC tables
  - `rrc_data_syncs` -- map to `rrc_data_syncs` table
  - `rrc_county_status` -- needs new table (NOT in current SQLAlchemy models)
  - `rrc_sync_jobs` -- needs new table (NOT in current SQLAlchemy models)
  - `rrc_metadata` -- needs new table or merge into config
  - `audit_logs` -- map to `audit_logs` table
  - `app_config` -- needs new table (key-value config store)
  - `user_preferences` -- needs new table
  - `ghl_connections` -- needs new table (with encrypted token column)
  - `entities` (from ETL entity_registry) -- needs new table
- Create SQLAlchemy models for the 5 missing tables BEFORE running migration.
- GHL encrypted tokens: migrate the `encrypted_token` field as-is (it's a string). The `ENCRYPTION_KEY` env var stays the same so decryption still works.

**Detection:** After migration, verify: `SELECT COUNT(*) FROM app_config`, `SELECT COUNT(*) FROM ghl_connections`, `SELECT COUNT(*) FROM user_preferences`. All should be > 0 if Firestore had data.

**Phase:** DB migration phase (DB-02 for models, DB-04 for migration script). The missing models must be created first.

## Moderate Pitfalls

### Pitfall 7: JWT Secret Key Management in Docker

**What goes wrong:** The JWT secret key is generated once and must persist across container restarts. If it's randomly generated at startup (a common pattern in tutorials), every restart invalidates all active tokens, forcing all users to re-login. If it's hardcoded in the Dockerfile or committed to git, it's a security vulnerability.

**Prevention:**
- Use `JWT_SECRET_KEY` as an env var, loaded via Pydantic Settings (already the pattern for `ENCRYPTION_KEY`).
- Generate it once during initial setup: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`.
- Store in `.env` file on the host, mounted into Docker via `env_file` in docker-compose.
- Add `JWT_SECRET_KEY` to the production environment variables alongside `ENCRYPTION_KEY`.
- Add a startup check: if `JWT_SECRET_KEY` is missing in production, fail fast (same pattern as the existing `ENCRYPTION_KEY` check in `main.py`).

**Phase:** Auth phase (AUTH-01, AUTH-02).

---

### Pitfall 8: Bcrypt Hashing Rounds Too Low or Too High

**What goes wrong:** Default bcrypt rounds (12) take ~250ms per hash. This is fine for login (one hash per request) but becomes a problem if the admin user creation CLI script needs to hash passwords for batch user creation, or if the test suite creates users in fixtures. Conversely, using low rounds (4) for speed makes passwords trivially crackable.

**Prevention:**
- Use 12 rounds for production (the bcrypt default). This is the industry standard for 2024-2026 hardware.
- For tests, override with a lower round count (4) via a test config fixture. Do NOT lower the production default.
- The admin CLI script creates one user at a time, so 250ms is acceptable.
- Store the hashed password, not the bcrypt rounds, in the database. Bcrypt embeds the round count in the hash string itself.

**Phase:** Auth phase (AUTH-01, AUTH-04).

---

### Pitfall 9: Firestore Timestamps vs PostgreSQL Timestamps

**What goes wrong:** Firestore stores `datetime.utcnow()` as a Firestore Timestamp with microsecond precision and implicit UTC. The migration script reads these as Python `datetime` objects, but some are timezone-naive (`datetime.utcnow()` returns naive) and some are timezone-aware (Firestore returns aware datetimes). PostgreSQL `DateTime(timezone=True)` columns expect timezone-aware values. Inserting naive datetimes silently assumes the server's local timezone, causing timestamps to shift by hours.

**Prevention:**
- In the migration script, normalize ALL datetimes to UTC-aware before inserting: `dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt`.
- In the new codebase, replace ALL `datetime.utcnow()` calls with `datetime.now(timezone.utc)`. The `utcnow()` function is deprecated in Python 3.12+ and returns naive datetimes.
- The SQLAlchemy models already use `DateTime(timezone=True)` -- this is correct. Just ensure the values going in are aware.

**Phase:** DB migration phase (DB-04 for migration script, DB-05 for updating service code).

---

### Pitfall 10: Storage Path Hardcoding for Docker Volumes

**What goes wrong:** The current `StorageService` uses `settings.data_dir` which defaults to `Path(__file__).parent.parent.parent / "data"` -- a path relative to the Python source. In Docker, this resolves to somewhere inside the container's read-only filesystem layer. Uploaded files, RRC data CSVs, and profile images written here disappear on container restart.

**Prevention:**
- Change `data_dir` default to `/app/data` for Docker (already the case in the Dockerfile, but verify).
- In `docker-compose.yml`, mount a named volume: `volumes: - toolbox_data:/app/data`.
- Verify the mounted directory is writable by the container user (common Docker permission issue).
- The `RRCDataStorage`, `UploadStorage`, and `ProfileStorage` all derive paths from `settings.data_dir` -- no additional changes needed if the base path is correct.
- Test: upload a file, restart the container, verify the file persists.

**Phase:** Storage phase (STOR-01). Address when removing GCS dependency.

---

### Pitfall 11: LM Studio Timeout and Connection Differences

**What goes wrong:** The Gemini provider uses Google's SDK which has built-in retry and long timeouts. The OpenAI Python client defaults to 10-minute timeouts, but LM Studio running on local hardware may be slow for large batches (25 entries with detailed prompts). A 7B model on CPU can take 60-90 seconds per batch. The client times out, the pipeline marks the batch as failed, and retry logic re-sends it (now the model is processing both the original and retry simultaneously, consuming memory).

**Prevention:**
- Set explicit timeouts on the OpenAI client: `openai.AsyncOpenAI(base_url=..., timeout=httpx.Timeout(120.0, connect=10.0))`.
- Reduce batch size for local models: make `BATCH_SIZE` configurable via admin settings (already stored in Firestore/config, extend to the new provider).
- Add a model warm-up call at startup (single short prompt) to detect if LM Studio is running and responsive.
- The disconnect detection logic (`disconnect_check` callback) already exists in the pipeline -- ensure the OpenAI provider passes it through.

**Phase:** AI migration phase (AI-01, AI-02).

---

### Pitfall 12: Test Suite Mocks Assume Firebase/Firestore Imports

**What goes wrong:** The existing test suite (`conftest.py`) overrides `require_auth` via FastAPI dependency injection, which will work with JWT auth too. But tests like `test_auth_enforcement.py` and `test_fetch_missing.py` mock `firestore_service` directly. After migration, these import paths change. Tests that mock `from app.services.firestore_service import ...` will fail because the module no longer exists (or has been replaced with a PostgreSQL service).

**Prevention:**
- During migration, update test mocks incrementally. The auth tests that override `require_auth` via `app.dependency_overrides` will continue to work -- this is the correct pattern for both Firebase and JWT auth.
- For Firestore mocks in `test_fetch_missing.py`: update to mock the new database service instead. Use an in-memory SQLite database for tests if possible (caveat: SQLite doesn't support JSONB, use `JSON` type alias).
- Better: use `pytest-postgresql` or a test database fixture that creates real tables in a throwaway PG database. This catches schema issues that SQLite would miss.
- Keep the existing conftest pattern of dependency overrides -- it's clean and works with both auth systems.

**Detection:** Run `make test` after each migration phase. Tests should pass continuously, not just at the end.

**Phase:** Crosses all phases. Each migration phase should update affected tests before merging.

## Minor Pitfalls

### Pitfall 13: CORS Origins Must Include On-Prem URL

**What goes wrong:** The current CORS config returns `["https://tools.tablerocktx.com"]` in production and `["http://localhost:5173"]` in development. On-prem deployment may use a different URL (e.g., `http://192.168.1.x:5173` or `https://tools.internal.tablerocktx.com`). If CORS origins aren't updated, the browser blocks all API requests.

**Prevention:** The `CORS_ALLOWED_ORIGINS` env var already supports comma-separated origins. Document the on-prem URL and set it in the Docker env file.

**Phase:** Deployment/infrastructure setup.

---

### Pitfall 14: Firebase npm Packages Left as Dead Dependencies

**What goes wrong:** After removing all Firebase imports from the frontend, the packages (`firebase`, `@firebase/auth`) remain in `package.json`. They add ~500KB to the production bundle and trigger npm audit warnings for known vulnerabilities in transitive dependencies.

**Prevention:** After AUTH-06 (remove Firebase imports), run `npm uninstall firebase` and verify the build still works. Check `dist/` bundle size before and after.

**Phase:** Auth phase (AUTH-06), after all frontend Firebase references are removed.

---

### Pitfall 15: OpenAI Client Token Counting Differs from Gemini

**What goes wrong:** The Gemini service tracks token usage via `response.usage_metadata.prompt_token_count` and `candidates_token_count` for monthly budget enforcement. The OpenAI API uses `response.usage.prompt_tokens` and `response.usage.completion_tokens`. LM Studio may or may not populate the `usage` field depending on the model backend (llama.cpp populates it, some others don't).

**Prevention:** In the OpenAI provider, handle missing usage gracefully: `usage = response.usage; prompt_tokens = usage.prompt_tokens if usage else 0`. Budget tracking becomes best-effort for local models -- acceptable since LM Studio is free.

**Phase:** AI migration phase (AI-01).

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Auth (AUTH-01 to AUTH-04) | JWT secret not persisted across restarts | Env var, fail-fast check at startup |
| Auth (AUTH-05) | Frontend `User` type mismatch | New `LocalUser` interface, TypeScript compilation catches it |
| Auth (AUTH-06) | Dead Firebase packages in bundle | `npm uninstall firebase` after all imports removed |
| DB (DB-02) | Missing SQLAlchemy models for 5 Firestore collections | Enumerate ALL collections before writing schema |
| DB (DB-03) | Schema creation misses indexes | Use `create_all()` which creates indexes from model definitions |
| DB (DB-04) | Nested Firestore docs flattened wrong | Explicit per-collection handlers with count verification |
| DB (DB-04) | Naive datetimes shift timezone | Normalize to UTC-aware before insert |
| DB (DB-05) | Session leaks in background worker | Separate sync Session factory for threads |
| DB (DB-05) | Connection pool exhaustion | Explicit pool settings, health check monitoring |
| AI (AI-01) | JSON parsing failures from local models | Multi-layer fallback parser, graceful degradation |
| AI (AI-01) | Slow local model timeouts | Configurable timeout, smaller batch sizes |
| AI (AI-02) | Token counting differs between providers | Graceful handling of missing usage data |
| Storage (STOR-01) | Docker volume not mounted, data lost on restart | Named volume in docker-compose, startup write test |
| Cross-cutting | Tests break incrementally during migration | Update tests per-phase, not at the end |

## Integration Pitfalls (Cross-Area)

These pitfalls emerge from the interaction between multiple migration areas.

### Integration 1: Auth + DB -- User ID Format Changes

**What goes wrong:** Firebase UIDs are strings like `"abc123def456"`. The new JWT auth uses auto-increment integer IDs or UUIDs for the users table. If the `jobs` table still has a `user_id` foreign key expecting the old Firebase UID format, existing jobs become orphaned (no matching user). New jobs use the new ID format but old jobs reference a non-existent user.

**Prevention:** Use the user's email as the stable identifier (already the case for allowlist checks). The `user_id` in jobs should be the email, not a Firebase UID. Or: migrate user IDs to UUIDs in the users table and update all FK references in the migration script.

**Phase:** Must be coordinated between AUTH-01 (user table) and DB-04 (migration script).

### Integration 2: Auth + AI -- Pipeline Disconnect Detection After Auth Change

**What goes wrong:** The pipeline's disconnect detection uses `request.is_disconnected()` which works independently of auth. But if the JWT token expires mid-pipeline (a 5-minute cleanup operation), the subsequent batch results POST fails with 401. The existing Firebase auth context had a token refresh handler; the new JWT auth needs an equivalent.

**Prevention:** Issue JWT tokens with a sufficiently long expiry (24 hours for this internal tool). Add a `/api/auth/refresh` endpoint. The frontend's 401 handler should call refresh before retrying.

**Phase:** AUTH-02 (backend endpoints) must include a refresh endpoint. AUTH-05 (frontend context) must wire up the refresh handler.

### Integration 3: DB + Storage -- Job Records Reference GCS Paths

**What goes wrong:** Existing job records in Firestore may contain `storage_path` or file references as `gs://bucket-name/path`. After migration to local storage, these paths are invalid. The app tries to load files from GCS paths that don't exist locally.

**Prevention:** The current codebase doesn't store GCS paths in job documents (uploads are processed in-memory and results are returned directly). But `UploadStorage.save_upload()` returns a GCS path string. If any service stores this path in Firestore, the migration script must rewrite `gs://` paths to local paths. Audit all `upload_storage.save_upload()` call sites.

**Phase:** DB migration (DB-04) and storage (STOR-01) should be coordinated.

## Sources

- Direct codebase analysis of `firestore_service.py` (1003 lines, 14 collections)
- Direct analysis of `auth.py` (Firebase token verification, allowlist management)
- Direct analysis of `AuthContext.tsx` (Firebase User type dependencies)
- Direct analysis of `rrc_background.py` (threading + asyncio.run() pattern)
- Direct analysis of `gemini_service.py` (structured output, rate limiting, token tracking)
- Direct analysis of `storage_service.py` (GCS/local fallback pattern)
- Direct analysis of `db_models.py` (existing SQLAlchemy models -- 5 collections missing)
- Direct analysis of `connection_service.py` (encrypted GHL token storage in Firestore)
- SQLAlchemy async documentation: session lifecycle and connection pooling
- Python 3.12 deprecation of `datetime.utcnow()` (PEP 705)
