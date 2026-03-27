# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- ✅ **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (shipped 2026-03-19)
- ✅ **v1.7 Batch Processing & Resilience** -- Phases 13-17 (shipped 2026-03-20)
- ✅ **v1.8 Preview System Overhaul** -- Phases 18-21 (shipped 2026-03-24)
- ✅ **v2.0 Full On-Prem Migration** -- Phases 22-27 (shipped 2026-03-25)
- [ ] **v2.1 Security Headers & Cleanup** -- Phases 28-29

## Phases

<details>
<summary>v1.3 Security Hardening (Phases 1-3) -- SHIPPED 2026-03-11</summary>

- [x] Phase 1: Auth Enforcement & CORS Lockdown (2/2 plans) -- completed 2026-03-11
- [x] Phase 2: Encryption Hardening (2/2 plans) -- completed 2026-03-11
- [x] Phase 3: Backend Test Suite (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.3-ROADMAP.md` for full details

</details>

<details>
<summary>v1.4 ECF Extraction (Phases 1-4) -- SHIPPED 2026-03-12</summary>

- [x] Phase 1: ECF PDF Parsing (2/2 plans) -- completed 2026-03-12
- [x] Phase 2: Convey 640 Processing (1/1 plan) -- completed 2026-03-12
- [x] Phase 3: Merge and Export (2/2 plans) -- completed 2026-03-12
- [x] Phase 4: Frontend Integration (2/2 plans) -- completed 2026-03-11

See: `.planning/milestones/v1.4-ROADMAP.md` for full details

</details>

<details>
<summary>v1.5 Enrichment Pipeline & Bug Fixes (Phases 5-9) -- SHIPPED 2026-03-17</summary>

- [x] Phase 5: ECF Upload Flow Fix (2/2 plans) -- completed 2026-03-14
- [x] Phase 6: RRC & GHL Fixes (2/2 plans) -- completed 2026-03-14
- [x] Phase 7: Enrichment UI & Preview State (3/3 plans) -- completed 2026-03-15
- [x] Phase 8: Enrichment Pipeline Features (3/3 plans) -- completed 2026-03-16
- [x] Phase 9: Tool-Specific AI Prompts (2/2 plans) -- completed 2026-03-17

See: `.planning/milestones/v1.5-ROADMAP.md` for full details

</details>

<details>
<summary>v1.6 Pipeline Fixes & Unified Enrichment (Phases 10-12) -- SHIPPED 2026-03-19</summary>

- [x] Phase 10: Auth Hardening & GHL Cleanup (3/3 plans) -- completed 2026-03-19
- [x] Phase 11: RRC Pipeline Fix (1/1 plan) -- completed 2026-03-18
- [x] Phase 12: Unified Enrichment Modal (2/2 plans) -- completed 2026-03-19

See: `.planning/milestones/v1.6-ROADMAP.md` for full details

</details>

<details>
<summary>v1.7 Batch Processing & Resilience (Phases 13-17) -- SHIPPED 2026-03-20</summary>

- [x] Phase 13: Operation Context & Batch Engine (2/2 plans) -- completed 2026-03-19
- [x] Phase 14: AI Cleanup Batching (2/2 plans) -- completed 2026-03-19
- [x] Phase 15: Operation Persistence UI (1/1 plan) -- completed 2026-03-20
- [x] Phase 16: Revenue Multi-PDF Streaming (2/2 plans) -- completed 2026-03-20
- [x] Phase 17: Proration Performance (2/2 plans) -- completed 2026-03-20

See: `.planning/milestones/v1.7-ROADMAP.md` for full details

</details>

<details>
<summary>v1.8 Preview System Overhaul (Phases 18-21) -- SHIPPED 2026-03-24</summary>

- [x] Phase 18: Key-Based Highlight Tracking -- completed 2026-03-24
- [x] Phase 19: Filter Correctness -- completed 2026-03-24
- [x] Phase 20: Preview UX Refinements -- completed 2026-03-24
- [x] Phase 21: Proration Enhancements -- completed 2026-03-24

See: `.planning/milestones/v1.8-ROADMAP.md` for full details

</details>

<details>
<summary>v2.0 Full On-Prem Migration (Phases 22-27) -- SHIPPED 2026-03-25</summary>

- [x] Phase 22: Database Models & Schema (2/2 plans) -- completed 2026-03-25
- [x] Phase 23: Auth Backend (2/2 plans) -- completed 2026-03-25
- [x] Phase 24: Auth Frontend & Firebase Removal (2/2 plans) -- completed 2026-03-25
- [x] Phase 25: Database Service Port (3/3 plans) -- completed 2026-03-25
- [x] Phase 26: AI Provider Swap (2/2 plans) -- completed 2026-03-25
- [x] Phase 27: Storage & Dependency Cleanup (2/2 plans) -- completed 2026-03-25

See: `.planning/milestones/v2.0-ROADMAP.md` for full details

</details>

**v2.1 Security Headers & Cleanup (Phases 28-29)**

- [x] **Phase 28: Security Headers Middleware** - Add all 6 security headers via FastAPI middleware with test coverage (completed 2026-03-27)
- [ ] **Phase 29: Firebase & Config Cleanup** - Remove dead Dockerfile Firebase ARGs and extract admin email to env var

## Phase Details

### Phase 28: Security Headers Middleware
**Goal**: Every API response includes security headers that satisfy the BrandPod scan findings
**Depends on**: Nothing (first phase of v2.1)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, TEST-01
**Success Criteria** (what must be TRUE):
  1. `curl -I https://tools.tablerocktx.com/api/health` returns all 6 security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) with correct values
  2. CSP header allows self, Google Fonts (fonts.googleapis.com, fonts.gstatic.com), and inline styles needed by React -- blocks all other script/style/font sources
  3. HSTS header has max-age of at least 31536000 (1 year) with includeSubDomains directive
  4. Permissions-Policy restricts camera, microphone, and geolocation to none
  5. Pytest tests assert all 6 headers present with expected values on a test client response -- tests pass in CI
**Plans**: 1 plan
Plans:
- [x] 28-01-PLAN.md -- SecurityHeadersMiddleware + pytest tests for all 6 headers

### Phase 29: Firebase & Config Cleanup
**Goal**: Dead Firebase references removed from Dockerfile and hardcoded admin email extracted to configuration
**Depends on**: Nothing (independent of Phase 28)
**Requirements**: CLEAN-02, CLEAN-03
**Success Criteria** (what must be TRUE):
  1. `grep -r VITE_FIREBASE Dockerfile` returns zero matches -- no VITE_FIREBASE_* ARGs or ENV references remain
  2. `grep -rn "james@tablerocktx.com" backend/` returns zero matches in auth.py and admin.py -- all references use `settings.default_admin_email` or `DEFAULT_ADMIN_EMAIL` env var
  3. App starts correctly with DEFAULT_ADMIN_EMAIL unset (falls back to james@tablerocktx.com as default in config.py)
**Plans**: TBD

## Progress

**Execution Order:**
Phases 28 -> 29
(Phase 29 can run in parallel with 28 since they are independent)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 22. Database Models & Schema | v2.0 | 2/2 | Complete | 2026-03-25 |
| 23. Auth Backend | v2.0 | 2/2 | Complete | 2026-03-25 |
| 24. Auth Frontend & Firebase Removal | v2.0 | 2/2 | Complete | 2026-03-25 |
| 25. Database Service Port | v2.0 | 3/3 | Complete | 2026-03-25 |
| 26. AI Provider Swap | v2.0 | 2/2 | Complete | 2026-03-25 |
| 27. Storage & Dependency Cleanup | v2.0 | 2/2 | Complete | 2026-03-25 |
| 28. Security Headers Middleware | v2.1 | 1/1 | Complete    | 2026-03-27 |
| 29. Firebase & Config Cleanup | v2.1 | 0/0 | Not started | - |
