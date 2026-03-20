# Phase 15: Operation Persistence UI - Research

**Researched:** 2026-03-20
**Domain:** React UI — status bar component + auto-restore behavior
**Confidence:** HIGH

## Summary

This phase is purely frontend React/TypeScript work. The OperationContext (Phase 13) already provides all the state needed: `operation.tool`, `operation.status`, `operation.batchProgress`, `operation.stepStatuses`. The status bar reads this state and renders a compact indicator in MainLayout. Auto-restore already works on mount via `getResultsForTool()` — Phase 15 adds `clearOperation()` after restore so the status bar clears.

No new libraries needed. No backend changes. The entire phase is one new component (OperationStatusBar), placement in MainLayout, and small tweaks to the four tool pages' auto-restore useEffect blocks.

**Primary recommendation:** Create a standalone `OperationStatusBar.tsx` component that consumes `useOperationState()` and renders between the mobile header and `<Outlet />` in MainLayout. Tool pages call `clearOperation()` after auto-restore applies.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Thin bar rendered below the mobile header / above page content in MainLayout, inside OperationProvider but outside `<Outlet />`
- Shows tool name + current step + compact progress (e.g. "Extract: Clean Up 3/8") — single line, minimal height
- Clicking the status bar navigates to the tool page where the operation is running
- Clears when user views the tool page with completed results (triggers `clearOperation`)
- Only visible when an operation is running or completed but not yet viewed
- No recovery banner or user prompt — results apply silently
- After auto-restore applies, `clearOperation()` is called so the status bar clears
- Subtle `tre-teal` background with white text for active operations
- Animated pulse/shimmer when actively processing
- Green/success state briefly shown when operation completes, then auto-clears on next page visit
- Compact height (~32px) to not push content down significantly

### Claude's Discretion
- Status bar component implementation (inline in MainLayout vs separate component)
- Animation approach (CSS transitions vs Tailwind animate classes)
- How to detect "user has viewed results" (mount effect vs explicit interaction)
- Whether to show partial failure count in status bar or just in modal

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERSIST-02 | User sees active operation status bar in MainLayout header | OperationStatusBar component reads `useOperationState()` — all data already available in context |
| PERSIST-03 | User can return to a tool page and see results from an operation that completed while away | Auto-restore already works (PERSIST-01). Phase 15 adds `clearOperation()` call after restore to clear status bar |
</phase_requirements>

## Standard Stack

No new libraries. This phase uses only existing project dependencies.

### Core (already installed)
| Library | Purpose | Why |
|---------|---------|-----|
| React 19 | Component + hooks | Already in project |
| React Router v7 | `useNavigate()` for status bar click | Already in project |
| Tailwind CSS 3 | Styling + animation utilities | Already in project |
| Lucide React | Icons (Loader2, CheckCircle2, etc.) | Already in project |

### Alternatives Considered
None needed — no new dependencies for this phase.

## Architecture Patterns

### Component Placement

```
MainLayout.tsx
├── Sidebar (desktop)
├── Mobile Sidebar Overlay
└── <main>
    ├── Mobile Header (lg:hidden)
    ├── <OperationProvider>          ← status bar INSIDE here
    │   ├── <OperationStatusBar />   ← NEW: between provider and outlet
    │   └── <div className="p-4 lg:p-6">
    │       └── <Outlet />           ← tool pages render here
    │   </div>
    └── </OperationProvider>
```

**Key insight:** The status bar MUST be inside `<OperationProvider>` to access context, but OUTSIDE `<Outlet />` so it persists across page navigation. Current MainLayout already has this structure — the bar slots in between `<OperationProvider>` and the padding div.

### Pattern 1: Status Bar Component (separate file)

**Recommendation:** Separate `OperationStatusBar.tsx` component. Keeps MainLayout clean and the status bar testable/maintainable independently.

