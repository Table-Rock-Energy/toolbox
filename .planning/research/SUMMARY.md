# Project Research Summary

**Project:** Table Rock Tools v1.6 — Pipeline Fixes & Unified Enrichment
**Domain:** Internal web app enhancement — auth hardening, data pipeline UX, backend bug fixes
**Researched:** 2026-03-18
**Confidence:** HIGH

## Executive Summary

v1.6 is a focused hardening and UX improvement release with no new dependencies required. Every capability needed is achievable with the existing stack: `sse-starlette` for SSE, React 19 primitives, FastAPI `Depends()`, and the existing pipeline/preview state hooks. The work splits cleanly into two tracks: (1) backend fixes that close auth gaps, correct broken data flows, and remove a deprecated field; and (2) a single large frontend change replacing a 3-button enrichment workflow with a unified modal that chains all three steps automatically with live preview updates.

The recommended approach is sequential delivery — fix broken infrastructure first (auth hardening, RRC compound lease lookup, GHL field removal), then build the enrichment modal on top of a stable foundation. The modal is the headline feature but depends on the backend pipeline endpoints being reliable and the auth model being correct. The backend fixes are all independent of each other and independently shippable; the modal is the only piece that requires everything else to be stable first.

The key risks are concentrated in two areas: auth changes that could lock users out of the app (the `check_user` endpoint must remain unauthenticated — router-level auth on the admin router will cause a login deadlock), and the enrichment modal's state management (race conditions from double-clicks, stale closures across sequential async steps, and render thrashing). Both risks have clear prevention strategies. The auth risk has a 5-minute recovery path; the modal state issues must be designed correctly from the start.

## Key Findings

### Recommended Stack

No new dependencies. All v1.6 capabilities are met by what's already installed. See [STACK.md](STACK.md) for full details.

**Core technologies in play:**
- `sse-starlette 2.0+`: Already installed and proven in GHL bulk send — NOT recommended for pipeline modal progress (steps are 2-15s HTTP calls, not long-running jobs; sequential `await` with state updates is sufficient and simpler)
- `FastAPI Depends()`: Auth pattern already established via `require_auth` / `require_admin`. Fix is adding per-endpoint `Depends()` to unprotected GET handlers — NOT router-level
- React 19 `useState` + `useCallback`: Sufficient for modal state machine — no `zustand`, `react-query`, or `framer-motion` needed
- `useEnrichmentPipeline.ts` + `usePreviewState.ts`: Core hooks to modify — add `runAllSteps()` with a local `currentEntries` variable threading cleaned data between steps

### Expected Features

See [FEATURES.md](FEATURES.md) for full list with complexity, dependency analysis, and UX spec.

**Must have (table stakes — currently broken):**
- RRC compound lease splitting — `split_lease_number()` exists but is never called in the fetch-missing loop
- RRC direct data use — split lease results not applied directly, causing unnecessary re-lookups
- RRC per-row status feedback — `fetch_status` field exists on model but not surfaced in UI
- Admin GET endpoint auth — `GET /users`, `GET /settings/*` are unauthenticated; exposes configuration
- History user-scoping — `/api/history/jobs` returns all users' jobs; delete has no ownership check
- GHL `smart_list_name` removal — deprecated field still used in backend fallback and frontend type

**Should have (differentiators):**
- Unified enrichment modal — single "Enrich" button replaces 3-button workflow; runs cleanup -> validate -> enrich sequentially with live preview updates between steps
- Step-level progress indicator with per-step change counts
- Step-level error recovery — skip unconfigured steps, surface status per step
- Change summary on modal completion — aggregate counts by step and confidence level

