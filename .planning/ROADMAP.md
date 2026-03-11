# Roadmap: Table Rock Tools v1.3 Security Hardening

## Overview

Harden the application's security posture in three phases: enforce authentication and lock down CORS across all endpoints, require and apply encryption for sensitive stored config, then build a backend test suite that verifies the hardened system. Every phase delivers a complete, independently verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Auth Enforcement and CORS Lockdown** - All endpoints require authentication, CORS restricted to explicit origins, frontend fails closed
- [x] **Phase 2: Encryption Hardening** - Application requires encryption key at startup and encrypts sensitive settings before Firestore persistence (completed 2026-03-11)
- [ ] **Phase 3: Backend Test Suite** - Test infrastructure with auth smoke tests and parsing regression tests

## Phase Details

### Phase 1: Auth Enforcement and CORS Lockdown
**Goal**: Every API request (except health check) is verified against a valid Firebase token, CORS rejects unknown origins, and the frontend denies access when the backend is unreachable
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, SEC-01
**Success Criteria** (what must be TRUE):
  1. Unauthenticated requests to any tool endpoint (Extract, Title, Proration, Revenue, GHL Prep, History, ETL) return 401
  2. CORS preflight requests from origins not in the allowlist are rejected; production allows only `https://tools.tablerocktx.com`
  3. Frontend shows login screen (not a broken state) when the backend is unreachable, with a development-mode override for local work
  4. The admin user (`james@tablerocktx.com`) can still log in and access all tools after auth enforcement is applied (no lockout)
**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md -- Backend auth enforcement, CORS lockdown, dev-mode bypass, SSE auth, and test suite
- [x] 01-02-PLAN.md -- Frontend fail-closed auth, ApiClient 401 interceptor, SSE token, login banner

### Phase 2: Encryption Hardening
**Goal**: Sensitive API keys stored in Firestore are encrypted at rest, and the application refuses to start without the encryption key in production
**Depends on**: Phase 1
**Requirements**: ENC-01, ENC-02
**Success Criteria** (what must be TRUE):
  1. Application fails to start when `ENVIRONMENT=production` and `ENCRYPTION_KEY` is not set, with a clear error message in the logs
  2. Admin/app settings (Gemini, Google Maps, PDL, SearchBug, GHL API keys) are stored encrypted in Firestore -- raw Firestore reads show ciphertext, not plaintext
  3. Settings are decrypted transparently on read -- the application behaves identically to before from the user's perspective
**Plans:** 2/2 plans complete

Plans:
- [ ] 02-01-PLAN.md -- Startup ENCRYPTION_KEY guard, hardened encrypt/decrypt, storage boundary encryption in admin settings
- [ ] 02-02-PLAN.md -- Gap closure: encrypt settings in Firestore seed path (init_app_settings_from_firestore)

### Phase 3: Backend Test Suite
**Goal**: Critical security paths and parsing pipelines have automated test coverage that catches regressions
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. `make test` runs a pytest suite with auth mocking via `app.dependency_overrides` -- no real Firebase tokens needed
  2. Every protected route has a smoke test confirming 401 without token and success with valid token
  3. At least one revenue parser and one extract parser have regression tests with representative fixtures asserting expected output structure
  4. All tests pass in CI (GitHub Actions) without GCP credentials or external service access
**Plans:** 2 plans

Plans:
- [x] 03-01-PLAN.md -- Auth smoke test expansion for full route coverage (TEST-01, TEST-02)
- [ ] 03-02-PLAN.md -- Parser regression tests (Extract + Revenue) and CI workflow (TEST-03)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Auth Enforcement and CORS Lockdown | 2/2 | Complete | 2026-03-11 |
| 2. Encryption Hardening | 2/2 | Complete   | 2026-03-11 |
| 3. Backend Test Suite | 1/2 | In Progress | - |
