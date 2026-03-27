# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.3 — Security Hardening

**Shipped:** 2026-03-11
**Phases:** 3 | **Plans:** 6 | **Tasks:** 13

### What Was Built
- Router-level auth enforcement on all 9 tool routers (+ dev-mode bypass)
- Frontend fail-closed auth with silent 401 token refresh and SSE query-param auth
- CORS lockdown with explicit origin allowlist from config
- Startup ENCRYPTION_KEY guard with storage-boundary encrypt/decrypt
- 32 auth smoke tests covering all protected routes
- Extract + Revenue parser regression tests with GitHub Actions CI

### What Worked
- Phase ordering (auth → encryption → tests) avoided rework — tests verified the final hardened system
- Router-level `dependencies=[Depends(require_auth)]` pattern prevented accidental unprotected endpoints
- Storage-boundary encryption pattern (encrypt before write, decrypt after read) cleanly covered all write paths including the seed path
- Inline text fixtures for parser tests kept tests fast and self-contained without binary fixtures
- All 3 phases completed in a single day with 6 plans

### What Was Inefficient
- Phase 3 roadmap checkbox wasn't updated after 03-02 completion, causing a stale "1/2 plans complete" display
- The audit found 7 tech debt items that were all pre-existing — spending time classifying them could have been skipped
- GHL connections test had a Firestore async client event loop issue requiring a mock workaround — fragile test isolation

### Patterns Established
- Router-level auth via `dependencies=[Depends(require_auth)]` on `include_router()` calls
- Storage-boundary encryption: encrypt before Firestore write, decrypt after read
- Auth smoke test pattern: unauthenticated → 401, authenticated → != 401 (not == 200)
- Inline text fixtures for parser tests instead of PDF file fixtures
- CI runs with `FIRESTORE_ENABLED=false` and `DATABASE_ENABLED=false` for isolation

### Key Lessons
1. Exclude routers that need special auth handling (SSE query-param, unauthenticated check endpoints) from blanket router-level auth
2. Test assertions should match what you're actually testing — `!= 401` for auth gates, not `== 200` which depends on backend services
3. Storage-boundary encryption must cover ALL write paths including init/seed paths, not just the primary save path

### Cost Observations
- Model mix: ~80% opus, ~20% sonnet
- Sessions: ~5
- Notable: All 3 phases completed in 1 day, fastest milestone yet

---

## Milestone: v1.4 — ECF Extraction

**Shipped:** 2026-03-12
**Phases:** 4 | **Plans:** 7 | **Timeline:** 2 days

### What Was Built
- ECF PDF parser with section-aware entry parsing, entity detection, and case metadata extraction
- Convey 640 CSV/Excel parser with name normalization pipeline and ZIP preservation
- PDF-authoritative merge service with entry-number matching and mismatch warnings
- Export enhancement: case metadata flows to Notes/Comments in mineral export
- Dual-file upload UI with metadata panel and auto-populated mineral export modal

### What Worked
- Independent phases (1 & 2) enabled parallel-capable development — CSV parser built without waiting for PDF parser
- TDD pattern from v1.3 carried forward — all three backend phases had tests before implementation
- Dedicated parser modules (ecf_parser.py, convey640_parser.py, merge_service.py) kept logic isolated and testable
- Reusing existing Extract infrastructure (format detection, entity types, mineral export columns) avoided rework
- 7 plans completed in ~1 hour total execution time (avg 8 min/plan)

### What Was Inefficient
- Phase 4 (frontend) executed before Phases 1-3 (backend) due to parallel session work — caused integration issues discovered only during audit
- Milestone audit found case_metadata not sent in export request (EXP-03) — a boundary that TDD didn't catch because frontend has no test suite
- Phase 4 missing VERIFICATION.md — the only phase without formal verification documentation
- 04-02-SUMMARY missing FE-02/03/04 in requirements-completed frontmatter — documentation hygiene gap

### Patterns Established
- Dedicated parser module per format (ecf_parser.py, convey640_parser.py) following consistent parse_X() API
- Name normalization pipeline with ordered transformations (strip numbers → clean suffixes → handle markers)
- Entry-number matching for cross-source merge (simple, reliable, avoids fuzzy matching complexity)
- Section-aware parsing with section_type tags on entries for downstream filtering

