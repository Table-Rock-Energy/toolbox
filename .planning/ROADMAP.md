# Roadmap: Table Rock Tools

## Milestones

- ✅ **v1.3 Security Hardening** -- Phases 1-3 (shipped 2026-03-11)
- ✅ **v1.4 ECF Extraction** -- Phases 1-4 (shipped 2026-03-12)
- ✅ **v1.5 Enrichment Pipeline & Bug Fixes** -- Phases 5-9 (shipped 2026-03-17)
- ✅ **v1.6 Pipeline Fixes & Unified Enrichment** -- Phases 10-12 (shipped 2026-03-19)
- ✅ **v1.7 Batch Processing & Resilience** -- Phases 13-17 (shipped 2026-03-20)
- ✅ **v1.8 Preview System Overhaul** -- Phases 18-21 (shipped 2026-03-24)
- ✅ **v2.0 Full On-Prem Migration** -- Phases 22-27 (shipped 2026-03-25)
- ✅ **v2.1 Security Headers & Cleanup** -- Phases 28-29 (shipped 2026-03-27)

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

<details>
<summary>v2.1 Security Headers & Cleanup (Phases 28-29) -- SHIPPED 2026-03-27</summary>

- [x] Phase 28: Security Headers Middleware (1/1 plan) -- completed 2026-03-27
- [x] Phase 29: Firebase & Config Cleanup (1/1 plan) -- completed 2026-03-27

See: `.planning/milestones/v2.1-ROADMAP.md` for full details

</details>

### v2.2 Post-Migration Fixes & AI Enrichment (In Progress)

**Milestone Goal:** Stabilize the on-prem migration by consolidating ad-hoc bug fixes and getting AI enrichment working end-to-end with LM Studio on the server.

- [x] **Phase 30: Bug Fix Consolidation** - Retroactively track 5 ad-hoc production fixes shipped during migration
- [ ] **Phase 31: Docker + LM Studio Connectivity** - Backend can reach LM Studio from inside Docker container and run AI inference
- [ ] **Phase 32: Nginx Proxy Configuration** - Reverse proxy handles long-running AI and streaming requests without timeouts

## Phase Details

### Phase 30: Bug Fix Consolidation
**Goal**: All ad-hoc production fixes from the v2.0 migration are tracked and accounted for
**Depends on**: Nothing (retroactive bookkeeping)
**Requirements**: BUGFIX-01, BUGFIX-02, BUGFIX-03, BUGFIX-04, BUGFIX-05
**Success Criteria** (what must be TRUE):
  1. Revenue check_amount values persist correctly as floats in PostgreSQL (no Decimal serialization errors)
  2. Admin user creation succeeds without import errors on password hashing
  3. Job records store the user's UUID (not email string) as the owner reference
  4. GHL-prep tool filtering produces correct filtered results
  5. RRC proration data is queryable from PostgreSQL with model filesystem discovery working
**Plans**: 0 (all fixes already shipped)
**Status**: Complete (pre-shipped as ad-hoc fixes)

### Phase 31: Docker + LM Studio Connectivity
**Goal**: AI enrichment pipeline works end-to-end from inside the Docker container using LM Studio running on the host
**Depends on**: Phase 30
**Requirements**: DOCKER-01, DOCKER-02, DOCKER-03
**Success Criteria** (what must be TRUE):
  1. Backend container can reach LM Studio at `host.docker.internal:1234` via `--add-host` flag in docker-compose
  2. Backend verifies the configured model ID exists in LM Studio's `/v1/models` response before making inference calls
  3. User can upload a file, click Enrich, and receive AI-processed results on the server (full pipeline: upload -> enrich -> results)
**Plans**: TBD

### Phase 32: Nginx Proxy Configuration
**Goal**: Nginx reverse proxy correctly handles long-running AI inference and streaming responses
**Depends on**: Phase 31
**Requirements**: NGINX-01, NGINX-02
**Success Criteria** (what must be TRUE):
  1. AI enrichment requests to `/api/pipeline/` complete without 504 timeout (600s proxy timeout configured)
  2. Revenue NDJSON streaming responses to `/api/revenue/` deliver progress updates in real-time (proxy buffering disabled)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 30. Bug Fix Consolidation | v2.2 | 0/0 | Complete | 2026-03-31 |
| 31. Docker + LM Studio Connectivity | v2.2 | 0/? | Not started | - |
| 32. Nginx Proxy Configuration | v2.2 | 0/? | Not started | - |
