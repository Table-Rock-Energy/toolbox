# Milestones

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

