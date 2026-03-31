# Table Rock Tools

## What This Is

Consolidated internal web application for Table Rock Energy's land and revenue teams. Provides five document-processing tools (Extract, Title, Proration, Revenue, GHL Prep) plus integrations with GoHighLevel, RRC data, and optional AI validation. Extract tool now supports three format modes: standard OCC Exhibit A, ECF multiunit well filings, and Convey 640 CSV/Excel. React 19 SPA frontend with FastAPI backend, deployed to Google Cloud Run. All endpoints authenticated via Firebase Auth with encrypted settings storage.

## Core Value

The tools must reliably process uploaded documents (PDFs, CSVs, Excel) and return accurate, exportable results. Everything else is secondary to parsing accuracy and data integrity.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Extract tool: upload OCC Exhibit A PDFs, extract party names/addresses/entity types, export to CSV/Excel — existing
- ✓ Title tool: upload Excel/CSV title opinions, consolidate owner info, detect entities, export — existing
- ✓ Proration tool: upload mineral holders CSV, NRA calculations with RRC data, export to Excel/PDF — existing
- ✓ Revenue tool: upload revenue PDFs (EnergyLink/Enverus/Energy Transfer), parse to M1 CSV format — existing
- ✓ GHL Prep tool: transform Mineral export CSV for GoHighLevel import — existing
- ✓ GoHighLevel bulk send with SSE progress tracking — existing
- ✓ Firebase Auth with Google Sign-In and email/password — existing
- ✓ RRC data pipeline: bulk download, county-level on-demand, individual HTML scraping — existing
- ✓ Firestore persistence for jobs, entries, RRC data — existing
- ✓ GCS file storage with local filesystem fallback — existing
- ✓ Dashboard with tool cards and recent jobs — existing
- ✓ Admin settings with user allowlist management — existing
- ✓ Contact enrichment (PDL + SearchBug) — existing
- ✓ AI validation via Gemini — existing
- ✓ CI/CD: push to main deploys to Cloud Run — existing
- ✓ All tool endpoints require Firebase token auth (unauthenticated → 401) — v1.3
- ✓ Frontend fail-closed auth when backend unreachable, with DEV override — v1.3
- ✓ CORS explicit origin allowlist, wildcard only in dev — v1.3
- ✓ App fails fast if ENCRYPTION_KEY missing in production — v1.3
- ✓ Sensitive settings encrypted before Firestore persistence — v1.3
- ✓ Backend test suite: auth smoke tests + parser regression tests + CI — v1.3
- ✓ ECF PDF parsing with section-aware entry extraction and entity detection — v1.4
- ✓ Case metadata extraction from ECF PDF headers (county, legal description, applicant, case number, well name) — v1.4
- ✓ Convey 640 CSV/Excel parsing with name normalization and ZIP preservation — v1.4
- ✓ PDF-authoritative merge when both PDF and CSV are provided — v1.4
- ✓ Mineral export with case metadata populating Notes/Comments — v1.4
- ✓ Dual-file upload UI in Extract page (PDF required, CSV optional) — v1.4
- ✓ Entity type detection for ECF respondents (Individual, Trust, LLC, Estate, etc.) — v1.4
- ✓ Merged results export to mineral CSV/Excel format — v1.4
- ✓ ECF upload flow fix: auto-detect format, staged upload with explicit Process button — v1.5
- ✓ Universal enrichment UI: Clean Up / Validate / Enrich buttons across all tool pages — v1.5
- ✓ Pipeline API: AI cleanup, address validation, contact enrichment with ProposedChange format — v1.5
- ✓ Preview state as single source of truth for exports (inline edits, exclusions, enrichment) — v1.5
- ✓ Tool-specific AI prompts: name cleanup, figure verification, cross-file comparison — v1.5
- ✓ Provider-agnostic LLM interface (Gemini swappable via admin settings) — v1.5
- ✓ RRC fetch-missing: compound lease splitting, semaphore-throttled concurrency, direct data return, sub-lease tooltips — v1.6
- ✓ Admin GET endpoints gated with require_admin, preference/profile endpoints with require_auth — v1.6
- ✓ History user-scoping (non-admin sees own jobs only) and delete ownership checks (403 for non-owner) — v1.6
- ✓ GHL smart_list_name removed from backend model, API, and frontend types — v1.6
- ✓ 403 delete error modal on all 5 tool pages — v1.6
- ✓ Unified enrichment modal: single Enrich button replaces 3-button toolbar, progress modal with step indicators and ETA, per-cell highlighting with original-value tooltips, global undo — v1.6
- ✓ OperationContext provider: batch-aware pipeline engine with 25-entry batches, progressive auto-apply, per-batch ETA, skip-and-continue on failure — v1.7
- ✓ Operation persistence across navigation: OperationProvider wraps Outlet in MainLayout, auto-restore on mount — v1.7
- ✓ Batch progress UI: sub-progress bar ("Batch N of M"), amber partial-failure text, cancel confirmation dialog — v1.7
- ✓ Configurable batch size, concurrency, and retry limits via admin settings with Firestore persistence — v1.7
- ✓ Concurrent Gemini batch execution via asyncio.Semaphore with thread-safe rate limiting — v1.7
- ✓ Backend disconnect detection: pipeline endpoints stop Gemini processing when client disconnects — v1.7
- ✓ End-of-step retry: failed batches automatically retried once before returning partial results — v1.7
- ✓ Operation status bar in MainLayout header: shows active operations with tool name, step, and batch progress — v1.7
- ✓ Auto-restore completed results on tool page return with clearOperation after apply — v1.7
- ✓ Revenue multi-PDF streaming: NDJSON per-file progress with inline UI counter in both panel views — v1.7
- ✓ Proration cache-first lookups: in-memory RRC cache with startup pre-warming, batch Firestore reads via asyncio.gather, cache invalidation after RRC sync — v1.7

