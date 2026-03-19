# Phase 12: Unified Enrichment Modal - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 3-button enrichment toolbar (Clean Up, Validate, Enrich) with a single "Enrich" button that opens a modal. The modal runs all enabled steps sequentially, auto-applies all changes, shows progress with step labels, and updates the preview table live as each step completes. Modified cells are highlighted so the user can review exactly what changed.

Requirements: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06, ENRICH-07

</domain>

<decisions>
## Implementation Decisions

### Review-vs-auto flow
- Full auto-apply: all steps run and apply automatically without pausing for user review
- All confidence levels auto-apply (high, medium, low) — no more propose-review-apply per step
- User reviews changes AFTER completion via highlighted cells in the preview table
- Global undo button appears in toolbar after enrichment completes — one click reverts all changes to pre-enrichment state (uses snapshot pattern from existing preAutoApplySnapshot)
- Single "Enrich" button completely replaces the 3 individual buttons — no advanced toggle for individual steps

### Modal interaction
- User CAN close modal while pipeline is running — steps continue in background
- When modal is closed mid-run, the Enrich button shows spinner + "Running..." state; clicking reopens modal to see detailed progress
- Failed steps are skipped, pipeline continues to next step — failed step shows error icon in modal, completed step results are preserved
- Preview table updates live after each step completes (not batched at end) — if user closes modal, they see partial results immediately

### Cell highlighting
- Per-cell highlighting: only the specific cells that changed get a subtle background tint (bg-green-50 or bg-tre-teal/10)
- Highlights persist until user clicks "Clear highlights" or starts a new upload — no auto-fade
- Hover tooltip on highlighted cells shows original value ("Original: [old value]")
- Highlights are visual only — do not affect exports

### Button & trigger UX
- Single "Enrich" button in same toolbar slot where 3 buttons currently live (above preview table, alongside export buttons)
- Teal gradient style matching existing Clean Up button (bg-gradient-to-r from-tre-teal)
- Label: "Enrich (N)" with Wand2 or Sparkles icon, showing entry count
- After completion: button changes to "Enriched" with check icon and green tint
- Clicking completed button re-runs with confirmation dialog
- "Clear highlights" and "Undo Enrichment" appear as secondary actions nearby after completion
- During run (if modal closed): button shows spinner + "Running..." and reopens modal on click

### Claude's Discretion
- Exact progress bar implementation (can reuse/adapt EnrichmentProgress.tsx step-based UI)
- ETA calculation approach (simple elapsed-time extrapolation or step-count based)
- How to structure runAllSteps() internal state management (local variable threading per STATE.md decision)
- AbortController wiring details
- Exact tooltip styling for original value display
- Animation for button state transitions (enriching → enriched)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Enrichment pipeline
- `.planning/phases/08-enrichment-pipeline-features/08-CONTEXT.md` — Phase 8 enrichment decisions (propose-review-apply workflow being replaced, auto-apply for high-confidence, edit conflict resolution rules)
- `.planning/REQUIREMENTS.md` — ENRICH-01 through ENRICH-07 acceptance criteria

### Out of scope constraints
- `.planning/REQUIREMENTS.md` §Out of Scope — SSE for enrichment progress explicitly out of scope; enrichment abort/cancel mid-step out of scope

### State decisions
- `.planning/STATE.md` §Accumulated Context — runAllSteps() uses local variable threading; sequential await not SSE; AbortController signal propagation concern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useEnrichmentPipeline.ts` — Core hook with `runStep()`, auto-apply logic, highlight tracking, snapshot/undo. Needs `runAllSteps()` added and confidence filtering removed for unified flow
- `EnrichmentProgress.tsx` — Step-based progress modal with per-step progress bars, step indicators, completion summary. Can be adapted into the enrichment modal
- `Modal.tsx` — Generic modal with sizes (sm/md/lg/xl/full), ESC close, backdrop click, header/body/footer slots
- `EnrichmentToolbar.tsx` — 3-button toolbar (will be replaced by single button + post-enrichment actions)
- `EnrichmentPanel.tsx` — Side panel for contact enrichment results (separate from pipeline, not affected)

### Established Patterns
- `usePreviewState` hook is single source of truth for table data — `updateEntries()` for data changes, `editedFields` Map for tracking user edits
- Feature flags via `/api/features/status` determine which steps are enabled/skipped
- `pipelineApi` in `utils/api.ts` has `.cleanup()`, `.validate()`, `.enrich()` methods
- Tool pages (Extract, Title, Proration, Revenue) all wire EnrichmentToolbar identically via useEnrichmentPipeline hook

### Integration Points
- Replace EnrichmentToolbar usage in 4 tool pages (Extract.tsx, Title.tsx, Proration.tsx, Revenue.tsx)
- New `runAllSteps()` method in useEnrichmentPipeline hook that calls runStep() for each enabled step sequentially
- New change tracking Map (entry_index + field → original_value) for per-cell highlights and hover tooltips
- Post-enrichment toolbar state: Enriched button + Clear highlights + Undo Enrichment

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-unified-enrichment-modal*
*Context gathered: 2026-03-19*
