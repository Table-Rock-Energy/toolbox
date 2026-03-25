# Phase 8: Enrichment Pipeline Features - Research

**Researched:** 2026-03-16
**Domain:** AI cleanup, address validation, contact enrichment pipeline with propose-review-apply workflow
**Confidence:** HIGH

## Summary

Phase 8 wires the three enrichment buttons (Clean Up, Validate, Enrich) that Phase 7 placed on all four tool pages. Each button triggers a backend service call, receives proposed changes, displays them for user review, and applies approved changes to the preview state. The phase also introduces a provider-agnostic LLM interface (Python ABC/Protocol) with a GeminiProvider as the sole implementation.

The existing codebase already contains most backend services needed: `gemini_service.py` (AI validation with batching and rate limiting), `address_validation_service.py` (Google Maps geocoding with batch support), and `enrichment_service.py` (PDL + SearchBug orchestration). The primary work is: (1) creating a new LLM abstraction layer wrapping gemini_service for cleanup-specific prompts, (2) building three new API endpoints that return proposed changes in a common format, (3) building frontend propose-review-apply UI with the EnrichmentToolbar, and (4) wiring all four tool pages through a shared hook.

**Primary recommendation:** Create a unified `useEnrichmentPipeline` hook that manages sequential step state, propose/apply workflow, and API calls -- shared across all four tool pages. Backend endpoints should return a common `ProposedChanges` response format so the frontend workflow is identical regardless of which step is running.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- AI Cleanup: fix name casing, expand abbreviations, infer entity types, reorder name parts, strip c/o from addresses to Notes, flag incomplete entries (do NOT guess missing data), silent preview update after apply
- Strict sequential order: Clean Up -> Validate -> Enrich, buttons unlock sequentially, skip unavailable steps
- Two-phase propose-review-apply: AI scans all rows, flags ones needing updates, sorts to top, user reviews/unchecks, clicks Apply
- Edit conflict: user manual edits win by default; Google Maps address validation overrides user edits (authoritative source)
- Provider-agnostic LLM interface: Python protocol/ABC, GeminiProvider only for v1.5, provider selected via global admin setting, backend interface only
- Loading UX: spinner + "Processing..." on toolbar button, table remains interactive
- Prompts hardcoded as Python constants (Phase 9 adds tool-specific prompts, admin-editable deferred to v1.6+)

### Claude's Discretion
- Exact propose/apply button placement and styling within EnrichmentToolbar
- How "expand to see proposed changes" UI works (inline expand, tooltip, or mini-panel)
- Badge design for flagged rows
- Green highlight fade animation timing
- How to structure LLM protocol methods beyond cleanup_entries
- Backend endpoint design (single unified endpoint vs per-step endpoints)

### Deferred Ideas (OUT OF SCOPE)
- Admin UI for LLM provider switching -- deferred to v1.6
- Admin-editable prompt templates -- deferred to v1.6+
- Tool-specific AI prompts -- Phase 9
- SSE progress for enrichment steps -- explicitly out of scope per REQUIREMENTS.md
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRICH-03 | Clean Up (AI) runs first: fix names, strip c/o, move extras to notes, attempt to complete partial entries | LLM protocol + GeminiProvider with cleanup-specific prompts; existing `gemini_service.py` batching infrastructure reused |
| ENRICH-04 | Validate (Google Maps) runs second: verify cleaned addresses, flag mismatches | Existing `address_validation_service.py` with `validate_addresses_batch()` already handles this; needs propose-format wrapper |
| ENRICH-05 | Enrich (PDL/SearchBug) runs third: fill phone/email using clean validated addresses | Existing `enrichment_service.py` with `enrich_persons()` already handles this; needs propose-format wrapper |
| ENRICH-06 | After each enrichment step, preview table updates with enriched data visible to user | `usePreviewState.updateEntries()` already supports this; new `useEnrichmentPipeline` hook coordinates the propose-apply cycle |
| ENRICH-10 | AI cleanup uses provider-agnostic LLM interface (Gemini now, swappable in v1.6) | New `backend/app/services/llm/` module with Protocol class + GeminiProvider |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | >=1.0.0 | Gemini API client for AI cleanup | Already used in gemini_service.py |
| requests | - | Google Maps Geocoding API calls | Already used in address_validation_service.py |
| httpx | - | PDL/SearchBug async HTTP | Already used in enrichment providers |

