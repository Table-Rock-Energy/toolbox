# Milestones

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

