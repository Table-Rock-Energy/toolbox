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

### Active

<!-- Empty — ready for next milestone requirements. -->

(None — use `/gsd:new-milestone` to define next scope)

### Out of Scope

- AI-powered OCR correction — PDF text extraction via PyMuPDF is sufficient for born-digital filings
- Automatic Convey 640 download/scraping — user provides the file manually
- Batch processing of multiple ECF filings at once — one filing per upload
- GoHighLevel direct send from ECF results — use existing GHL Prep workflow after export
- Fuzzy name matching between PDF/CSV respondents — entry-number matching is sufficient for now
- Frontend test suite — defer
- Rate limiting — defer
- Structured logging / request tracing — defer

## Context

- **Production URL:** https://tools.tablerocktx.com
- **Users:** Small internal team at Table Rock Energy (land and revenue departments)
- **Deployment:** Google Cloud Run, us-central1, `--allow-unauthenticated` (network-level access open, auth enforced at app level)
- **Primary admin:** james@tablerocktx.com
- **Auth model:** Firebase Auth tokens verified server-side, JSON allowlist for authorization
- **Codebase:** ~476K LOC (TypeScript + Python), React 19 + FastAPI + Firestore
- **Test suite:** 50+ pytest tests (auth smoke, CORS, extract parsers, revenue parser), CI via GitHub Actions
- **Extract formats:** Standard OCC Exhibit A, ECF multiunit well filings (with optional Convey 640 CSV/Excel)
- **Shipped:** v1.3 Security Hardening (2026-03-11), v1.4 ECF Extraction (2026-03-12)

## Constraints

- **Stack:** React 19 + FastAPI + Firestore + Firebase Auth — no changes to core stack
- **No new dependencies:** Use existing PyMuPDF for PDF text extraction, pandas for CSV/Excel processing
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

---
*Last updated: 2026-03-12 after v1.4 milestone completion*
