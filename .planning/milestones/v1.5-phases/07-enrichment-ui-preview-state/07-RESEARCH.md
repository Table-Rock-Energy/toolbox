# Phase 7: Enrichment UI & Preview State - Research

**Researched:** 2026-03-13
**Domain:** React frontend architecture -- shared enrichment buttons, editable preview table, export-from-preview pattern
**Confidence:** HIGH

## Summary

Phase 7 requires building a universal enrichment button bar and making the preview table the single source of truth for exports across four tool pages (Extract, Title, Proration, Revenue). The codebase already has partial implementations: Extract has all three buttons (Validate, AI Review, Contact Lookup) and a streaming enrichment flow; Title has AI Review and Contact Lookup; Proration and Revenue only have AI Review. Each tool page is 700-1500 lines of duplicated table rendering, filtering, exclusion, and export logic.

The key architectural challenge is **extracting shared state management and UI components** from four divergent tool pages without breaking their tool-specific behavior. Each page has different entry shapes (PartyEntry, OwnerEntry, MineralHolderRow, RevenueRow), different exclusion mechanisms (entry_number set, index set, _id set, index set), and different export flows. The enrichment buttons need a unified backend endpoint for feature availability (currently split across `/extract/pipeline-status`, `/ai/status`, and `/enrichment/status`).

**Primary recommendation:** Create a shared `EnrichmentToolbar` component and a `usePreviewState` hook that encapsulates the common patterns (exclusion tracking, inline editing, flagged-row sorting, export derivation), parameterized by tool-specific entry shape and key field. Wire a single `/api/features/status` endpoint that returns all three feature flags in one call.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRICH-01 | Three conditional buttons (Clean Up, Validate, Enrich) shown across all tool pages | Shared `EnrichmentToolbar` component replaces per-page button rendering; feature flags drive visibility |
| ENRICH-02 | Buttons visible only when corresponding API keys/switches are configured | Single `/api/features/status` endpoint returns `cleanup_enabled`, `validate_enabled`, `enrich_enabled`; toolbar hides unavailable buttons |
| ENRICH-06 | After enrichment step, preview table updates with enriched data | `usePreviewState` hook exposes `updateEntries()` method; enrichment callbacks merge results into preview state |
| ENRICH-07 | Flagged rows sort to top of preview for user review | Sort comparator in `usePreviewState` places `flagged: true` rows first; works with existing filter/sort |
| ENRICH-08 | User can uncheck flagged rows to omit from export, or edit inline | Exclusion set + inline edit state managed by `usePreviewState`; cell-level editing with blur-to-commit |
| ENRICH-09 | Export always reflects current preview state (edits, unchecks, enrichment) | `entriesToExport` computed from preview state with exclusions applied; passed to export handlers |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | Component framework | Already in use |
| TypeScript | 5.x | Type safety for generic hook/component | Already in use, strict mode |
| Tailwind CSS | 3.x | Styling enrichment toolbar and editable cells | Already in use with tre-* colors |
| Lucide React | 0.x | Icons for Clean Up (Wand2), Validate (MapPin), Enrich (Search) | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | 0.x | Backend feature status endpoint | Single unified endpoint |

No new libraries needed. This phase is entirely about refactoring existing patterns into shared components.

## Architecture Patterns

### Current State (Problem)

Each tool page independently implements:
1. **Feature flag fetching** -- separate `useEffect` calls to `/ai/status`, `/enrichment/status`, `/extract/pipeline-status`
2. **Entry exclusion** -- `excludedEntries` (Set of entry_number), `excludedIndices` (Set of index), `excludedRows` (Set of _id)
3. **Export derivation** -- `entriesToExport` / `rowsToExport` computed via `useMemo`
4. **Inline editing** -- only Proration has a modal-based row editor; others have no inline edit
5. **Enrichment buttons** -- Extract has Validate+AI+Enrich, Title has AI+Enrich, Proration/Revenue have AI only

### Recommended Architecture

