# Project Research Summary

**Project:** Table Rock Tools v1.5 — Enrichment Pipeline & Bug Fixes
**Domain:** Internal document-processing tools with post-processing enrichment
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

v1.5 is a wiring and bug-fix release, not a greenfield effort. All required libraries, services, and backend infrastructure already exist in the codebase. The work is connecting existing backend services (Gemini AI, Google Maps address validation, PDL/SearchBug enrichment) to tool page frontends that currently lack those integrations, and fixing data flow bugs where enrichment results never propagate back to the preview table. No new dependencies are needed. Two new API endpoints are required (address validation batch, service status), and three thin `/enrich` wrappers need adding to existing tool routers.

The recommended approach is to fix standalone bugs first (ECF upload flow, RRC fetch-missing), then build the universal enrichment UI. The GHL "smart list" feature is not a code fix but a UX clarification -- GHL SmartLists are filter-based saved views, not API-creatable objects. The field should be renamed from "SmartList Name" to "Campaign Tag" with help text explaining the manual SmartList creation workflow in GHL's UI.

The primary risk is **concurrent enrichment operations corrupting shared state**. The universal 3-button enrichment UI (Validate / Clean Up / Enrich) must enforce serial execution -- if two buttons are clicked simultaneously, the last to complete silently overwrites the other's results. A version-counter on the entries array and button-disabling during active operations are the minimum safeguards. Secondary risk is the enrichment service's sequential processing of 50+ persons without progress feedback, which will appear hung on larger datasets.

## Key Findings

### Recommended Stack

No new packages, libraries, or environment variables are needed. Every v1.5 feature uses existing infrastructure.

**Core technologies (all already installed):**
- **Gemini AI** (`google-genai`, model `gemini-2.5-flash`): Powers "Clean Up" button via existing `TOOL_PROMPTS` with per-tool QA prompts. Structured JSON output already configured.
- **Google Maps Geocoding API** (`requests`-based): Powers "Validate" button via existing `address_validation_service.py` with batch support at 40 QPS. Only needs an API endpoint wrapper.
- **PDL + SearchBug** (`enrichment_service.py`): Powers "Enrich" button for contact data enrichment. Exists but needs frontend wiring and progress feedback.
- **React + useState**: Sufficient for preview state management. No Redux/Zustand needed.

**New endpoints required (2):**
- `POST /api/validate/addresses` -- wraps existing `validate_addresses_batch()`
- `GET /api/services/status` -- aggregates feature flag status for conditional button rendering

**New thin endpoints (3):**
- `POST /api/title/enrich`, `POST /api/proration/enrich`, `POST /api/revenue/enrich` -- 3-line delegates to existing `data_enrichment_pipeline.enrich_entries()`

### Expected Features

**Must have (table stakes -- product feels broken without these):**
- **Preview updates after enrichment** -- Validate/Cleanup buttons exist but results never update the preview table. Core data flow bug across all tools.
- **ECF upload: explicit Process button** -- ECF auto-processes on PDF upload before user can add CSV. Confusing UX that actively harms the workflow.
- **RRC fetch-missing returns usable data** -- Endpoint queries RRC but results don't surface to user. Multi-lease parsing broken.
- **GHL smart list clarification** -- "SmartList Name" field does nothing. Rename to "Campaign Tag" with workflow documentation.

**Should have (differentiators):**
- **Universal 3-button enrichment bar** -- Validate / Clean Up / Enrich as conditional buttons across all tool pages, gated by API key availability.
- **Tool-specific Gemini QA prompt refinement** -- Existing prompts work but can be sharpened per tool.
- **Multi-step enrichment progress modal** -- `EnrichmentProgress.tsx` exists but is only partially wired.
- **RRC multi-lease parsing** -- Handle combined lease numbers like "02-12345/02-12346".