### Key Lessons
1. Milestone audit catches integration boundary bugs that unit tests miss — the frontend→backend export boundary was broken despite all backend tests passing
2. When phases can run in parallel, ensure integration tests cover the seams between them before declaring complete
3. Documentation hygiene (VERIFICATION.md, SUMMARY frontmatter) should be part of the plan, not an afterthought

### Cost Observations
- Model mix: ~70% opus, ~30% sonnet
- Sessions: ~4
- Notable: Fastest per-plan velocity (8 min avg), total execution under 1 hour

---

## Milestone: v1.5 — Enrichment Pipeline & Bug Fixes

**Shipped:** 2026-03-17
**Phases:** 5 | **Plans:** 12 | **Timeline:** 4 days

### What Was Built
- ECF upload flow fix: auto-detect format, staged upload with explicit Process button
- RRC & GHL bug fixes (fetch-missing improvements, GHL connection management)
- Universal enrichment UI: Clean Up / Validate / Enrich buttons across all tool pages
- Pipeline API with AI cleanup, address validation, contact enrichment
- Preview state as single source of truth for exports
- Tool-specific AI prompts for each pipeline step
- Provider-agnostic LLM interface (Gemini swappable via admin settings)

### What Worked
- Preview state refactor (Phase 7) unified all data flow through a single state — eliminated data divergence between display and export
- Pipeline API design with ProposedChange format enabled the unified enrichment flow in v1.6
- 5 phases completed in 4 days — good velocity for the scope

### What Was Inefficient
- No retrospective written at milestone completion — gap in documentation discipline
- v1.5 milestone completion skipped directly to v1.6 planning without formal archival

### Patterns Established
- Preview state as single source of truth pattern (previewEntries → export)
- Pipeline API with ProposedChange format for all enrichment steps
- Tool-specific AI prompt configuration via admin settings

### Key Lessons
1. Preview state unification pays off immediately — every downstream feature benefits
2. Pipeline API abstraction enables rapid iteration on enrichment steps

### Cost Observations
- Sessions: ~6-8
- Notable: Largest milestone by phase count (5 phases, 12 plans)

---

## Milestone: v1.6 — Pipeline Fixes & Unified Enrichment

**Shipped:** 2026-03-19
**Phases:** 3 | **Plans:** 6 | **Timeline:** 2 days

### What Was Built
- Admin GET endpoints gated with `require_admin`; check_user remains unauthenticated
- History user-scoping (non-admin sees own jobs only) with delete ownership checks and 403 modal
- GHL `smart_list_name` fully removed from backend, API, and frontend
- Compound lease splitting with district inheritance + direct data return + per-row status UI
- Single "Enrich" button replacing 3-button toolbar with progress modal, ETA, and step indicators
- Per-cell change tracking with green highlighting, original-value tooltips, and global undo

### What Worked
- Wave-based parallel execution: Phase 10 (3 plans) executed efficiently in 2 waves
- Local variable threading pattern in `runAllSteps()` avoided stale React closure bugs
- Pre-enrichment snapshot for global undo — simple and reliable
- Clean separation: Plan 01 (hook/data layer) → Plan 02 (UI layer) kept both plans focused

### What Was Inefficient
- Phase 12 browser verification deferred to production — local dev environment unavailable during execution
- SUMMARY one-liners not populated by executors — summary-extract returned null for all plans
- EnrichmentToolbar left as orphaned export after replacement — should be cleaned up

### Patterns Established
- Local variable threading for sequential async operations (avoids React state staleness)
- Per-cell change tracking with Map<string, EnrichmentCellChange> keyed by `${entryIndex}:${field}`
- Pre-operation snapshot for global undo (shallow copy array before mutation)
- Per-endpoint `Depends(require_admin)` for granular auth (vs router-level for broad protection)

### Key Lessons
1. Separate hook (data) and UI (component) plans — enables independent testing and focused reviews
2. Local variable threading is essential for sequential async React operations — React state updates batch and cause stale closures
3. Browser verification should not be skipped — even when local dev is down, production testing should happen before milestone completion

### Cost Observations
- Model mix: ~60% opus, ~40% sonnet
- Sessions: ~3
- Notable: 2-day milestone, tightest timeline yet for 6 plans across 3 phases

---