### Supporting (Already Installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Request/response models for propose/apply endpoints | All new API models |
| React | 19.x | Frontend UI components | Tool pages + hooks |

### No New Dependencies Required
All backend and frontend libraries are already installed. Phase 8 creates new modules using existing libraries only.

## Architecture Patterns

### Recommended Project Structure (New Files)
```
backend/app/
├── services/
│   └── llm/                        # NEW: provider-agnostic LLM layer
│       ├── __init__.py
│       ├── protocol.py             # LLMProvider Protocol/ABC
│       ├── gemini_provider.py      # GeminiProvider implementation
│       └── prompts.py              # Cleanup prompt constants
├── api/
│   └── pipeline.py                 # NEW: /api/pipeline/* endpoints (cleanup, validate, enrich)
├── models/
│   └── pipeline.py                 # NEW: ProposedChange, PipelineRequest/Response models

frontend/src/
├── hooks/
│   └── useEnrichmentPipeline.ts    # NEW: shared pipeline state + API orchestration
├── components/
│   └── ProposedChangesPanel.tsx    # NEW: expandable row showing proposed changes
```

### Pattern 1: Provider-Agnostic LLM Protocol
**What:** A Python Protocol class defining the interface for LLM operations, with GeminiProvider as the sole implementation.
**When to use:** All AI cleanup operations go through this protocol.
**Example:**
```python
# backend/app/services/llm/protocol.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.models.pipeline import ProposedChange

@runtime_checkable
class LLMProvider(Protocol):
    async def cleanup_entries(
        self, tool: str, entries: list[dict]
    ) -> list[ProposedChange]: ...

    def is_available(self) -> bool: ...
```

**Key design decisions:**
- Use `typing.Protocol` (not ABC) -- more Pythonic, allows structural subtyping, no inheritance required
- `runtime_checkable` decorator enables `isinstance()` checks if needed
- Methods return `list[ProposedChange]` -- a unified change format, not tool-specific models
- Provider instance created at module level (singleton pattern matching existing gemini_service.py)

### Pattern 2: Unified Proposed Changes Format
**What:** A single Pydantic model for proposed changes across all three enrichment steps.
**When to use:** Every enrichment step returns the same shape so the frontend workflow is identical.
**Example:**
```python
# backend/app/models/pipeline.py
class ProposedChange(BaseModel):
    entry_index: int           # Index in the submitted entries array
    field: str                 # Field name to change
    current_value: str         # Current value
    proposed_value: str        # Suggested new value
    reason: str                # Human-readable explanation
    confidence: str            # "high", "medium", "low"
    source: str                # "ai_cleanup", "google_maps", "pdl", "searchbug"
    authoritative: bool = False # True for Google Maps (overrides user edits)
```

### Pattern 3: Frontend useEnrichmentPipeline Hook
**What:** A shared hook managing sequential step state, propose/apply cycle, and API calls.
**When to use:** Imported into all four tool pages, replacing the current stubs.
**Example:**
```typescript
// frontend/src/hooks/useEnrichmentPipeline.ts
interface EnrichmentPipelineOptions {
  tool: string
  entries: T[]
  updateEntries: (entries: T[]) => void
  editedFields: Map<string, Partial<T>>
  keyField: string
}

interface EnrichmentPipelineState {
  // Sequential step tracking
  completedSteps: Set<'cleanup' | 'validate' | 'enrich'>
  activeAction: 'cleanup' | 'validate' | 'enrich' | null

  // Propose-review state
  proposedChanges: ProposedChange[] | null
  checkedChanges: Set<number>  // indices of changes to apply

  // Toolbar callbacks
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  onApply: () => void
  onDismiss: () => void

  // Button enablement (sequential unlock)
  canValidate: boolean
  canEnrich: boolean
  isProcessing: boolean
}
```

### Pattern 4: Propose-Review-Apply Cycle
**What:** Three-step user interaction for each enrichment operation.
**When to use:** Every enrichment step follows this pattern.
**Flow:**
1. User clicks button -> API call to get proposed changes
2. Proposed changes displayed: flagged rows sorted to top, expandable to see per-field changes, checkboxes to include/exclude
3. User clicks Apply -> checked changes merged into entries via `updateEntries()`
4. Brief green highlight animation on changed rows, then fade

