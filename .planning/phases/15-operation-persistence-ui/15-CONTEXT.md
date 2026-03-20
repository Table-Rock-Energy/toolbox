# Phase 15: Operation Persistence UI - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Status bar UI in MainLayout showing active operations with progress, and auto-restore of completed results when user navigates back to a tool page. This is the user-facing persistence layer on top of Phase 13's OperationContext.

Requirements: PERSIST-02, PERSIST-03

</domain>

<decisions>
## Implementation Decisions

### Status Bar Design
- Thin bar rendered below the mobile header / above page content in MainLayout, inside OperationProvider but outside `<Outlet />`
- Shows tool name + current step + compact progress (e.g. "Extract: Clean Up 3/8") — single line, minimal height
- Clicking the status bar navigates to the tool page where the operation is running
- Clears when user views the tool page with completed results (triggers `clearOperation`)
- Only visible when an operation is running or completed but not yet viewed

### Auto-Restore Behavior
- When tool page mounts and `getResultsForTool(toolName)` returns data, auto-apply to preview state
- No recovery banner or user prompt — results apply silently (already decided in Phase 13 context)
- After auto-restore applies, `clearOperation()` is called so the status bar clears

### Visual Style
- Subtle `tre-teal` background with white text for active operations
- Animated pulse/shimmer when actively processing
- Green/success state briefly shown when operation completes, then auto-clears on next page visit
- Compact height (~32px) to not push content down significantly

### Claude's Discretion
- Status bar component implementation (inline in MainLayout vs separate component)
- Animation approach (CSS transitions vs Tailwind animate classes)
- How to detect "user has viewed results" (mount effect vs explicit interaction)
- Whether to show partial failure count in status bar or just in modal

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OperationContext.tsx` — Already has `operation.status`, `operation.tool`, `operation.batchProgress`, `operation.stepStatuses` for status bar data
- `useOperationState()` hook — Subscribes to operation state without re-renders from actions
- `getResultsForTool()` — Already checks if completed results exist for a given tool
- `useNavigate()` from React Router — For click-to-navigate on status bar

### Established Patterns
- Split context pattern (OperationStateContext + OperationActionsContext) prevents re-render storms
- Tool pages already call `getResultsForTool` in useEffect on mount for auto-restore
- `tre-teal` (#90c5ce) used for active/accent states across the app
- Mobile header pattern in MainLayout (bg-tre-navy with white text)

### Integration Points
- `MainLayout.tsx` line 74: OperationProvider wraps content — status bar goes between header and `<Outlet />`
- Tool pages (Extract, Title, Proration, Revenue): Already have `getResultsForTool` calls — may need to trigger `clearOperation` after applying
- `EnrichmentModal.tsx`: Status bar complements modal — bar shows when modal is closed (navigated away), modal shows when on the tool page

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard status bar pattern with existing OperationContext data.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-operation-persistence-ui*
*Context gathered: 2026-03-20*