## Milestone: v2.0 — Full On-Prem Migration

**Shipped:** 2026-03-25
**Phases:** 6 | **Plans:** 13

### What Was Built
- Local JWT auth replacing Firebase Auth (PyJWT + pwdlib[bcrypt] + PostgreSQL users table)
- Full Firestore→PostgreSQL migration with SQLAlchemy async sessions and Alembic
- OpenAI-compatible AI provider for LM Studio replacing Gemini
- Stripped all Google Cloud dependencies (Firebase, Firestore, GCS, google-genai)
- One-time migration script with 16 collection handlers and per-table verification
- Disabled Cloud Run CI/CD — app runs fully on-prem

### What Worked
- Phase ordering: models→auth backend→auth frontend→DB port→AI swap→cleanup avoided circular dependencies
- AI provider swap was cleanly independent of auth/DB work — could have parallelized
- Incremental Firestore removal (service-by-service swap) prevented big-bang breakage
- 78+ tests passing throughout migration gave confidence at each step

### What Was Inefficient
- 27-01 plan checkbox left unchecked in ROADMAP despite being complete — caused confusion at milestone completion
- Some tech debt accepted (VITE_FIREBASE_* Dockerfile ARGs, JSON allowlist dual-path) that could have been cleaned inline

### Patterns Established
- Local auth pattern: PyJWT + pwdlib[bcrypt] + SQLAlchemy users table
- Provider abstraction: LLMProvider protocol with factory routing
- Sync session factory for background threads outside asyncio event loop
- Migration script pattern: per-collection handlers with count verification

### Key Lessons
1. Plan checkbox state in ROADMAP.md must be maintained — stale state causes confusion at milestone boundary
2. "Full removal" milestones benefit from a final grep sweep phase to catch stragglers
3. Accepting tech debt items should be explicitly tracked in STATE.md blockers (which was done correctly)

### Cost Observations
- Model mix: ~70% opus, ~30% sonnet
- Sessions: ~4
- Notable: Largest infrastructure change (6 phases, 13 plans) completed in 1 day

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Plans | Key Change |
|-----------|----------|--------|-------|------------|
| v1.3 | ~5 | 3 | 6 | First milestone with GSD workflow, audit-before-complete |
| v1.4 | ~4 | 4 | 7 | TDD carried forward, parallel phases, audit caught integration gap |
| v1.5 | ~7 | 5 | 12 | Largest milestone, preview state unification, pipeline API pattern |
| v1.6 | ~3 | 3 | 6 | Tightest timeline (2 days), wave-based parallel execution |
| v1.7 | ~3 | 5 | 9 | Batch processing engine, operation persistence, multi-PDF streaming |
| v1.8 | ~2 | 4 | 6 | Key-based tracking, filter correctness, minimal-touch milestone |
| v2.0 | ~4 | 6 | 13 | Full infra migration (Firebase→JWT, Firestore→PG, Gemini→LM Studio) |

### Cumulative Quality

| Milestone | Tests | Coverage | Key Addition |
|-----------|-------|----------|-------------|
| v1.3 | 50+ | Auth + parsers | CI workflow, auth smoke tests |
| v1.4 | 60+ | + ECF/Convey640/merge parsers | ECF parser tests, merge service tests, Convey 640 tests |
| v1.5 | 60+ | + pipeline integration | Pipeline API smoke tests |
| v1.6 | 60+ | + admin auth | Admin endpoint auth tests, history scoping tests |
| v1.7 | 60+ | + batch/pipeline | Batch engine tests, disconnect detection |
| v1.8 | 60+ | + filter/highlight | Filter correctness, key-based tracking |
| v2.0 | 78+ | + JWT auth + DB port | JWT auth tests, migration script verification |

### Top Lessons (Verified Across Milestones)

1. Phase ordering matters — build features before testing them
2. Router-level auth is safer than per-endpoint auth (prevents accidental exposure); per-endpoint for granular control
3. Milestone audits catch integration boundary bugs that per-phase TDD misses — run before completing
4. Preview state unification pays dividends across all downstream features
5. Local variable threading is essential for sequential async React operations
6. "Full removal" milestones need a final grep sweep to catch stragglers
7. Plan checkbox state must stay current — stale ROADMAP state causes confusion at milestone boundary