### Anti-Patterns to Avoid
- **Don't duplicate the gemini_service rate limiting in the LLM provider.** The GeminiProvider should delegate to the existing rate limiting infrastructure in gemini_service.py rather than reimplementing it.
- **Don't create separate API endpoints per tool per step.** Use a unified `/api/pipeline/{step}` with tool name in the request body (matching the existing `/api/ai/validate` pattern).
- **Don't track propose/apply state in individual tool pages.** The `useEnrichmentPipeline` hook should own all state; tool pages just consume it.
- **Don't modify `usePreviewState` internals.** Use its public API (`updateEntries`, `editedFields`) from the pipeline hook.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI batching + rate limiting | Custom batching logic | Existing `gemini_service.py` batching (25/batch, 6s delay, RPM/RPD/budget limits) | Already handles Gemini free tier limits, retry logic, spend tracking |
| Address geocoding | Custom geocoding client | Existing `address_validation_service.py` with `validate_addresses_batch()` | Already handles rate limiting (40 QPS), component extraction, change detection |
| Contact enrichment orchestration | Custom PDL/SearchBug merging | Existing `enrichment_service.py` with `enrich_persons()` | Already merges PDL + SearchBug, handles deduplication, phone cap |
| Edit conflict detection | Custom diff tracking | `usePreviewState.editedFields` Map | Already tracks which cells the user has manually edited |
| Flagged row sorting | Custom sort logic | `usePreviewState` flagField-based sorting | Already sorts flagged rows to top with stable sort |

**Key insight:** Phase 8's backend work is mostly wrapping existing services in a common ProposedChange format and adding the LLM protocol layer. The heavy lifting (API clients, rate limiting, data merging) is already done.

## Common Pitfalls

### Pitfall 1: Race Conditions on Concurrent Button Clicks
**What goes wrong:** User clicks Clean Up, then immediately clicks Validate before cleanup finishes. Two async operations modify entries simultaneously.
**Why it happens:** EnrichmentToolbar doesn't enforce sequential execution beyond disabling during processing.
**How to avoid:** The `useEnrichmentPipeline` hook must set `isProcessing` immediately on click and disable ALL buttons until the current step completes. The `activeAction` prop already exists in EnrichmentToolbar for this.
**Warning signs:** Entries appear to "jump" or revert, propose panel shows stale data.

### Pitfall 2: editedFields Conflict with Proposed Changes
**What goes wrong:** User manually edits a name field, then AI cleanup proposes a different name for the same field. Apply overwrites the user's edit.
**Why it happens:** `updateEntries()` replaces entire entries, not individual fields.
**How to avoid:** Before applying proposed changes, filter out any change where `editedFields.has(key)` and the change's field matches an edited field. Exception: changes with `authoritative: true` (Google Maps) override user edits per CONTEXT.md decision.
**Warning signs:** User complains their manual edits disappeared after clicking Apply.

### Pitfall 3: Stale Entries After Multiple Steps
**What goes wrong:** Clean Up modifies entries, user makes more manual edits, then Validate sends the pre-edit entries to the API.
**Why it happens:** The entries sent to the API might be captured from `previewEntries` at render time, not including the latest edits.
**How to avoid:** Always build the entries to send from the current `previewEntries` (which includes applied edits) at the moment the API call is made, not from a stale closure.
**Warning signs:** Validate proposes fixing addresses that the user already fixed manually.

### Pitfall 4: Gemini Batch Size vs Entry Count
**What goes wrong:** 200+ entries cause 8+ batches with 48+ seconds of batching delay, making "Processing..." appear to hang.
**Why it happens:** Gemini free tier rate limiting requires 6s between batches.
**How to avoid:** This is expected behavior. Consider showing batch progress in the button text (e.g., "Processing... 3/8") or accept the wait since SSE is out of scope. The existing 500-entry cap on `/api/ai/validate` is a reasonable limit.
**Warning signs:** Users think the app is frozen on large datasets.

### Pitfall 5: Address Field Name Mismatch Across Tools
**What goes wrong:** `validate_addresses_batch()` expects `mailing_address` as the street field default, but different tools use different field names.
**Why it happens:** Extract uses `mailing_address`, Title uses `address`, Revenue has no address fields.
**How to avoid:** The pipeline endpoint must accept field name mappings per tool, or the hook should normalize field names before sending. The existing `validate_addresses_batch()` already supports custom field names via parameters.
**Warning signs:** Validate returns "no addresses found" because it's looking in the wrong fields.

