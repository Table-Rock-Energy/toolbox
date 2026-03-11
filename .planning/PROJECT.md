# Table Rock Tools

## What This Is

Consolidated internal web application for Table Rock Energy's land and revenue teams. Provides five document-processing tools (Extract, Title, Proration, Revenue, GHL Prep) plus integrations with GoHighLevel, RRC data, and optional AI validation. React 19 SPA frontend with FastAPI backend, deployed to Google Cloud Run.

## Core Value

The tools must reliably process uploaded documents (PDFs, CSVs, Excel) and return accurate, exportable results. Everything else is secondary to parsing accuracy and data integrity.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

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

### Active

<!-- Current scope: security hardening + quality improvements from code review feedback. -->

- [ ] Enforce authentication on all tool endpoints (Extract, Title, Proration, Revenue, GHL Prep, ETL, History)
- [ ] Add admin-only access control to admin endpoints (user management, settings, profile image)
- [ ] Replace spoofable x-user-email/x-user-name headers with verified token-based user identity
- [ ] Lock down CORS: explicit origin allowlist from config, wildcard only in development
- [ ] Require ENCRYPTION_KEY at startup — fail fast if missing, no plaintext fallback
- [ ] Encrypt admin/app settings before Firestore persistence
- [ ] Enforce profile image upload ownership (user_id must match authenticated user unless admin)
- [ ] Restructure Firestore revenue statements: move rows to subcollection to avoid document size limits
- [ ] Fix ETL entity detail N+1 fetches with batch retrieval
- [ ] Define required Firestore composite indexes and remove client-side sorting fallback
- [ ] Add backend test suite: auth-protected route smoke tests, parsing pipeline regression tests

### Out of Scope

- Frontend test suite — focus on backend tests first for this milestone
- Rate limiting — important but separate concern, defer to next milestone
- Structured logging / request tracing — defer to next milestone
- Dead PostgreSQL code removal — tech debt cleanup, not security-critical
- Frontend page component decomposition — UX improvement, not this milestone
- Deprecated FastAPI lifecycle events — minor, defer
- datetime.utcnow() migration — minor, defer
- Broad exception narrowing — incremental improvement, defer

## Current Milestone: v1.3 Security Hardening

**Goal:** Harden authentication, authorization, encryption, and data modeling across the application, then add backend test coverage for critical paths.

**Target features:**
- Auth enforcement on all tool endpoints
- Admin-only access control on admin endpoints
- Token-based user identity (replace spoofable headers)
- CORS lockdown with explicit origin allowlist
- Mandatory ENCRYPTION_KEY with encrypted Firestore settings
- Profile image upload ownership enforcement
- Firestore revenue subcollection restructuring
- ETL batch retrieval (fix N+1)
- Firestore composite index definitions
- Backend test suite (auth smoke tests, parsing regression tests)

## Context

- **Production URL:** https://tools.tablerocktx.com
- **Users:** Small internal team at Table Rock Energy (land and revenue departments)
- **Deployment:** Google Cloud Run, us-central1, `--allow-unauthenticated` (network-level access open, auth enforced at app level)
- **Code review source:** Automated code review identified 11 findings across security, performance, data modeling, and testing
- **Primary admin:** james@tablerocktx.com
- **Auth model:** Firebase Auth tokens verified server-side, JSON allowlist for authorization
- **Existing auth infrastructure:** `require_auth`, `require_admin`, `get_current_user` dependencies already exist in `backend/app/core/auth.py` — they just aren't applied to most routes

## Constraints

- **Stack:** React 19 + FastAPI + Firestore + Firebase Auth — no changes to core stack
- **Deployment:** Cloud Run with `--allow-unauthenticated` — security must be enforced at application layer
- **Backwards compatibility:** Frontend already sends auth tokens — backend changes should not break existing frontend auth flow
- **Memory:** 1Gi Cloud Run instances — Firestore restructuring should reduce document payload sizes
- **RRC SSL:** RRC website requires custom SSL adapter with `verify=False` — this is a known, accepted risk

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| All endpoints require auth except /api/health | Internal tool, no public API consumers | — Pending |
| Admin endpoints are admin-only | Prevent privilege escalation, protect user management | — Pending |
| Job history visible to all authenticated users | Small team, transparency preferred over isolation | — Pending |
| Require ENCRYPTION_KEY at startup | Fail fast prevents accidental plaintext secret storage | — Pending |
| Revenue rows as Firestore subcollection | Avoids 1MB document size limit, reduces read costs | — Pending |
| Backend tests first, frontend tests later | Security and parsing accuracy are highest risk areas | — Pending |

---
*Last updated: 2026-03-11 after milestone v1.3 start*
