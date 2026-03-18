# Feature Landscape

**Domain:** v1.6 Pipeline Fixes & Unified Enrichment
**Researched:** 2026-03-18

## Table Stakes

Features that are broken or incomplete in the current build. Fixing these is prerequisite work, not optional.

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| RRC compound lease splitting | Users enter "08-12345/12346" as a single lease field. `split_lease_number()` exists but isn't wired into the `fetch_missing_rrc_data` loop -- each compound value queries as-is and fails | Low | Existing `split_lease_number()` in proration.py line 41 |
| RRC direct data use (skip Firestore re-lookup) | After individual HTML scrape, compound split leases may still re-query Firestore. The RRC-01 fix (line 445) handles simple leases but compound splits need the same treatment | Low | fetch_missing endpoint, compound splitting |
| RRC per-row status feedback | `fetch_status` field exists on `MineralHolderRow` model but frontend doesn't surface it. User can't tell which rows matched, failed, or were never queried | Low | `MineralHolderRow.fetch_status` field already on model |
| Admin GET endpoint auth | `get_gemini_settings`, `get_google_cloud_settings`, `get_google_maps_settings`, and `get_users` lack `require_admin` dependency. Any authenticated user can read API keys (masked but still config leak) | Low | `require_admin` already imported and used on write endpoints |
| History user-scoping | `/api/history/jobs` returns ALL users' jobs with no `user_id` filter. `delete_job` has no ownership check -- any user can delete any job | Med | `require_auth` already on router (main.py:81), need to extract user_id and pass to Firestore query |
| GHL `smart_list_name` removal | Deprecated field in model (explicit docstring says "Use campaign_tag instead") but still used in `ghl.py` send logic (line 343) and frontend type (api.ts:457) | Low | 6 code files reference it; 13 refs are in old planning docs |

## Differentiators

The unified enrichment modal is the headline feature. It replaces a 3-button + review panel workflow with a single-click automated flow.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| **Unified enrichment modal** | Replace 3 separate buttons + confirmation dialogs + ProposedChangesPanel flow with single "Enrich" button that opens a modal, runs all enabled steps sequentially, shows real-time progress, and streams changes to table | High | Replaces EnrichmentToolbar; refactors useEnrichmentPipeline; new EnrichmentModal component |
| Sequential step execution with progress | Modal runs cleanup -> validate -> enrich as a single flow. Each step shows: step name, progress indicator, running count of changes found | Med | State machine inside modal or refactored useEnrichmentPipeline |
| Live preview updates during pipeline | As each step completes, high-confidence changes auto-apply to the table behind the modal. User sees rows highlight green in real-time | Med | Existing `updateEntries` + `recentlyAppliedKeys` pattern already supports this |
| Time estimate per step | "~30s remaining" based on entry count. Cleanup is LLM-bound (~2s/entry), validate is Google Maps-bound (~0.5s/entry), enrich is PDL-bound (~1s/entry) | Low | Static multipliers based on entry count, no server-side timing needed |
| Step-level error recovery | If validate fails (no API key configured), modal skips to enrich instead of aborting entire flow. Shows which steps succeeded vs failed | Med | Error handling per step in sequential runner |
| Change summary on completion | After all steps complete, modal shows: "12 names corrected, 8 addresses validated, 5 phones found" with breakdown by source and confidence | Low | Aggregate counts from ProposedChange arrays returned by each step |

## Anti-Features

Features to explicitly NOT build for v1.6.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| SSE/WebSocket for pipeline progress | Pipeline steps are HTTP POST calls that take 5-30s each. Not long-running jobs. The existing `useSSEProgress` pattern is for GHL bulk send (minutes), not pipeline steps (seconds) | Keep existing async/await per step. Show progress via state updates between steps |
| Granular per-entry progress within a step | Backend processes all entries in one API call (LLM batch, Maps batch). No per-entry streaming exists in pipeline.py | Show step-level progress (1/3, 2/3, 3/3), not entry-level |
| User-selectable pipeline steps in modal | "Choose which steps to run" checkbox UI adds decision friction for a 3-person team | Run all enabled steps automatically. Skip disabled ones (no API key) silently |
| Undo individual auto-applied changes | Current undo restores entire pre-snapshot. Per-change undo requires field-level undo stack | Keep existing bulk undo via `preAutoApplySnapshot` pattern |
| RRC background county download progress | Already runs in background thread via `rrc_background.py`. Adding progress tracking adds complexity with minimal user value | Keep fire-and-forget background county refresh |
| Pipeline result caching/persistence | Enrichment results are ephemeral -- they modify preview state, which gets exported. No need to persist intermediate pipeline state to Firestore | Preview state IS the persistence layer (until export) |
| New backend endpoints for unified modal | The 3 existing pipeline endpoints (cleanup/validate/enrich) work fine. The modal just calls them sequentially from the frontend | No backend changes for the modal feature |

## Feature Dependencies

```
Admin GET auth hardening       (independent, no deps)
History user-scoping           (independent, needs user_id from require_auth)
GHL smart_list_name removal    (independent, no deps)

RRC compound lease splitting  --> RRC direct data use (splitting feeds into lookup loop)
RRC direct data use           --> RRC per-row status feedback (status only meaningful with correct lookups)

Unified enrichment modal      --> Sequential step execution (modal IS the step runner)
Sequential step execution     --> Live preview updates (updates happen between steps)
Sequential step execution     --> Step-level error recovery (recovery happens between steps)
Live preview updates          --> Change summary in modal (summary aggregates all step results)
Time estimate per step            (independent, cosmetic, wire in after modal works)
```