- ✓ Key-based enrichment highlight tracking (entry_key replaces entry_index) — v1.8
- ✓ Filter-anytime correctness: filters work before/during/after enrichment without breaking highlights — v1.8
- ✓ Enrichment scoped to visible/filtered rows only (saves API costs) — v1.8
- ✓ Case-insensitive entity type filtering across all tool pages — v1.8
- ✓ Export respects current filter state with enrichment changes applied — v1.8
- ✓ Click-to-reveal original values in green enrichment cells — v1.8
- ✓ No-change checkmark indicator for processed-but-unchanged rows — v1.8
- ✓ RRC lease-only search first with district+lease fallback — v1.8
- ✓ Fetch-missing stop button with AbortController and partial results — v1.8

- ✓ Security headers middleware (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) on every API response — v2.1
- ✓ Pytest tests for all 6 security headers — v2.1
- ✓ Dead VITE_FIREBASE_* ARGs removed from Dockerfile — v2.1
- ✓ Hardcoded admin email extracted to DEFAULT_ADMIN_EMAIL env var with fallback — v2.1

- ✓ Replace Firebase Auth with local JWT auth (bcrypt + PostgreSQL users table) — v2.0
- ✓ Backend /api/auth/login and /api/auth/me endpoints returning JWT tokens — v2.0
- ✓ Replace Firebase token verification middleware with JWT verification — v2.0
- ✓ CLI/startup script to create initial admin user — v2.0
- ✓ Frontend local auth context replacing Firebase Auth context — v2.0
- ✓ Remove firebase.ts, Firebase npm packages, and all Firebase imports — v2.0
- ✓ Remove Firestore entirely — PostgreSQL as only database via SQLAlchemy — v2.0
- ✓ Extend SQLAlchemy models to cover all Firestore collections — v2.0
- ✓ Alembic initialized with async template, initial migration generated — v2.0
- ✓ One-time Firestore to PostgreSQL migration script — v2.0
- ✓ Every firestore_service.py function has PostgreSQL equivalent in db_service.py — v2.0
- ✓ OpenAI-compatible provider for LM Studio — v2.0
- ✓ Provider factory routing AI calls based on AI_PROVIDER config — v2.0
- ✓ Gemini removed, LM Studio is only AI backend — v2.0
- ✓ Local filesystem default, no GCS warnings — v2.0
- ✓ google-cloud-storage removed — v2.0
- ✓ All Google dependencies removed from requirements.txt — v2.0

### Active

<!-- v2.2 Post-Migration Fixes & AI Enrichment -->
- AI enrichment pipeline working end-to-end with LM Studio on server
- Revenue Decimal-to-float coercion for DB persistence
- Admin password hashing import fix
- Job record user email-to-UUID resolution
- GHL-prep tool filter fix
- RRC data PostgreSQL migration + model filesystem discovery
- Nginx reverse proxy configuration

### Out of Scope

- AI-powered OCR correction — PDF text extraction via PyMuPDF is sufficient for born-digital filings
- Automatic Convey 640 download/scraping — user provides the file manually
- Batch processing of multiple ECF filings at once — one filing per upload
- GoHighLevel direct send from ECF results — use existing GHL Prep workflow after export
- Fuzzy name matching between PDF/CSV respondents — entry-number matching is sufficient for now
- GHL SmartList API creation — SmartLists are UI-only saved filters in GHL, not API-creatable (confirmed, abandoned)
- Frontend test suite — defer
- Rate limiting — defer
- Structured logging / request tracing — defer

## Current Milestone: v2.2 Post-Migration Fixes & AI Enrichment

**Goal:** Stabilize the on-prem migration by fixing bugs surfaced in production and getting AI enrichment working end-to-end with LM Studio.

**Target features:**
- AI enrichment pipeline debugging (LM Studio connectivity, prompt formatting, response parsing on server)
- Retroactively track recent ad-hoc fixes (revenue Decimal coercion, admin password hashing, job record user resolution, GHL-prep filter, RRC PostgreSQL migration)
- Nginx reverse proxy configuration validation

## Current State