```typescript
// frontend/src/components/OperationStatusBar.tsx
import { useOperationState } from '../contexts/OperationContext'
import { useNavigate } from 'react-router-dom'

// Maps operation tool name → route path
const TOOL_ROUTES: Record<string, string> = {
  extract: '/extract',
  ecf: '/extract',
  title: '/title',
  proration: '/proration',
  revenue: '/revenue',
}

export default function OperationStatusBar() {
  const operation = useOperationState()
  const navigate = useNavigate()

  if (!operation || operation.status === 'idle') return null

  const handleClick = () => {
    const route = TOOL_ROUTES[operation.tool]
    if (route) navigate(route)
  }

  // Derive display text from batchProgress + stepStatuses
  const label = deriveLabel(operation)

  return (
    <div
      onClick={handleClick}
      className={/* conditional classes based on status */}
    >
      {label}
    </div>
  )
}
```

### Pattern 2: Auto-Restore with clearOperation

Current tool pages (Extract, Title, Proration, Revenue) all have this pattern:

```typescript
// Current (PERSIST-01)
useEffect(() => {
  const results = getResultsForTool(toolName)
  if (results) {
    setTimeout(() => {
      preview.updateEntries(results as PartyEntry[])
    }, 0)
  }
}, []) // eslint-disable-line react-hooks/exhaustive-deps
```

Phase 15 adds `clearOperation()` after restore:

```typescript
// Updated (PERSIST-03)
useEffect(() => {
  const results = getResultsForTool(toolName)
  if (results) {
    setTimeout(() => {
      preview.updateEntries(results as PartyEntry[])
      clearOperation() // Clear status bar after results applied
    }, 0)
  }
}, []) // eslint-disable-line react-hooks/exhaustive-deps
```

### Pattern 3: Animation with Tailwind

Tailwind 3 has built-in `animate-pulse` class. For a shimmer effect on the status bar during active processing, use a custom CSS animation or the built-in pulse:

```typescript
// Active: shimmer/pulse
className="animate-pulse bg-tre-teal/90 text-white"

// Completed: green brief flash
className="bg-emerald-500 text-white transition-colors duration-300"
```

No need for custom Tailwind config — `animate-pulse` is built in. For a more subtle shimmer, a small CSS keyframe in `index.css` is sufficient.

### Anti-Patterns to Avoid
- **Subscribing to OperationActionsContext in OperationStatusBar:** The status bar only READS state. Using `useOperationState()` (not `useOperationActions()`) avoids unnecessary re-renders when actions object changes.
- **Putting status bar outside OperationProvider:** It needs context access. Must be a child of `<OperationProvider>`.
- **Using local state to track "viewed":** The existing `clearOperation()` already handles this — no need for separate viewed/unviewed tracking.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress text formatting | Complex string builder | Simple template from `batchProgress` fields | `batchProgress.currentStep`, `currentBatch`, `totalBatches` already provided |
| Route mapping | Regex path parser | Static `TOOL_ROUTES` lookup object | Only 4-5 tools, static mapping is clearer |
| Animation | Custom JS animation | Tailwind `animate-pulse` + CSS transition | Built-in, no JS overhead |

## Common Pitfalls

### Pitfall 1: Re-render Storm from Status Bar
**What goes wrong:** Status bar subscribes to operation state, which updates every batch (dozens of times per operation). If MainLayout or Outlet re-render on each update, entire page thrashes.
**Why it happens:** Using `useOperationContext()` (which includes actions) instead of `useOperationState()` only.
**How to avoid:** OperationStatusBar uses ONLY `useOperationState()`. The split context pattern (Phase 13 decision) already prevents this — state changes don't trigger action consumers.
**Warning signs:** Visible lag or flicker during batch processing.

### Pitfall 2: Tool Name to Route Mismatch
**What goes wrong:** Clicking status bar navigates to wrong page or nowhere.
**Why it happens:** Tool names in operation context (`extract`, `ecf`, `title`, `proration`, `revenue`) don't map 1:1 to routes. `ecf` maps to `/extract`.
**How to avoid:** Explicit `TOOL_ROUTES` mapping with `ecf` -> `/extract` entry.
**Warning signs:** Click on status bar does nothing or goes to 404.

### Pitfall 3: clearOperation Called Too Early
**What goes wrong:** Status bar disappears before results are visible, or results flash then vanish.
**Why it happens:** `clearOperation()` called synchronously before `updateEntries` processes.
**How to avoid:** Call `clearOperation()` AFTER `updateEntries` in the same `setTimeout` callback (already the pattern — just add the call after).
**Warning signs:** Status bar flickers on tool page load.