## Code Examples

### Backend: LLM Provider Protocol
```python
# backend/app/services/llm/protocol.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.models.pipeline import ProposedChange

@runtime_checkable
class LLMProvider(Protocol):
    async def cleanup_entries(
        self, tool: str, entries: list[dict]
    ) -> list[ProposedChange]:
        """Run AI cleanup on entries. Returns proposed changes."""
        ...

    def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        ...
```

### Backend: GeminiProvider Implementation
```python
# backend/app/services/llm/gemini_provider.py
from app.services.llm.protocol import LLMProvider
from app.services.llm.prompts import CLEANUP_PROMPTS
from app.models.pipeline import ProposedChange

class GeminiProvider:
    """Gemini-backed LLM provider for AI cleanup."""

    async def cleanup_entries(
        self, tool: str, entries: list[dict]
    ) -> list[ProposedChange]:
        # Delegates to existing gemini_service batching infrastructure
        from app.services.gemini_service import validate_entries
        result = await validate_entries(tool, entries)
        # Transform AiSuggestion -> ProposedChange
        return [
            ProposedChange(
                entry_index=s.entry_index,
                field=s.field,
                current_value=s.current_value,
                proposed_value=s.suggested_value,
                reason=s.reason,
                confidence=s.confidence.value,
                source="ai_cleanup",
                authoritative=False,
            )
            for s in result.suggestions
        ]

    def is_available(self) -> bool:
        from app.core.config import settings
        return settings.use_gemini
```

### Backend: Pipeline Endpoint
```python
# backend/app/api/pipeline.py
@router.post("/cleanup")
async def pipeline_cleanup(request: PipelineRequest) -> PipelineResponse:
    provider = get_llm_provider()
    if not provider or not provider.is_available():
        return PipelineResponse(success=False, error="AI cleanup not configured")
    changes = await provider.cleanup_entries(request.tool, request.entries)
    return PipelineResponse(success=True, proposed_changes=changes)

@router.post("/validate")
async def pipeline_validate(request: PipelineRequest) -> PipelineResponse:
    from app.services.address_validation_service import validate_addresses_batch
    import asyncio
    results = await asyncio.to_thread(
        validate_addresses_batch, request.entries,
        street_field=request.field_mapping.get("street", "mailing_address"),
        # ... other field mappings
    )
    # Transform AddressValidationResult -> ProposedChange with authoritative=True
    ...

@router.post("/enrich")
async def pipeline_enrich(request: PipelineRequest) -> PipelineResponse:
    from app.services.enrichment.enrichment_service import enrich_persons
    result = await enrich_persons(request.entries)
    # Transform EnrichedPerson -> ProposedChange
    ...
```

### Frontend: useEnrichmentPipeline Hook (Key Logic)
```typescript
// Apply proposed changes respecting user edits
const applyChanges = useCallback(() => {
  const updatedEntries = [...currentEntries]
  for (const change of proposedChanges) {
    if (!checkedChanges.has(change.entry_index)) continue
    const key = String(updatedEntries[change.entry_index][keyField])
    const userEdits = editedFields.get(key)
    // Skip if user edited this field (unless authoritative)
    if (userEdits?.[change.field] !== undefined && !change.authoritative) continue
    updatedEntries[change.entry_index] = {
      ...updatedEntries[change.entry_index],
      [change.field]: change.proposed_value,
    }
  }
  updateEntries(updatedEntries)
  setProposedChanges(null)
  setCompletedSteps(prev => new Set([...prev, currentStep]))
}, [proposedChanges, checkedChanges, editedFields, currentEntries])
```

