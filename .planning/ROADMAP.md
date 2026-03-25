# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- ✅ **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (shipped 2026-03-19)
- ✅ **v1.7 Batch Processing & Resilience** -- Phases 13-17 (shipped 2026-03-20)
- ✅ **v1.8 Preview System Overhaul** -- Phases 18-21 (shipped 2026-03-24)
- 🚧 **v2.0 Full On-Prem Migration** -- Phases 22-27 (in progress)

## Phases

<details>
<summary>v1.3 Security Hardening (Phases 1-3) -- SHIPPED 2026-03-11</summary>

- [x] Phase 1: Auth Enforcement & CORS Lockdown (2/2 plans) -- completed 2026-03-11
- [x] Phase 2: Encryption Hardening (2/2 plans) -- completed 2026-03-11
- [x] Phase 3: Backend Test Suite (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.3-ROADMAP.md` for full details

</details>

<details>
<summary>v1.4 ECF Extraction (Phases 1-4) -- SHIPPED 2026-03-12</summary>

- [x] Phase 1: ECF PDF Parsing (2/2 plans) -- completed 2026-03-12
- [x] Phase 2: Convey 640 Processing (1/1 plan) -- completed 2026-03-12
- [x] Phase 3: Merge and Export (2/2 plans) -- completed 2026-03-12
- [x] Phase 4: Frontend Integration (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.4-ROADMAP.md` for full details

</details>

<details>
<summary>v1.5 Enrichment Pipeline & Bug Fixes (Phases 5-9) -- SHIPPED 2026-03-17</summary>

- [x] Phase 5: ECF Upload Flow Fix (2/2 plans) -- completed 2026-03-14
- [x] Phase 6: RRC & GHL Fixes (2/2 plans) -- completed 2026-03-14
- [x] Phase 7: Enrichment UI & Preview State (3/3 plans) -- completed 2026-03-15
- [x] Phase 8: Enrichment Pipeline Features (3/3 plans) -- completed 2026-03-16
- [x] Phase 9: Tool-Specific AI Prompts (2/2 plans) -- completed 2026-03-17

See: `.planning/milestones/v1.5-ROADMAP.md` for full details

</details>

<details>
<summary>v1.6 Pipeline Fixes & Unified Enrichment (Phases 10-12) -- SHIPPED 2026-03-19</summary>

- [x] Phase 10: Auth Hardening & GHL Cleanup (3/3 plans) -- completed 2026-03-19
- [x] Phase 11: RRC Pipeline Fix (1/1 plan) -- completed 2026-03-18
- [x] Phase 12: Unified Enrichment Modal (2/2 plans) -- completed 2026-03-19

See: `.planning/milestones/v1.6-ROADMAP.md` for full details

</details>

<details>
<summary>v1.7 Batch Processing & Resilience (Phases 13-17) -- SHIPPED 2026-03-20</summary>

- [x] Phase 13: Operation Context & Batch Engine (2/2 plans) -- completed 2026-03-19
- [x] Phase 14: AI Cleanup Batching (2/2 plans) -- completed 2026-03-19
- [x] Phase 15: Operation Persistence UI (1/1 plan) -- completed 2026-03-20
- [x] Phase 16: Revenue Multi-PDF Streaming (2/2 plans) -- completed 2026-03-20
- [x] Phase 17: Proration Performance (2/2 plans) -- completed 2026-03-20

See: `.planning/milestones/v1.7-ROADMAP.md` for full details

</details>

<details>
<summary>v1.8 Preview System Overhaul (Phases 18-21) -- SHIPPED 2026-03-24</summary>

- [x] Phase 18: Key-Based Highlight Tracking -- completed 2026-03-24
- [x] Phase 19: Filter Correctness -- completed 2026-03-24
- [x] Phase 20: Preview UX Refinements -- completed 2026-03-24
- [x] Phase 21: Proration Enhancements -- completed 2026-03-24

See: `.planning/milestones/v1.8-ROADMAP.md` for full details

</details>

### v2.0 Full On-Prem Migration

- [x] **Phase 22: Database Models & Schema** - Extend SQLAlchemy models for all Firestore collections and initialize Alembic (completed 2026-03-25)
- [x] **Phase 23: Auth Backend** - JWT login/me endpoints, token verification middleware, admin seed script (completed 2026-03-25)
- [ ] **Phase 24: Auth Frontend & Firebase Removal** - Local auth context with JWT, remove all Firebase packages and imports
- [ ] **Phase 25: Database Service Port** - Replace every Firestore service function with PostgreSQL equivalent
- [ ] **Phase 26: AI Provider Swap** - LM Studio via OpenAI-compatible API, remove Gemini dependency
- [ ] **Phase 27: Storage & Dependency Cleanup** - Local filesystem default, GCS removal, migration script, final purge

## Phase Details

### Phase 22: Database Models & Schema
**Goal**: PostgreSQL schema covers all data currently stored in Firestore, with Alembic migration tooling
**Depends on**: Nothing (first phase of v2.0)
**Requirements**: DB-02, DB-03
**Success Criteria** (what must be TRUE):
  1. SQLAlchemy models exist for all Firestore collections -- AppConfig, UserPreference, RRCCountyStatus, GHLConnection added; User model has password_hash, role, scope, tools columns
  2. `alembic upgrade head` creates all tables in an empty PostgreSQL database with correct column types, indexes, and foreign keys
  3. Alembic initialized with async template and initial migration auto-generated from models
**Plans**: 2 plans
Plans:
- [x] 22-01-PLAN.md -- Extend db_models.py with 6 new models and User auth columns
- [x] 22-02-PLAN.md -- Initialize Alembic async template and generate initial migration

### Phase 23: Auth Backend
**Goal**: Users authenticate via email/password against PostgreSQL with JWT tokens verified on every protected request
**Depends on**: Phase 22 (users table with password_hash column)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. `POST /api/auth/login` with valid email/password returns a JWT access token and user profile
  2. `GET /api/auth/me` with valid Bearer token returns user profile (email, role, name)
  3. Protected endpoints return 401 without valid JWT -- existing require_auth/require_admin dependency chain works with JWT verification
  4. CLI seed script creates admin user (james@tablerocktx.com) in PostgreSQL with bcrypt-hashed password
  5. App fails fast at startup if JWT_SECRET_KEY is missing in production
**Plans**: 2 plans
Plans:
- [x] 23-01-PLAN.md -- Security module, JWT config, auth.py rewrite, SSE/admin fixes, startup check
- [x] 23-02-PLAN.md -- Auth API endpoints (login/me), seed script, tests

### Phase 24: Auth Frontend & Firebase Removal
**Goal**: Frontend authenticates via local JWT with zero Firebase code remaining in the codebase
**Depends on**: Phase 23 (backend auth endpoints exist)
**Requirements**: AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. User logs in on Login page with email/password -- no Google Sign-In button visible
  2. User stays logged in across page refreshes (JWT in localStorage)
  3. User is redirected to login on 401 with session-expired handling
  4. `firebase` npm package uninstalled, `firebase.ts` deleted, zero Firebase imports in frontend code
  5. `npx tsc --noEmit` passes cleanly after all Firebase removal
**Plans**: 2 plans
Plans:
- [ ] 24-01-PLAN.md -- AuthContext rewrite with LocalUser + JWT, backend change-password endpoint, Login Google removal
- [ ] 24-02-PLAN.md -- Settings.tsx Firebase removal, all consumer file updates, firebase.ts deletion, npm uninstall

### Phase 25: Database Service Port
**Goal**: Every data operation reads/writes PostgreSQL -- Firestore code completely removed from backend
**Depends on**: Phase 22 (models), Phase 23 (auth uses PG users table)
**Requirements**: DB-01, DB-05, DB-06
**Success Criteria** (what must be TRUE):
  1. All CRUD operations (jobs, entries, RRC data, config, preferences, GHL connections) use PostgreSQL
  2. RRC background worker uses sync SQLAlchemy session for thread-safe database access
  3. `firestore_service.py` deleted -- no imports of firestore_service anywhere in codebase
  4. `firebase-admin` Python package has zero remaining import sites in backend
  5. Existing test suite passes with PostgreSQL as sole database
**Plans**: TBD

### Phase 26: AI Provider Swap
**Goal**: AI operations use LM Studio via OpenAI-compatible API -- Gemini dependency fully removed
**Depends on**: Nothing (independent of auth/DB work)
**Requirements**: AI-01, AI-02, AI-03
**Success Criteria** (what must be TRUE):
  1. OpenAI-compatible provider implements LLMProvider protocol and calls configurable base URL
  2. Provider factory routes based on AI_PROVIDER setting (lmstudio or none)
  3. JSON response parsing handles markdown-fenced and preamble-wrapped model output with graceful fallback
  4. `google-genai` dependency removed, `gemini_service.py` and GeminiProvider deleted
  5. Enrichment pipeline works end-to-end with LM Studio or gracefully skips AI when AI_PROVIDER=none

### Phase 27: Storage & Dependency Cleanup
**Goal**: App runs fully on-prem with zero Google cloud dependencies in code or requirements.txt
**Depends on**: Phase 24 (Firebase frontend gone), Phase 25 (Firestore backend gone), Phase 26 (Gemini gone)
**Requirements**: STOR-01, STOR-02, DB-04, CLEAN-01
**Success Criteria** (what must be TRUE):
  1. Local filesystem is default storage when GCS_BUCKET_NAME is empty -- no warnings or errors in logs
  2. `google-cloud-storage` code paths and pip dependency removed
  3. One-time Firestore-to-PostgreSQL migration script handles all collections with per-table count verification
  4. `requirements.txt` has zero Google dependencies (firebase-admin, google-cloud-firestore, google-cloud-storage, google-genai)
  5. App starts and serves all five tools with only PostgreSQL, local filesystem, and optionally LM Studio
  6. GitHub Actions CI/CD workflow (.github/workflows/deploy.yml) disabled or removed -- no auto-deploy to Cloud Run

## Progress

**Execution Order:**
Phases 22 -> 23 -> 24 -> 25 -> 26 -> 27
(Phase 26 can run in parallel with 24-25 since AI is independent of auth/DB)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 22. Database Models & Schema | v2.0 | 2/2 | Complete    | 2026-03-25 |
| 23. Auth Backend | v2.0 | 2/2 | Complete    | 2026-03-25 |
| 24. Auth Frontend & Firebase Removal | v2.0 | 0/2 | Not started | - |
| 25. Database Service Port | v2.0 | 0/0 | Not started | - |
| 26. AI Provider Swap | v2.0 | 0/0 | Not started | - |
| 27. Storage & Dependency Cleanup | v2.0 | 0/0 | Not started | - |