### Pitfall 4: Status Bar Visible on the Active Tool Page
**What goes wrong:** User is on the Extract page watching the EnrichmentModal progress, and the status bar also shows above — redundant UI.
**Why it happens:** Status bar renders for any running operation regardless of current page.
**How to avoid:** Compare `operation.tool` with current route. If user is already on the tool's page, optionally hide the bar (since the modal is showing). Or keep it visible — it's subtle enough at 32px. This is a Claude's Discretion item.
**Warning signs:** Visual clutter with both modal and status bar showing same info.

## Code Examples

### Deriving Status Bar Label
```typescript
function deriveLabel(operation: OperationState): string {
  const toolLabel = operation.tool.charAt(0).toUpperCase() + operation.tool.slice(1)

  if (operation.status === 'completed') {
    return `${toolLabel}: Complete`
  }

  const bp = operation.batchProgress
  if (bp) {
    const stepLabel = bp.currentStep === 'cleanup' ? 'Clean Up'
      : bp.currentStep === 'validate' ? 'Validate'
      : 'Enrich'
    return `${toolLabel}: ${stepLabel} ${bp.currentBatch}/${bp.totalBatches}`
  }

  return `${toolLabel}: Processing...`
}
```

### MainLayout Integration
```typescript
// In MainLayout.tsx, inside <OperationProvider>:
<OperationProvider>
  <OperationStatusBar />
  <div className="p-4 lg:p-6">
    <Outlet />
  </div>
</OperationProvider>
```

### Tool-to-Route Mapping
```typescript
const TOOL_ROUTES: Record<string, string> = {
  extract: '/extract',
  ecf: '/extract',
  title: '/title',
  proration: '/proration',
  revenue: '/revenue',
}
```

## State of the Art

No changes from Phase 13. The split context pattern and OperationProvider are current and well-suited.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-page operation state | OperationContext above Router | Phase 13 (v1.7) | Enables this phase's status bar |

## Open Questions

1. **Show status bar on the active tool page?**
   - What we know: When user is on the tool page, the EnrichmentModal already shows progress
   - What's unclear: Is it redundant to also show the status bar?
   - Recommendation: Show it anyway — it's only 32px and provides consistency. The modal has detailed info; the bar is a quick glance indicator. If it feels noisy, hide when on the same page.

2. **Partial failure count in status bar?**
   - What we know: `batchProgress.failedBatches` is available
   - What's unclear: Whether to surface this in the compact bar or only in the modal
   - Recommendation: Only show failure info in modal. Status bar stays clean: tool + step + progress. If all batches fail, the status bar would show "Complete" and the modal shows the failure details.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | No frontend test framework configured |
| Config file | none |
| Quick run command | N/A |
| Full suite command | `make lint` (ESLint only) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERSIST-02 | Status bar shows active operations | manual-only | Visual verification: start operation, navigate away, confirm bar visible | N/A |
| PERSIST-03 | Results restore on return to tool page | manual-only | Visual verification: start operation, navigate away, return after completion | N/A |

**Justification for manual-only:** No frontend test framework exists (documented as out of scope). Both requirements are UI behaviors best verified by visual inspection. ESLint (`make lint`) validates TypeScript correctness.

### Sampling Rate
- **Per task commit:** `npx tsc --noEmit` (type check)
- **Per wave merge:** `make lint` (full lint)
- **Phase gate:** `make build` (production build succeeds)

### Wave 0 Gaps
None -- no test infrastructure to set up for this frontend-only phase. TypeScript compiler and ESLint are the verification tools.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `OperationContext.tsx` (448 lines) -- all state shapes, actions, hooks verified
- Direct code inspection of `MainLayout.tsx` (82 lines) -- OperationProvider placement confirmed at line 74
- Direct code inspection of all 4 tool pages (Extract, Title, Proration, Revenue) -- auto-restore pattern confirmed
- `tailwind.config.js` -- confirmed `tre-teal` color and no custom animations yet

### Secondary (MEDIUM confidence)
- Tailwind CSS 3 built-in `animate-pulse` -- standard Tailwind utility, well-documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing
- Architecture: HIGH -- direct code inspection, clear placement
- Pitfalls: HIGH -- derived from actual code patterns observed

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable -- no external dependencies)