### Frontend: Sequential Button Unlock Logic
```typescript
// In useEnrichmentPipeline
const canValidate = useMemo(() => {
  if (!featureFlags.validateEnabled) return false
  return completedSteps.has('cleanup') || !featureFlags.cleanUpEnabled
}, [completedSteps, featureFlags])

const canEnrich = useMemo(() => {
  if (!featureFlags.enrichEnabled) return false
  // Can enrich if validate completed, OR validate unavailable and cleanup completed
  if (completedSteps.has('validate')) return true
  if (!featureFlags.validateEnabled) {
    return completedSteps.has('cleanup') || !featureFlags.cleanUpEnabled
  }
  return false
}, [completedSteps, featureFlags])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct gemini_service calls from AI validation router | Provider-agnostic LLM protocol wrapping gemini_service | Phase 8 (new) | Enables future Ollama/Qwen swap in v1.6 |
| Separate validation/enrichment API patterns | Unified /api/pipeline/* with ProposedChange format | Phase 8 (new) | Frontend workflow identical for all three steps |
| Auto-apply corrections silently | Propose-review-apply with user confirmation | Phase 8 (new) | User maintains control over all changes |

## Open Questions

1. **Address field names per tool**
   - What we know: Extract uses `mailing_address`, `city`, `state`, `zip_code`. Title likely uses different names. Revenue has no address fields.
   - What's unclear: Exact field name mapping for each tool.
   - Recommendation: Planner should include a task to audit field names across all four tools and define a `FIELD_MAPPING` constant per tool for the pipeline endpoints. This is a quick investigation task.

2. **Cleanup prompt differentiation from validation prompts**
   - What we know: `gemini_service.py` already has TOOL_PROMPTS for validation (checking correctness). Cleanup needs different prompts (actively fixing/improving data, not just flagging).
   - What's unclear: Whether to reuse validate_entries with different prompts or create a separate cleanup function in the provider.
   - Recommendation: Create separate cleanup prompts in `prompts.py` focused on corrections (name casing, c/o stripping, abbreviation expansion). Reuse the existing batching/rate-limiting infrastructure via a new method that accepts custom prompts.

3. **Re-run behavior with confirmation dialog**
   - What we know: CONTEXT.md says re-runs allowed with confirmation dialog warning previous results overwritten but manual edits preserved.
   - What's unclear: Whether "manual edits preserved" means editedFields stay in the Map, or that re-run results should exclude fields the user manually edited.
   - Recommendation: Both -- editedFields Map is never cleared by re-run, AND the propose step skips fields already in editedFields (except authoritative Google Maps changes).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (asyncio_mode = auto) |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRICH-03 | Cleanup endpoint returns proposed changes from LLM | unit | `python3 -m pytest tests/test_pipeline_cleanup.py -x` | No -- Wave 0 |
| ENRICH-04 | Validate endpoint returns proposed address corrections | unit | `python3 -m pytest tests/test_pipeline_validate.py -x` | No -- Wave 0 |
| ENRICH-05 | Enrich endpoint returns proposed phone/email additions | unit | `python3 -m pytest tests/test_pipeline_enrich.py -x` | No -- Wave 0 |
| ENRICH-06 | Preview updates after apply (frontend) | manual-only | N/A -- React component behavior, no frontend test suite | N/A |
| ENRICH-10 | LLM protocol allows provider swap | unit | `python3 -m pytest tests/test_llm_protocol.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -x -q`
- **Per wave merge:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_cleanup.py` -- covers ENRICH-03 (mock Gemini, verify ProposedChange output)
- [ ] `tests/test_pipeline_validate.py` -- covers ENRICH-04 (mock Google Maps, verify address correction proposals)
- [ ] `tests/test_pipeline_enrich.py` -- covers ENRICH-05 (mock PDL/SearchBug, verify phone/email proposals)
- [ ] `tests/test_llm_protocol.py` -- covers ENRICH-10 (verify Protocol structure, GeminiProvider satisfies it)

## Sources

### Primary (HIGH confidence)
- Existing codebase: `gemini_service.py`, `address_validation_service.py`, `enrichment_service.py` -- direct code review
- Existing codebase: `usePreviewState.ts`, `EnrichmentToolbar.tsx`, `useFeatureFlags.ts` -- direct code review
- Existing codebase: All four tool pages (Extract, Title, Proration, Revenue) -- Phase 8 stubs confirmed

### Secondary (MEDIUM confidence)
- Python typing.Protocol documentation -- standard library, well-documented pattern for structural subtyping

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use, no new dependencies
- Architecture: HIGH -- building on established patterns (service modules, Pydantic models, React hooks), well-understood integration points
- Pitfalls: HIGH -- identified from direct code analysis of field name differences, race conditions visible in current stub patterns, edit conflict logic clear from usePreviewState internals

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable -- all underlying services already exist)
