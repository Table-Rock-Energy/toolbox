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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.3 | ~5 | 3 | First milestone with GSD workflow, audit-before-complete |

### Cumulative Quality

| Milestone | Tests | Coverage | Key Addition |
|-----------|-------|----------|-------------|
| v1.3 | 50+ | Auth + parsers | CI workflow, auth smoke tests |

### Top Lessons (Verified Across Milestones)

1. Phase ordering matters — build features before testing them
2. Router-level auth is safer than per-endpoint auth (prevents accidental exposure)
