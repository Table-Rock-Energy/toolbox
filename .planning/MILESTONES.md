# Milestones

## v2.0 Full On-Prem Migration (Shipped: 2026-03-25)

**Phases completed:** 6 phases, 13 plans
**Commits:** 78 (8230083..bc3a739)
**Files changed:** 140 (+15,532 / -6,476)
**Timeline:** 1 day (2026-03-25)

**Key accomplishments:**

- Replaced Firebase Auth with local JWT auth (PyJWT + pwdlib[bcrypt]) against PostgreSQL users table
- Removed Firestore entirely — PostgreSQL is sole database via SQLAlchemy async sessions with Alembic migrations
- Created OpenAI-compatible provider for LM Studio replacing Gemini AI
- Stripped all Google Cloud dependencies (Firebase, Firestore, GCS, Gemini) from code and requirements.txt
- Created one-time Firestore→PostgreSQL migration script with 16 collection handlers
- Disabled GitHub Actions CI/CD (no more auto-deploy to Cloud Run)
- 78+ backend tests passing, TypeScript compiles clean

**Tech debt carried forward:**

- VITE_FIREBASE_* ARGs in Dockerfile (user chose not to modify Dockerfile)
- JSON allowlist dual-path with PostgreSQL users table
- check_user endpoint unauthenticated (by design)

---

## v1.8 Preview System Overhaul (Shipped: 2026-03-24)

**Phases completed:** 4 phases, 6 commits
**Commits:** 00fafd1..f1ea148
**Files changed:** 23 (+565 / -282)
**Timeline:** 1 day (2026-03-24)

**Key accomplishments:**

- Root cause fix: enrichment highlights keyed by stable entry_key instead of array index
- Enrichment scoped to visible/filtered rows only (saves Gemini API costs)
- Case-insensitive entity type filtering across all tool pages
- No-change checkmark indicator for processed-but-unchanged rows
- RRC lease-only search first with district+lease fallback
- Fetch-missing stop button with AbortController and partial results
- Fixed pre-existing lint errors in FetchRrcModal and usePreviewState

**Guardrail enforced:** Upload flows, backend parsers, panel layout, enrichment modal UX, OperationContext navigation, batch engine, API signatures, auth/admin, styling — all untouched per user requirement.

---

## v1.7 Batch Processing & Resilience (Shipped: 2026-03-20)

**Phases completed:** 5 phases, 9 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v1.6 Pipeline Fixes & Unified Enrichment (Shipped: 2026-03-19)

**Phases completed:** 3 phases, 6 plans
**Commits:** 48 (b4c5eae..f95e78a)
**Files changed:** 54 (+7,248 / -1,644)
**Timeline:** 2 days (2026-03-18 → 2026-03-19)

**Key accomplishments:**

- Admin GET endpoints gated with `require_admin`; `check_user` remains unauthenticated for login flow
- History user-scoping — non-admin sees own jobs only; delete restricted to owner/admin with 403 modal on all 5 tool pages
- GHL `smart_list_name` removed from backend model, API, and frontend types
- Compound lease splitting with district inheritance + direct data return from fetch-missing + per-row status UI
- Single "Enrich" button replaces 3-button toolbar with progress modal (step indicators, ETA), live preview updates, and per-cell highlighting with original-value tooltips
- Global enrichment undo via pre-enrichment snapshot

**Tech debt carried forward:**

- EnrichmentToolbar component still exported from barrel (unused after replacement)
- Phase 12 browser verification deferred to production (5 visual tests pending)
- Nyquist validation incomplete on all 3 phases (draft/missing VALIDATION.md)

---

## v1.4 ECF Extraction (Shipped: 2026-03-12)

**Phases completed:** 4 phases, 7 plans
**Commits:** 26 (14e841a..58224e9)
**Files changed:** 126 (+21,787 / -275)
**Timeline:** 2 days (2026-03-11 → 2026-03-12)

**Key accomplishments:**

- ECF PDF parser with section-aware entry parsing, entity detection, and case metadata extraction
- Convey 640 CSV/Excel parser with name normalization pipeline and ZIP preservation
- PDF-authoritative merge service with entry-number matching and mismatch warnings
- Mineral export with case metadata flowing to Notes/Comments column
- Dual-file upload UI in Extract page with metadata panel and auto-populated mineral export

**Known gaps (from audit):**

- Phase 4 missing VERIFICATION.md (visual verification only)
- All 4 VALIDATION.md files are draft (Nyquist non-compliant)

**Tech debt carried forward:**

- Frontend PartyEntry interface missing section_type field (works at runtime)
- Fuzzy name matching between PDF/CSV deferred to future release

---

## v1.3 Security Hardening (Shipped: 2026-03-11)

**Phases completed:** 3 phases, 6 plans, 13 tasks
**Commits:** 29 (3e1c7d9..78fc6e5)
**Files changed:** 138 (+12,495 / -16,863)
**Timeline:** 1 day (2026-03-11)

**Key accomplishments:**

- Router-level auth enforcement on all 9 tool routers with dev-mode bypass
- Frontend fail-closed auth with 401 interceptor and SSE query-param token
- CORS lockdown with explicit origin allowlist (no more wildcard in production)
- Startup ENCRYPTION_KEY guard with storage-boundary encrypt/decrypt for Firestore
- Auth smoke tests covering all 32 protected routes
- Parser regression tests (Extract + Revenue) with GitHub Actions CI workflow

**Tech debt carried forward:**

- 5 admin endpoints without auth (AUTHZ-01)
- History endpoints not user-scoped (AUTHZ-02)
- Startup guard untestable with ASGITransport
- Enverus/Energy Transfer parsers lack regression tests

---