```
frontend/src/
  components/
    EnrichmentToolbar.tsx      # NEW: shared 3-button bar
    EditableCell.tsx            # NEW: inline cell editor
  hooks/
    usePreviewState.ts         # NEW: generic preview state management
    useFeatureFlags.ts         # NEW: single-call feature availability
  pages/
    Extract.tsx                # MODIFIED: use shared hooks/components
    Title.tsx                  # MODIFIED: use shared hooks/components
    Proration.tsx              # MODIFIED: use shared hooks/components
    Revenue.tsx                # MODIFIED: use shared hooks/components
  backend/app/api/
    features.py                # NEW: unified feature status endpoint
```

### Pattern 1: usePreviewState Hook (Generic)

**What:** A generic React hook that manages the preview table state for any tool entry type.
**When to use:** Every tool page that shows processed results in a table.

```typescript
// Generic hook parameterized by entry type and key field
interface UsePreviewStateOptions<T> {
  entries: T[]                    // Source entries from processing result
  keyField: keyof T              // Unique identifier field (entry_number, _id, index)
  initialExcluded?: Set<string>  // Pre-excluded keys
}

interface PreviewState<T> {
  // Core state
  previewEntries: T[]            // Entries with edits applied
  excludedKeys: Set<string>      // Keys of excluded entries
  editedFields: Map<string, Partial<T>>  // Overrides per entry key

  // Derived
  entriesToExport: T[]           // Filtered, non-excluded, with edits applied
  flaggedEntries: T[]            // Entries with flagged=true, sorted to top

  // Actions
  updateEntries: (entries: T[]) => void  // Replace all entries (after enrichment)
  toggleExclude: (key: string) => void
  toggleExcludeAll: (keys: string[]) => void
  editField: (key: string, field: keyof T, value: unknown) => void
  resetEdits: () => void

  // Selection helpers
  isAllSelected: boolean
  isSomeSelected: boolean
}
```

### Pattern 2: EnrichmentToolbar Component

**What:** Shared button bar that shows Clean Up, Validate, and Enrich buttons based on feature flags.
**When to use:** Rendered in every tool page's results header area.

```typescript
interface EnrichmentToolbarProps {
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  isCleaningUp?: boolean
  isValidating?: boolean
  isEnriching?: boolean
  entryCount: number
  // Feature flags injected from useFeatureFlags
  cleanUpEnabled: boolean
  validateEnabled: boolean
  enrichEnabled: boolean
}
```

### Pattern 3: useFeatureFlags Hook

**What:** Single API call to get all feature availability flags.
**When to use:** Once per tool page mount.

```typescript
interface FeatureFlags {
  cleanUpEnabled: boolean    // gemini_enabled (AI cleanup)
  validateEnabled: boolean   // google_maps_enabled (address validation)
  enrichEnabled: boolean     // enrichment_enabled (PDL/SearchBug)
}

function useFeatureFlags(): FeatureFlags {
  // Single GET /api/features/status
  // Replaces 3 separate API calls per page
}
```

### Pattern 4: Flagged Row Sorting

**What:** Entries with `flagged: true` (or equivalent) automatically sort to the top of the preview table.
**When to use:** After any enrichment step returns flagged entries.

Each tool already has a `flagged` or similar field:
- Extract: `PartyEntry.flagged` (boolean) + `flag_reason`
- Title: `OwnerEntry.duplicate_flag` (boolean) -- needs a generic `flagged` field added
- Proration: No flag field yet -- add `flagged` + `flag_reason`
- Revenue: No flag field yet -- add `flagged` + `flag_reason`

The sort must be stable (flagged first, then preserve existing sort order).

### Pattern 5: Inline Cell Editing

**What:** Click-to-edit cells in the preview table.
**When to use:** User wants to correct a value before export.

```typescript
// EditableCell wraps any table cell
interface EditableCellProps {
  value: string | number | undefined
  onCommit: (newValue: string) => void
  type?: 'text' | 'number'
}
```

Implementation: Display as `<span>`, click converts to `<input>`, blur/Enter commits, Escape cancels. Edited cells get a subtle visual indicator (e.g., light blue background).

### Anti-Patterns to Avoid