**Defer (v2+):**
- Enrichment result caching (don't re-enrich already-enriched entries)
- Enrichment history/audit trail
- Direct SmartList API creation (not how GHL SmartLists work)
- Real-time SSE streaming for enrichment (overkill for current batch sizes)
- Auto-enrichment on upload (users need to see raw data first)

### Architecture Approach

v1.5 follows the existing tool-per-module pattern. The only net-new frontend code is a shared `usePostProcess` hook extracted from Extract.tsx's existing enrichment logic. Backend changes are thin wiring -- per-tool `/enrich` endpoints delegate to the existing `data_enrichment_pipeline.enrich_entries()` orchestrator, which already handles tool-specific logic via `FIELD_MAPS` and conditional step execution. The key architectural rule: entries live in frontend state only (no Firestore persistence of intermediate enrichment results), and each enrichment step takes current entries as input and produces updated entries as output in a serial pipeline.

**Major components (modified, not new):**
1. **`data_enrichment_pipeline.py`** -- Add `FIELD_MAPS` for proration and revenue tools
2. **`hooks/usePostProcess.ts`** (NEW) -- Shared hook encapsulating NDJSON streaming, progress tracking, entry state replacement
3. **Per-tool pages** (Extract, Title, Proration, Revenue) -- Add conditional enrichment buttons using shared hook
4. **`api/proration.py`** -- Fix fetch-missing to use returned data directly instead of Firestore re-lookup
5. **`GhlSendModal.tsx`** -- Rename SmartList field, add help text

### Critical Pitfalls

1. **Concurrent enrichment button clicks cause race condition** -- Two simultaneous operations overwrite each other's results. Fix: disable all buttons during active operation, enforce serial pipeline with version counter.
2. **Preview state goes stale after async enrichment** -- AI suggestions reference stale entry indices if entries were modified by a prior step. Fix: version-stamp entries, reject suggestions from outdated versions.
3. **Enrichment service processes sequentially without progress** -- 50 persons at ~2s each = 100+ seconds with no feedback. Fix: add per-person progress events, cap batch at 25, consider parallel execution with semaphore.
4. **GHL SmartLists are not API-creatable** -- The field exists but does nothing. Fix: rename to "Campaign Tag", document manual SmartList creation workflow.
5. **RRC HTML parsing breaks on website layout changes** -- Positional column indexing is fragile. Fix: add header row validation before deploying multi-lease lookups.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: ECF Upload Flow Fix
**Rationale:** Lowest complexity, zero backend changes, immediate UX improvement. Self-contained in Extract.tsx.
**Delivers:** Explicit Process button for ECF uploads; standard OCC format unchanged.
**Addresses:** ECF upload table-stakes bug
**Avoids:** Auto-processing without confirmation (Pitfall #8)
**Complexity:** LOW

### Phase 2: RRC Fetch-Missing Repair
**Rationale:** Fixes an existing broken endpoint. Backend parsing bug is small; frontend state merge follows patterns established elsewhere.
**Delivers:** Multi-lease parsing, direct use of fetch results (no Firestore re-lookup race), results surfaced in Proration preview.
**Addresses:** RRC fetch-missing table-stakes bug, multi-lease parsing differentiator
**Avoids:** Session state leakage (Pitfall #7), HTML parsing fragility (Pitfall #6)
**Complexity:** MEDIUM

### Phase 3: GHL Smart List Clarification
**Rationale:** Independent of other phases. Low complexity UX fix that removes user confusion. Can run in parallel with Phases 1-2.
**Delivers:** Renamed "Campaign Tag" field, help text explaining tag-based SmartList workflow, post-send instructions.
**Addresses:** GHL smart list table-stakes bug
**Avoids:** Building impossible API integration (Pitfall #2)
**Complexity:** LOW

### Phase 4: Universal Enrichment UI + Preview Updates
**Rationale:** Largest scope, depends on understanding Extract.tsx patterns from Phase 1. This is the core v1.5 feature. Preview updates and the 3-button UI are inseparable -- buttons without preview updates are useless.
**Delivers:** Validate/CleanUp/Enrich buttons on all tool pages, conditional visibility by API key, shared `usePostProcess` hook, entry state replacement after each step, undo capability.
**Addresses:** Preview update table-stakes bug, universal enrichment bar differentiator, progress modal
**Avoids:** Race conditions (Pitfall #4), stale preview state (Pitfall #1), sequential processing without progress (Pitfall #3)
**Complexity:** HIGH (but using established patterns from Extract.tsx)

### Phase 5: Gemini QA Prompt Refinement
**Rationale:** Low-risk prompt engineering. Can be done anytime after Phase 4 establishes the universal Clean Up button.
**Delivers:** Sharpened per-tool validation and cleanup prompts, partial validation warning banner.
**Addresses:** Tool-specific Gemini prompts differentiator
**Avoids:** Partial validation looking like success (Pitfall #5)
**Complexity:** LOW

### Phase Ordering Rationale

- **Phases 1-3 are independent** -- can be built in parallel or any order. All are bug fixes or UX clarifications with no cross-dependencies.
- **Phase 4 is the core feature work** -- depends on familiarity with Extract.tsx patterns (gained in Phase 1) and must solve the state management pitfalls before any enrichment buttons ship.
- **Phase 5 is polish** -- prompt text changes only, no structural risk. Natural follow-on after Phase 4 proves the enrichment pipeline works.
- **Grouping logic:** Bug fixes first (quick wins, user-facing improvements), then feature work (universal enrichment), then refinement (prompts).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (GHL):** Verify current GHL API v2 documentation for smart list/saved search endpoints. Prior research is from Feb 2026; API may have changed. Check `https://highlevel.stoplight.io/docs/integrations`.
- **Phase 4 (Universal Enrichment):** The state management pattern (version counter, serial pipeline, undo snapshots) needs careful design. Research Extract.tsx's existing implementation thoroughly before generalizing.

Phases with standard patterns (skip research-phase):
- **Phase 1 (ECF Fix):** Pure frontend state change. Pattern is well-understood.
- **Phase 2 (RRC Fix):** Bug fix with known root cause (Firestore re-lookup race). Code changes are targeted.
- **Phase 5 (Prompts):** Prompt engineering. No architectural decisions needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies. All libraries verified as installed and functional in codebase. |
| Features | MEDIUM | Web search unavailable; feature scope based on codebase analysis and prior research. GHL SmartList limitation needs re-verification against current API docs. |
| Architecture | HIGH | Based on direct codebase analysis. All proposed patterns extend existing, working implementations. |
| Pitfalls | HIGH | All critical pitfalls identified from actual code paths. Race condition and stale state issues are deterministic bugs, not edge cases. |

**Overall confidence:** HIGH

### Gaps to Address

- **GHL SmartList API availability:** Prior research (Feb 2026) says no API endpoint exists. This should be re-verified against current GHL API v2 documentation before finalizing Phase 3 scope. If an endpoint now exists, Phase 3 becomes a code integration rather than a UX clarification.
- **Enrichment service production behavior:** PDL + SearchBug services exist but have limited production testing. Phase 4 should include integration testing with real API keys before deploying universally.
- **Cloud Run scaling + Gemini rate limits:** Module-level rate limit state is per-instance. Acceptable for current scale (small team, max 10 instances) but should be monitored. Not a v1.5 blocker.
- **RRC website stability:** HTML scraping is inherently fragile. Phase 2 should add header validation but cannot guarantee long-term reliability. Consider monitoring for parsing failures post-deploy.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all referenced files (services, models, API routes, frontend components)
- Existing implementation patterns in `Extract.tsx`, `data_enrichment_pipeline.py`, `gemini_service.py`

### Secondary (MEDIUM confidence)
- Prior GHL API research: `.planning/research/FEATURES-GHL-API.md` (2026-02-26)
- Prior GHL pitfalls research: `.planning/research/PITFALLS-GHL-API.md` (2026-02-26)

### Tertiary (LOW confidence)
- GHL SmartList API availability -- needs re-verification against current docs (web search was unavailable)

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