**Shipped:** v2.1 Security Headers & Cleanup (2026-03-27)
- All 6 BrandPod security headers in place via middleware
- Dead Firebase Dockerfile references removed
- Admin email configurable via DEFAULT_ADMIN_EMAIL env var
- 7 new pytest tests for security headers (388+ total suite)

## Context

- **Production URL:** https://tools.tablerocktx.com
- **Users:** Small internal team at Table Rock Energy (land and revenue departments)
- **Deployment:** Google Cloud Run (current), migrating to on-prem Ubuntu server with Docker
- **Primary admin:** james@tablerocktx.com
- **Auth model:** Local JWT + PostgreSQL users table (migrated from Firebase Auth in v2.0)
- **Codebase:** ~476K LOC (TypeScript + Python), React 19 + FastAPI + PostgreSQL
- **Test suite:** 380+ pytest tests (auth, CORS, security headers, extract parsers, revenue parser), CI via GitHub Actions
- **Extract formats:** Standard OCC Exhibit A, ECF multiunit well filings (with optional Convey 640 CSV/Excel)
- **Shipped:** v1.3 Security Hardening (2026-03-11), v1.4 ECF Extraction (2026-03-12), v1.5 Enrichment Pipeline (2026-03-17), v1.6 Pipeline Fixes & Unified Enrichment (2026-03-19)
- **Shipped:** v1.7 Batch Processing & Resilience (2026-03-20)
- **Shipped:** v1.8 Preview System Overhaul (2026-03-24)
- **Shipped:** v2.0 Full On-Prem Migration (2026-03-25), v2.1 Security Headers & Cleanup (2026-03-27)

## Constraints

- **Stack:** React 19 + FastAPI + PostgreSQL + local JWT auth
- **No new dependencies (parsing):** Use existing PyMuPDF for PDF text extraction, pandas for CSV/Excel processing
- **New dependencies (infra):** bcrypt, python-jose (JWT), openai (LM Studio client)
- **Mineral export format:** Output must match existing MINERAL_EXPORT_COLUMNS (shared across Extract/Title tools)
- **Memory:** 1Gi Cloud Run instances
- **RRC SSL:** RRC website requires custom SSL adapter with `verify=False` — known, accepted risk

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| All endpoints require auth except /api/health | Internal tool, no public API consumers | ✓ Good — v1.3 |
| Router-level auth via dependencies on include_router() | Prevents accidental unprotected endpoints | ✓ Good — v1.3 |
| GHL/admin routers excluded from router-level auth | SSE needs query-param auth; check_user must be unauthenticated | ✓ Good — v1.3 |
| Fail-closed frontend auth (even in dev mode) | Prevents dev/prod behavior divergence | ✓ Good — v1.3 |
| Storage-boundary encryption (encrypt before write, decrypt after read) | Clean separation, all write paths covered | ✓ Good — v1.3 |
| Inline text fixtures for parser tests (no PDF files) | Self-contained, fast, no binary fixtures | ✓ Good — v1.3 |
| Backend tests first, frontend tests later | Security and parsing accuracy are highest risk | ✓ Good — v1.3 |
| ECF extraction as new mode in Extract tool | Reuses existing infrastructure (format detection, name parsing, export) | ✓ Good — v1.4 |
| PDF required, CSV optional | PDF has authoritative data; CSV just accelerates processing | ✓ Good — v1.4 |
| PDF is source of truth for respondent data | Convey 640 has OCR errors; PDF text is cleaner | ✓ Good — v1.4 |
| Map Convey 640 metadata (county, STR, case#) to mineral export | Maximizes field coverage in output | ✓ Good — v1.4 |
| Entry-number matching (not fuzzy) for PDF/CSV merge | Simple, reliable, covers the common case | ✓ Good — v1.4 |
| Dedicated ecf_parser.py module (not extending parser.py) | Clean separation, ECF has distinct parsing logic | ✓ Good — v1.4 |

| Per-endpoint require_admin on admin GET routes (not router-level) | Granular control — check_user needs to stay unauthenticated | ✓ Good — v1.6 |
| History user-scoping with admin override | Non-admin sees own jobs; admin sees all | ✓ Good — v1.6 |
| Compound lease splitting with district inheritance | Handles "02-12345/12346" by splitting and inheriting district prefix | ✓ Good — v1.6 |
| Unified enrichment as single-button modal (not improving 3-button toolbar) | Users want fewer clicks; modal contains all progress; undo is more discoverable | Pending live verification — v1.6 |
| Local variable threading in runAllSteps (not React state) | Avoids stale closure between sequential async steps | ✓ Good — v1.6 |
| SecurityHeadersMiddleware registered before CORS (LIFO) | Starlette LIFO ordering ensures headers applied after CORS processing | ✓ Good — v2.1 |
| CSP allows unsafe-inline for style-src | React injects inline styles that would be blocked otherwise | ✓ Good — v2.1 |
| Admin email as Pydantic Settings field (not module constant) | Configurable via DEFAULT_ADMIN_EMAIL env var with sensible fallback | ✓ Good — v2.1 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-31 after v2.2 milestone start*