- **Copying hook logic per page:** Each page should call `usePreviewState` rather than maintaining its own `excludedEntries`/`entriesToExport` logic.
- **Multiple feature-flag API calls:** Replace 3 separate `useEffect` calls with one `useFeatureFlags()`.
- **Enrichment buttons that call different endpoints per tool:** Phase 7 only wires the UI and preview state. Phase 8 connects actual enrichment logic. Buttons in Phase 7 should call tool-agnostic callbacks passed as props.
- **Breaking existing export flows:** The `entriesToExport` from `usePreviewState` must be backward-compatible with existing export handlers that POST entries to backend.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Inline cell editing | Custom contentEditable with selection management | Simple controlled `<input>` appearing on click | contentEditable has cross-browser quirks; input is simpler and sufficient |
| Entry diffing after enrichment | Custom deep-diff to highlight changes | Compare old vs new values per-field, mark changed cells | Full diffing is overkill; per-field comparison is sufficient |
| Complex state management | Redux/Zustand for preview state | React useState + useMemo in custom hook | Existing patterns use local state; adding a state library for one feature is overhead |

## Common Pitfalls

### Pitfall 1: Entry Key Instability
**What goes wrong:** Using array index as key for exclusion sets, then enrichment adds/removes entries (e.g., name splitting), invalidating all indices.
**Why it happens:** Title page uses index-based exclusion; if entries change length, exclusion set is wrong.
**How to avoid:** Use a stable unique key per entry. Extract has `entry_number`. Title/Revenue/Proration need a synthetic stable ID (e.g., generated UUID on first load). The `usePreviewState` hook should require a `keyField` that returns a stable identifier.
**Warning signs:** After enrichment, wrong rows are excluded or included.