## MVP Recommendation

**Phase 1 -- Fix broken things (no UX changes):**
1. Admin GET endpoint auth (add `Depends(require_admin)` to 4 GET handlers)
2. History user-scoping (filter by `user_id` from auth token, ownership check on delete)
3. GHL `smart_list_name` removal (delete from model, API fallback logic, frontend type)
4. RRC compound lease splitting (wire `split_lease_number` into fetch-missing loop, iterate results)
5. RRC direct data use (ensure split lease results use fetched data directly)
6. RRC per-row status feedback (surface `fetch_status` in Proration.tsx table)

**Phase 2 -- Unified enrichment modal:**
1. New `EnrichmentModal` component (modal shell with step indicator)
2. Sequential pipeline runner (refactor `useEnrichmentPipeline` to auto-chain enabled steps)
3. Progress UI: 3-step indicator + time estimate + change count per step
4. Live preview: auto-apply high-confidence changes between steps (existing pattern)
5. Change summary on completion
6. Error recovery: skip failed steps, continue to next, show status per step
7. Remove `EnrichmentToolbar` 3-button UI, replace with single "Enrich" trigger

**Defer:**
- Per-entry progress within pipeline steps (backend doesn't support streaming)
- Pipeline result persistence (unnecessary for internal tool)

## Existing Code to Reuse

| Component/Hook | Current Role | v1.6 Role |
|----------------|-------------|-----------|
| `useEnrichmentPipeline` | Manages 3 independent buttons, tracks completed steps, auto-applies high-confidence | Core logic stays. Refactor `runStep` to chain automatically instead of user-triggered |
| `usePreviewState.updateEntries` | Updates table data from enrichment callbacks | Same -- modal calls this between steps for live preview |
| `ProposedChangesPanel` | Shows changes for review after each step | Replaced by in-modal summary. Keep for post-modal review of remaining low-confidence changes |
| `EnrichmentToolbar` | 3 buttons (Clean Up, Validate, Enrich) | Replaced entirely by single "Enrich" button |
| `ProposedChangeCell` | Inline diff rendering in table cells | Keep as-is for live preview highlighting during modal run |
| `AutoCorrectionsBanner` | Shows auto-applied high-confidence changes count | Move into modal's completion summary |
| `pipelineApi` (cleanup/validate/enrich) | HTTP calls to 3 backend endpoints | No change -- modal calls same endpoints sequentially |
| `recentlyAppliedKeys` + green highlight | 2-second green flash on applied rows | Keep as-is, trigger between steps |

## Unified Enrichment Modal UX Spec

**Trigger:** Single "Enrich" button in toolbar area (replaces 3 buttons). Styled like current `cleanUpEnabled` button (gradient teal).

**Modal states:**

1. **Ready:** Shows which steps will run based on feature flags/API keys. Example: "AI Cleanup (enabled), Address Validation (enabled), Contact Enrichment (not configured)". Entry count. "Start Enrichment" button.

2. **Running:** Vertical step list with current step highlighted. Each step shows:
   - Step name + icon (Wand2 for cleanup, MapPin for validate, Search for enrich)
   - Status: pending (gray), running (spinner), complete (green check), failed (red X), skipped (gray dash)
   - When complete: "4 changes found" or "No changes"
   - Time estimate for current step: "~{entryCount * multiplier}s remaining"

3. **Complete:** All steps show final status. Summary card: "18 changes applied automatically, 3 changes need review". "Close" button. Table behind modal already shows green highlights on auto-applied rows.

4. **Partial failure:** Failed step shows error inline (e.g., "Google Maps API key not configured"). Other steps still complete. User gets partial results.

**Auto-apply behavior (carried forward from existing `useEnrichmentPipeline`):**
- Cleanup: high-confidence changes auto-apply immediately. Medium/low queue for review.
- Validate: authoritative (Google Maps) changes auto-apply.
- Enrich: phone/email changes queue for review (additive data, user should confirm).

**After modal closes:** If any changes need review, show `ProposedChangesSummary` bar (existing component) in the toolbar area with remaining unapplied changes. User reviews and applies/dismisses as today.

## Sources

- Codebase analysis: `useEnrichmentPipeline.ts` (307 lines), `EnrichmentToolbar.tsx` (77 lines), `ProposedChangesPanel.tsx` (241 lines), `pipeline.py` (366 lines), `proration.py` fetch-missing endpoint (lines 343-472)
- Existing patterns: `useSSEProgress.ts` (SSE progress model), `usePreviewState.ts` (entry update + highlight model)
- Project context: `.planning/PROJECT.md` v1.6 milestone definition
- Admin auth gaps: `admin.py` GET handlers at lines 280, 290, 393, 411, 475, 535 lack `require_admin`
- History gaps: `history.py` has no user filtering, router-level `require_auth` only verifies token
- GHL legacy: `ghl.py` line 343 uses `campaign_tag`, line 343 falls back to `smart_list_name`
