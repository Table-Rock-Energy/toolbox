---
phase: quick
plan: 260319-ixh
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/pages/Proration.tsx
autonomous: true
requirements: [QUICK-260319-ixh]
must_haves:
  truths:
    - "RRC data status no longer appears as a full-width bar above the upload card"
    - "RRC data status appears inside the Upload Mineral Holders CSV card in both panel-expanded and panel-collapsed views"
    - "Page layout no longer shifts down when RRC status loads"
  artifacts:
    - path: "frontend/src/pages/Proration.tsx"
      provides: "Proration page with integrated RRC status"
  key_links: []
---

<objective>
Move the RRC data status notification from a standalone full-width row (lines 802-816) into the "Upload Mineral Holders CSV" upload card, so it doesn't push page content down.

Purpose: The full-width RRC status bar wastes vertical space and breaks the layout pattern used by other tool pages. Integrating it into the upload card keeps the page compact.
Output: Updated Proration.tsx with RRC status inside the upload card.
</objective>

<execution_context>
@/Users/yojimbo/.claude/get-shit-done/workflows/execute-plan.md
@/Users/yojimbo/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/pages/Proration.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Move RRC status into upload card in both panel states</name>
  <files>frontend/src/pages/Proration.tsx</files>
  <action>
1. **Remove** the standalone RRC status block (lines 802-816) — the `{/* RRC Data Status - informational only */}` section with its loading state and green status bar that sits between the header and the upload section.

2. **Add RRC status inside the panel-expanded upload card** (the `bg-white rounded-xl border` card starting around line 947 inside `{!panelCollapsed && ...}`). Place it as the first child inside the card div, ABOVE the `FileUpload` component and ABOVE the `showProcessingOptions` conditional. Use a compact inline layout:
   - When `rrcLoading`: show a small `animate-pulse` line with Database icon and "Loading RRC status..." text in gray
   - When loaded: show Database icon + record counts in a compact `text-xs` line, e.g. `"12,345 RRC records (8,000 oil, 4,345 gas)"` in green text
   - Use `mb-3` spacing below the status line to separate from the FileUpload component
   - No border/background needed — just an inline text line with the Database icon to keep it minimal inside the card

3. **Add the same RRC status into the panel-collapsed upload card** (the `bg-white rounded-xl border` card starting around line 820 inside `{panelCollapsed && !activeJob?.result && ...}`). Same placement — first child inside the card, above FileUpload, same compact styling.

4. Keep all existing RRC state variables (`rrcStatus`, `rrcLoading`, `checkRRCStatus`, etc.) and their useEffects unchanged — only the JSX rendering location changes.
  </action>
  <verify>
    <automated>cd /Users/yojimbo/Documents/dev/toolbox && npx tsc --noEmit --project frontend/tsconfig.app.json 2>&1 | head -20</automated>
  </verify>
  <done>RRC status bar no longer renders as a standalone full-width element. It appears as a compact line inside both the expanded and collapsed upload cards. TypeScript compiles without errors.</done>
</task>

</tasks>

<verification>
- `npx tsc --noEmit` passes
- Visually: no full-width green bar between header and content
- RRC record count visible inside the upload card area
</verification>

<success_criteria>
- RRC data status integrated into upload card in both panel states
- No standalone full-width RRC status bar
- Page content no longer pushed down by RRC status
- TypeScript compiles cleanly
</success_criteria>

<output>
After completion, create `.planning/quick/260319-ixh-move-rrc-data-status-notification-into-u/260319-ixh-SUMMARY.md`
</output>
