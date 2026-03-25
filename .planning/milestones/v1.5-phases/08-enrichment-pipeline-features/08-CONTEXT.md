# Phase 8: Enrichment Pipeline Features - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the actual AI cleanup, address validation, and contact enrichment through the three buttons that Phase 7 placed on every tool page. Each step follows a propose-review-apply workflow. The preview table updates after each step using the updateEntries infrastructure from Phase 7. A provider-agnostic LLM interface enables future provider swapping.

Requirements: ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06, ENRICH-10

</domain>

<decisions>
## Implementation Decisions

### AI Cleanup Behavior
- Aggressive corrections: fix name casing (JOHN DOE -> John Doe), expand abbreviations (Jno -> John), infer entity types from name patterns (Smith Family -> Trust), reorder name parts
- Strip c/o from addresses, move to Notes/Comments column
- Flag incomplete entries (missing address, city, state) but do NOT attempt to infer/guess missing data -- just mark as incomplete and sort to top
- Preview updates silently after apply (no summary banner, no per-row changelog)

### Enrichment Sequencing
- Strict sequential order: Clean Up -> Validate -> Enrich
- Buttons unlock sequentially: Validate becomes clickable only after Clean Up completes, Enrich only after Validate completes
- If a step is unavailable (no API key configured), skip it and unlock the next step in the chain (e.g., no Google Maps key -> Enrich available after Clean Up)
- Re-runs allowed: user can re-run any completed step, with a confirmation dialog warning that previous results will be overwritten (manual edits are preserved)

### Two-Phase Propose-Review-Apply Workflow
- Each enrichment step follows this flow:
  1. AI/service scans ALL rows, identifies which ones need updates
  2. Flag those rows and sort to top of preview with a badge ("AI suggests changes")
  3. User can expand to see proposed changes, manually edit, or uncheck rows they don't want changed
  4. User clicks Apply to commit changes to checked/flagged rows
  5. After apply, changed rows get a brief green highlight animation that fades, rows stay at top for spot-checking
- Only checked (non-excluded) proposed rows get the changes applied
- This applies to all three steps (Clean Up, Validate, Enrich)

### Edit Conflict Resolution
- User manual edits win by default -- AI skips cells the user has already edited
- Exception: Google Maps address validation overrides user edits when it returns a verified correct address (authoritative data source)

### Provider-Agnostic LLM Interface
- Simple Python protocol/ABC: `cleanup_entries(entries) -> results` (and similar methods)
- GeminiProvider is the only implementation for v1.5
- Provider selected via global admin setting (not per-user)
- Backend interface only -- no admin UI for provider switching until v1.6 when Ollama/Qwen is added
- Prompts hardcoded in Python code as constants (Phase 9 adds tool-specific prompts, admin-editable prompts deferred to v1.6+)

### Loading UX
- Toolbar button shows spinner + "Processing..." text (already built in EnrichmentToolbar)
- Table remains interactive during processing -- user can scroll and review
- No table overlay or blocking UI

### Claude's Discretion
- Exact propose/apply button placement and styling within the EnrichmentToolbar
- How the "expand to see proposed changes" UI works (inline expand, tooltip, or mini-panel)
- Badge design for flagged rows
- Green highlight fade animation timing
- How to structure the LLM protocol methods beyond cleanup_entries
- Backend endpoint design (single unified endpoint vs per-step endpoints)

</decisions>

<specifics>
## Specific Ideas

- "I want AI to determine where updates can be made, then check those rows and then make updates. In the preview the ones that should be updated should be highlighted at the top so that the user can scroll through and spot check items."
- After changes are made, user should be able to see changes and spot check after updates are made
- Google Maps address validation is considered authoritative -- it should override even user edits when it returns a verified address

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EnrichmentToolbar` (frontend/src/components/EnrichmentToolbar.tsx): Three buttons with `onCleanUp`, `onValidate`, `onEnrich` callbacks, already wired to all 4 tool pages as stubs (`/* stub for Phase 8 */`)
- `usePreviewState` hook (frontend/src/hooks/usePreviewState.ts): `updateEntries()` method for replacing entry data, `editedFields` Map for tracking user edits, `excludedKeys` Set for unchecked rows, flagged row sorting
- `useFeatureFlags` hook (frontend/src/hooks/useFeatureFlags.ts): Fetches `/api/features/status` to determine which buttons to show
- `gemini_service.py` (backend/app/services/gemini_service.py): Existing Gemini client with rate limiting, cost tracking, batch processing (25 entries/batch). Currently does validation -- cleanup would be a new mode
- `address_validation_service.py` (backend/app/services/address_validation_service.py): Google Maps geocoding with `validate_addresses_batch()`, rate limiting (40 QPS), `AddressValidationResult` dataclass
- `enrichment_service.py` (backend/app/services/enrichment/enrichment_service.py): PDL + SearchBug orchestrator with runtime API key overrides from admin UI
- `AutoCorrectionsBanner` (frontend/src/components/AutoCorrectionsBanner.tsx): Existing component for showing correction summaries (used in Proration) -- available but user chose silent updates
- `features.py` (backend/app/api/features.py): `/api/features/status` endpoint returning cleanup/validate/enrich enabled flags

### Established Patterns
- Service modules follow `{domain}_service.py` naming with lazy client initialization
- Backend uses `async def` handlers, Pydantic models for request/response
- Frontend uses `usePreviewState` as single source of truth, `ApiClient` for fetch calls
- Feature flags checked via `/api/features/status` endpoint
- Runtime config overrides stored in Firestore, loaded via admin API

### Integration Points
- Frontend: Replace `/* stub for Phase 8 */` callbacks in Extract.tsx, Title.tsx, Proration.tsx, Revenue.tsx
- Backend: New endpoints needed for cleanup, validate, enrich (likely under `/api/enrichment/` or per-step)
- LLM protocol: New module (e.g., `backend/app/services/llm/`) with protocol + GeminiProvider
- Preview state: `updateEntries()` receives enriched data, `editedFields` consulted for conflict resolution

</code_context>

<deferred>
## Deferred Ideas

- Admin UI for LLM provider switching -- deferred to v1.6 when Ollama/Qwen is added
- Admin-editable prompt templates -- deferred to v1.6+
- Tool-specific AI prompts -- Phase 9
- SSE progress for enrichment steps -- explicitly out of scope per REQUIREMENTS.md

</deferred>

---

*Phase: 08-enrichment-pipeline-features*
*Context gathered: 2026-03-16*
