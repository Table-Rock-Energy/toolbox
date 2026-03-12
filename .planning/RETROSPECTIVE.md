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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.3 | ~5 | 3 | First milestone with GSD workflow, audit-before-complete |
| v1.4 | ~4 | 4 | TDD carried forward, parallel phases, audit caught integration gap |

### Cumulative Quality

| Milestone | Tests | Coverage | Key Addition |
|-----------|-------|----------|-------------|
| v1.3 | 50+ | Auth + parsers | CI workflow, auth smoke tests |
| v1.4 | 60+ | + ECF/Convey640/merge parsers | ECF parser tests, merge service tests, Convey 640 tests |

### Top Lessons (Verified Across Milestones)

1. Phase ordering matters — build features before testing them
2. Router-level auth is safer than per-endpoint auth (prevents accidental exposure)
3. Milestone audits catch integration boundary bugs that per-phase TDD misses — run before completing