**Defer:**
- Per-entry streaming progress within a step (backend doesn't support it; steps are single batch calls)
- Pipeline result persistence (preview state IS the persistence layer until export)
- User-selectable pipeline steps (3-person team; adds decision friction with no benefit)

### Architecture Approach

The architecture is additive with surgical modifications to existing components. No new backend endpoints are needed for the modal — it orchestrates the three existing pipeline endpoints from the frontend. Auth fixes use per-endpoint `Depends()` (not router-level) to preserve the `check_user` exemption. The RRC fix adds a new `lease_parser.py` utility and integrates it into `fetch_missing_rrc_data()` before the query cap check. See [ARCHITECTURE.md](ARCHITECTURE.md) for full component boundaries, state machine diagram, and implementation code sketches.

**Major components and change types:**
1. `EnrichmentModal.tsx` (NEW) — Replaces `EnrichmentToolbar.tsx`; orchestrates 3-step pipeline with step-level progress UI and accumulated review state
2. `useEnrichmentPipeline.ts` (MODIFIED) — Add `runAllSteps()` with local `currentEntries` variable threading cleaned data between steps without relying on React state timing
3. `lease_parser.py` (NEW) — Compound lease splitting with district inheritance; integrated into `fetch_missing_rrc_data()` before the query budget cap
4. Admin/History endpoints (MODIFIED) — Per-endpoint `Depends()` additions; admin bypass logic in history query
5. `BulkSendRequest` model (MODIFIED) — Two-step removal of `smart_list_name`: frontend first, then backend

### Critical Pitfalls

Top 5 from [PITFALLS-V1.6.md](PITFALLS-V1.6.md):

1. **`check_user` login deadlock** — Adding auth at the admin router level breaks the login flow entirely. Use per-endpoint `Depends()` only; `check_user` must remain unauthenticated. Test full login flow (sign out -> sign in) after every admin auth change.

2. **Enrichment modal race condition** — Double-click or modal reopen starts concurrent pipeline requests against the same preview state. Prevent with `AbortController` per run and hard-disabling the trigger button while the modal is open.

3. **Stale closure in `runAllSteps()`** — React state doesn't update synchronously between `await` calls. Using `previewEntries` from the hook closure in step 2 means step 2 sees pre-step-1 data. Fix: maintain a local `currentEntries` variable inside `runAllSteps()` and pass it explicitly between steps.

4. **Compound lease district inheritance** — `"02-12345/12346"` splits into `["02-12345", "12346"]`; the second part loses its district prefix. Must propagate district from the first part. Also: expand compound leases BEFORE the `MAX_INDIVIDUAL_QUERIES` cap check, not inside the loop.

5. **`smart_list_name` two-step removal** — Removing from the backend model first causes 422 errors on cached frontends (Pydantic strict mode rejects unknown fields). Remove from frontend first, keep backend field accepted-but-unused for one deploy cycle, then remove backend field.

## Implications for Roadmap

### Phase 1: Backend Fixes & Security Hardening

**Rationale:** All items are independent of each other and of the enrichment modal. Low-risk, mostly backend-only (GHL has a frontend type component). Closes active security gaps. Should ship before any user-facing feature work so the modal builds on correct infrastructure.
**Delivers:** Authenticated admin settings, user-scoped job history with admin bypass, clean GHL model without deprecated field, correct RRC compound lease lookups with per-row status feedback.
**Addresses:** Admin GET auth, history user-scoping + delete ownership, GHL `smart_list_name`, RRC compound lease splitting + direct data use + status feedback.
**Avoids:** check_user deadlock (Pitfall 2), admin visibility loss (Pitfall 3), 422 from cached frontend (Pitfall 5), compound lease budget exhaustion (Pitfall 9).
**Effort:** ~4.5h total (0.5h GHL + 1h admin auth + 1h history + 2h RRC).

### Phase 2: Unified Enrichment Modal

**Rationale:** Largest frontend change — touches all four tool pages. Benefits from stable backend pipeline and correct auth. The modal's `runAllSteps()` stale closure fix and `AbortController` race condition prevention must be designed upfront; they cannot be added after the fact.
**Delivers:** Single "Enrich" button replacing the 3-button toolbar; 3-step progress modal with live table updates between steps; accumulated change review on completion; step-level error recovery for unconfigured services.
**Uses:** Existing `useEnrichmentPipeline`, `usePreviewState.updateEntries()`, `pipelineApi` (3 existing endpoints), `Modal.tsx` pattern, Tailwind `transition-colors` for cell highlighting.
**Implements:** `EnrichmentModal.tsx` (new), `useEnrichmentPipeline.runAllSteps()` (modified), removes `EnrichmentToolbar.tsx`.
**Avoids:** Race condition (Pitfall 1), render thrashing (Pitfall 6), cross-page state leakage (Pitfall 8), pipeline timeout UX (Pitfall 12).
**Effort:** ~4h.

### Phase Ordering Rationale

- Phase 1 before Phase 2: auth and data correctness must be stable before building modal UX on top. The modal calls pipeline endpoints; those must return user-scoped, correct data.
- GHL cleanup first within Phase 1: lowest risk, zero dependencies, two-step removal is straightforward.
- Admin auth before history scoping: both use the same `require_auth` pattern; doing admin first confirms the pattern works correctly.
- RRC last in Phase 1: most logic complexity (compound splitting, district inheritance, cap ordering) and a new utility file — isolating it reduces blast radius.
- Enrichment modal last: touches 4 pages, has the most integration surface, benefits from all other work being stable.

### Research Flags

Phases with standard patterns — no additional research needed:
- **Phase 1 (GHL cleanup):** Pydantic field deprecation is well-documented; two-step removal pattern is standard.
- **Phase 1 (admin auth):** FastAPI `Depends()` per-endpoint pattern is documented and already used in this codebase.
- **Phase 1 (history scoping):** Firestore query filtering plus conditional admin bypass is a simple pattern.

Areas requiring care during implementation (not formal research, but upfront design):
- **Phase 1 (RRC compound leases):** District inheritance logic needs testing with real compound lease CSV data before shipping. The `split_lease_number` function has never been called in production — verify its actual behavior on edge cases (`"02-12345/12346"`, `"12345/12346"`, mixed separators).
- **Phase 2 (enrichment modal):** The `runAllSteps()` stale closure fix is non-obvious. The `AbortController` integration needs verification that the existing `ApiClient` fetch wrapper can propagate the signal. Component boundary decision (per-page vs. shared with key) must be made before implementation begins.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Codebase-verified — all deps confirmed installed; no new packages needed |
| Features | HIGH | All features based on direct codebase analysis of gaps, broken endpoints, and existing implementations |
| Architecture | HIGH | Code sketches verified against actual function signatures, patterns, and router configs in codebase |
| Pitfalls | HIGH | All pitfalls identified from direct codebase inspection (line numbers cited); not hypothetical |

**Overall confidence:** HIGH

### Gaps to Address

- **`split_lease_number` edge case behavior:** Function exists but has no confirmed test coverage for district inheritance edge cases. Test with real compound lease data before shipping Phase 1 RRC work.
- **`ApiClient` AbortController support:** Verify the existing fetch wrapper in `utils/api.ts` can accept and propagate an `AbortController` signal. If not, a small wrapper update is needed before the modal's race condition prevention will work.
- **Admin settings GET auth level:** Research recommends `require_auth` (any authenticated user) for GET settings endpoints. Verify the Settings page is accessible to non-admin users — if admin-only, bump those specific endpoints to `require_admin`.

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `backend/app/main.py` lines 72-86 — admin router confirmed mounted without auth dependencies
- `backend/app/api/admin.py` lines 280, 290, 393, 411, 475, 535 — GET handlers confirmed lacking auth
- `backend/app/api/history.py` — no `user_id` filtering confirmed; `delete_job` has no ownership check
- `backend/app/api/ghl.py` line 343 — `smart_list_name` fallback usage confirmed active
- `backend/app/api/proration.py` lines 343-472 — `fetch_missing_rrc_data()` confirms `split_lease_number` defined but uncalled in main loop
- `backend/app/models/proration.py` — `MineralHolderRow.fetch_status` field confirmed on model
- `frontend/src/hooks/useEnrichmentPipeline.ts` (307 lines) — sequential `runStep` pattern confirmed
- `frontend/src/hooks/usePreviewState.ts` — `updateEntries()` and `recentlyAppliedKeys` confirmed
- `frontend/src/components/EnrichmentToolbar.tsx` (77 lines) — 3-button UI confirmed for replacement
- `requirements.txt` — `sse-starlette>=2.0` confirmed installed; no new deps needed
- `package.json` — no additional frontend deps needed confirmed

---
*Research completed: 2026-03-18*
*Ready for roadmap: yes*
