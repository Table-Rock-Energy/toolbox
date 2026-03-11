All three skill files have been updated. Here's a summary of what changed:

**SKILL.md** — Rewrote with accurate patterns from the actual codebase:
- Corrected the active nav link pattern to include `border-l-4 border-tre-teal` (the real Sidebar.tsx pattern)
- Corrected the modal overlay to use `bg-tre-navy/60 backdrop-blur-sm` (not `bg-black/50`)
- Added the collapsible section `max-h-0/max-h-96` transition trick
- Added the status badge semantic color pattern
- Added the responsive layout (desktop sidebar + mobile drawer) pattern

**references/patterns.md** — Replaced generic examples with real component patterns:
- Sidebar active/collapsed/flyout patterns from actual `Sidebar.tsx`
- Modal overlay with correct `tre-navy/60` (not `black/50`)
- StatusBadge semantic color config from actual `StatusBadge.tsx`
- Updated anti-patterns: dynamic interpolation causing purge, wrong overlay color, and the `@apply` → React component solution

**references/workflows.md** — Added a "New Component Checklist" section at the top covering the key guardrails (token usage, Oswald font, mobile-first, transitions, focus rings, disabled states, dark sidebar contrast, purge safety).