### Pitfall 2: Stale Closure in Enrichment Callbacks
**What goes wrong:** Enrichment callback captures stale `activeJob` or `entries` state, overwrites newer edits.
**Why it happens:** Streaming enrichment (Extract's `handleValidate`) closes over state at call time.
**How to avoid:** Use functional state updates (`setEntries(prev => ...)`) or pass latest state via ref. The `updateEntries` method in `usePreviewState` should replace the full entry array.
**Warning signs:** User edits disappear after enrichment completes.

### Pitfall 3: Export Sends Original Data Instead of Preview State
**What goes wrong:** Export handler sends `activeJob.result.entries` instead of `previewEntries` (which includes edits).
**Why it happens:** Export was written before inline editing existed, references original data.
**How to avoid:** All export handlers must use `entriesToExport` from `usePreviewState`, never `activeJob.result.entries` directly.
**Warning signs:** Exported CSV does not reflect user's inline edits.

### Pitfall 4: Race Condition on Concurrent Button Clicks
**What goes wrong:** User clicks Clean Up, then immediately clicks Validate before Clean Up finishes.
**Why it happens:** No serialization of enrichment operations.
**How to avoid:** Disable all enrichment buttons while any enrichment operation is in progress. STATE.md already notes this as a known concern.
**Warning signs:** Preview table shows partial/conflicting results.

### Pitfall 5: Flagged Sort Conflicts with User Sort
**What goes wrong:** User sorts by name, then enrichment flags some rows and forces them to top, disrupting the user's chosen sort.
**How to avoid:** Flagged-to-top sort should be a "priority" layer that composes with user sort: flagged first, then within flagged/unflagged groups, apply the user's chosen sort column.
**Warning signs:** Table sort feels broken or inconsistent after enrichment.

## Code Examples

### Unified Feature Status Endpoint (Backend)

```python
# backend/app/api/features.py
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/status")
async def feature_status():
    """Return all enrichment feature availability flags in one call."""
    return {
        "cleanup_enabled": settings.use_gemini,      # AI-powered cleanup
        "validate_enabled": settings.use_google_maps, # Address validation
        "enrich_enabled": settings.use_enrichment,    # PDL/SearchBug contact lookup
    }
```

### useFeatureFlags Hook (Frontend)

```typescript
// frontend/src/hooks/useFeatureFlags.ts
import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export interface FeatureFlags {
  cleanUpEnabled: boolean
  validateEnabled: boolean
  enrichEnabled: boolean
  loaded: boolean
}

export function useFeatureFlags(): FeatureFlags {
  const [flags, setFlags] = useState<FeatureFlags>({
    cleanUpEnabled: false,
    validateEnabled: false,
    enrichEnabled: false,
    loaded: false,
  })

  useEffect(() => {
    api.get<{ cleanup_enabled: boolean; validate_enabled: boolean; enrich_enabled: boolean }>(
      '/features/status'
    ).then(res => {
      if (res.data) {
        setFlags({
          cleanUpEnabled: res.data.cleanup_enabled,
          validateEnabled: res.data.validate_enabled,
          enrichEnabled: res.data.enrich_enabled,
          loaded: true,
        })
      }
    })
  }, [])

  return flags
}
```

### EnrichmentToolbar Component

```typescript
// frontend/src/components/EnrichmentToolbar.tsx
import { Wand2, MapPin, Search } from 'lucide-react'

interface EnrichmentToolbarProps {
  cleanUpEnabled: boolean
  validateEnabled: boolean
  enrichEnabled: boolean
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  isProcessing: boolean
  entryCount: number
}

export default function EnrichmentToolbar({
  cleanUpEnabled, validateEnabled, enrichEnabled,
  onCleanUp, onValidate, onEnrich,
  isProcessing, entryCount,
}: EnrichmentToolbarProps) {
  const hasAnyButton = cleanUpEnabled || validateEnabled || enrichEnabled
  if (!hasAnyButton) return null

  return (
    <div className="flex gap-2">
      {cleanUpEnabled && (
        <button
          onClick={onCleanUp}
          disabled={isProcessing || entryCount === 0}
          className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-tre-teal to-tre-teal/80 text-white rounded-lg hover:from-tre-teal/90 hover:to-tre-teal/70 transition-colors text-sm disabled:opacity-50"
        >
          <Wand2 className="w-4 h-4" />
          {isProcessing ? 'Processing...' : 'Clean Up'}
        </button>
      )}
      {validateEnabled && (
        <button
          onClick={onValidate}
          disabled={isProcessing || entryCount === 0}
          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm disabled:opacity-50"
        >
          <MapPin className="w-4 h-4" />
          Validate
        </button>
      )}
      {enrichEnabled && (
        <button
          onClick={onEnrich}
          disabled={isProcessing || entryCount === 0}
          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm disabled:opacity-50"
        >
          <Search className="w-4 h-4" />
          Enrich ({entryCount})
        </button>
      )}
    </div>
  )
}
```

### Inline EditableCell

```typescript
// frontend/src/components/EditableCell.tsx
import { useState, useRef, useEffect } from 'react'

interface EditableCellProps {
  value: string | number | undefined
  onCommit: (newValue: string) => void
  className?: string
}

export default function EditableCell({ value, onCommit, className = '' }: EditableCellProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(String(value ?? ''))
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing) inputRef.current?.focus()
  }, [isEditing])

  const handleCommit = () => {
    setIsEditing(false)
    if (editValue !== String(value ?? '')) {
      onCommit(editValue)
    }
  }

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleCommit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleCommit()
          if (e.key === 'Escape') { setEditValue(String(value ?? '')); setIsEditing(false) }
        }}
        className={`w-full px-1 py-0.5 text-sm border border-tre-teal rounded focus:outline-none focus:ring-1 focus:ring-tre-teal ${className}`}
      />
    )
  }

  return (
    <span
      onClick={() => { setEditValue(String(value ?? '')); setIsEditing(true) }}
      className={`cursor-pointer hover:bg-tre-teal/5 px-1 py-0.5 rounded ${className}`}
      title="Click to edit"
    >
      {value ?? '-'}
    </span>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-page feature flag fetching (3 calls) | Single unified `/api/features/status` | Phase 7 | Reduces API calls from 3 to 1 per page load |
| Index-based row exclusion | Stable key-based exclusion | Phase 7 | Survives entry additions/removals from enrichment |
| No inline editing (except Proration modal) | Click-to-edit cells in preview table | Phase 7 | Users can fix data before export without modal |
| Export reads from original processing result | Export reads from preview state (edits + exclusions) | Phase 7 | Export reflects what user actually sees |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + httpx |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRICH-01 | Three buttons rendered when features enabled | manual-only | Visual verification in browser | N/A |
| ENRICH-02 | Buttons hidden when API keys missing | unit (backend) | `python3 -m pytest tests/test_feature_status.py -x` | Wave 0 |
| ENRICH-06 | Preview updates after enrichment | manual-only | Visual verification -- state update is frontend-only | N/A |
| ENRICH-07 | Flagged rows sort to top | manual-only | Visual verification in browser | N/A |
| ENRICH-08 | Uncheck/edit rows in preview | manual-only | Visual verification in browser | N/A |
| ENRICH-09 | Export reflects preview state | unit (backend) | `python3 -m pytest tests/test_export_preview.py -x` | Wave 0 |

**Note:** ENRICH-01, ENRICH-06, ENRICH-07, ENRICH-08 are primarily frontend UI behavior. No frontend test suite exists (per CLAUDE.md). Backend tests cover the feature status endpoint and export payload integrity.

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_feature_status.py` -- covers ENRICH-02 (feature flags endpoint returns correct values based on config)
- [ ] `tests/test_export_preview.py` -- covers ENRICH-09 (export endpoint accepts and uses preview-state entries with edits applied)

## Open Questions

1. **Entry key stability for Title page**
   - What we know: Extract uses `entry_number`, Revenue uses synthetic `_id`, Proration uses array index
   - What's unclear: Title uses array index for exclusion -- needs a stable key
   - Recommendation: Generate a synthetic `_uid` field when entries are first loaded (crypto.randomUUID or incrementing counter). Apply this in `usePreviewState` initialization.

2. **Clean Up / Validate button naming vs. existing "Validate Data" button**
   - What we know: Extract already has a "Validate Data" button that triggers the streaming enrichment pipeline. The new Phase 7 buttons are "Clean Up" and "Validate" which map to the same underlying operations.
   - What's unclear: Should the existing Extract "Validate Data" flow be split into "Clean Up" + "Validate" or kept as one?
   - Recommendation: The existing streaming enrichment on Extract already runs addresses + names + splitting in sequence. Phase 7 should present this as the same three buttons but each button triggers only its portion. Phase 8 will wire the actual backend logic. Phase 7 buttons are UI-only stubs with loading states.

3. **Proration page compatibility**
   - What we know: Proration has a modal-based row editor (not inline). It also has RRC-specific buttons and a very different table layout.
   - What's unclear: Should Proration get inline editing or keep its modal editor?
   - Recommendation: Keep the modal editor for Proration (it edits many fields at once including RRC lookups). Add the three enrichment buttons to the results header bar, but Proration can use the modal for row-level edits and the enrichment buttons for batch operations.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `frontend/src/pages/Extract.tsx`, `Title.tsx`, `Proration.tsx`, `Revenue.tsx` -- current button rendering, exclusion patterns, export flows
- Codebase analysis: `frontend/src/components/EnrichmentPanel.tsx`, `EnrichmentProgress.tsx`, `AiReviewPanel.tsx` -- existing enrichment UI components
- Codebase analysis: `backend/app/core/config.py` -- feature flag properties (`use_gemini`, `use_google_maps`, `use_enrichment`)
- Codebase analysis: `frontend/src/utils/api.ts` -- API client patterns, existing enrichment/AI API wrappers
- Codebase analysis: `backend/app/api/extract.py` lines 301-329 -- pipeline-status and enrich endpoints

### Secondary (MEDIUM confidence)
- `REQUIREMENTS.md` -- ENRICH-01 through ENRICH-09 requirement definitions
- `ROADMAP.md` -- Phase 7 scope and success criteria
- `STATE.md` -- Known blocker about concurrent enrichment button race conditions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, refactoring existing patterns
- Architecture: HIGH -- patterns derived directly from codebase analysis of 4 tool pages
- Pitfalls: HIGH -- derived from actual code issues observed (index-based exclusion, stale closures, export-from-original)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable -- internal codebase, no external dependency changes)
