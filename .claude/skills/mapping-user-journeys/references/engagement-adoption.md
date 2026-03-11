# Engagement & Adoption Reference

## Contents
- Measuring Tool Adoption via Job History
- Dashboard as Re-engagement Surface
- Cross-Tool Workflow Handoffs
- Repeat Use Patterns
- WARNING: Adoption Gaps

---

## Measuring Tool Adoption via Job History

`GET /api/history/jobs` is the only adoption signal. Dashboard fetches the last 50 jobs and builds per-tool counts:

```typescript
// frontend/src/pages/Dashboard.tsx
useEffect(() => {
  fetch(`${API_BASE}/history/jobs?limit=50`)
    .then(r => r.json())
    .then(data => {
      const counts: Record<string, number> = {};
      for (const job of data.jobs || []) {
        counts[job.tool] = (counts[job.tool] || 0) + 1;
      }
      setToolCounts(counts);  // Shown as "X times used" on each tool card
    });
}, []);
```

Tool cards render `toolCounts[tool.tool] || 0` as the usage counter. A tool showing `0` is visually identical to one with 50 uses — no urgency or call-to-action to try it.

**GOOD - Surface zero-use tools with a nudge:**
```typescript
{toolCounts[tool.tool] === 0 && (
  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
    Not yet used
  </span>
)}
```

---

## Dashboard as Re-engagement Surface

The Recent Activity table navigates to the relevant tool on row click:

```typescript
// pages/Dashboard.tsx
<tr onClick={() => navigate(toolPaths[job.tool] || '/')}>
```

This returns the user to the tool page but restores no state. The user must re-upload to repeat work.

**GOOD - "Resume last job" link per tool card:**
```typescript
// Requires storing last job_id in localStorage after processing
const lastJobId = localStorage.getItem(`last-job-${tool.tool}`);
{lastJobId && (
  <button
    onClick={() => navigate(`${tool.path}?resume=${lastJobId}`)}
    className="text-xs text-tre-teal underline mt-1"
  >
    Resume last session
  </button>
)}
```

---

## Cross-Tool Workflow Handoffs

Tools form a natural sequence that the UI doesn't surface:

| Step | Tool | Typical Next |
|------|------|-------------|
| 1 | Extract | Title (ownership verification) |
| 2 | Title | Proration or GHL Prep |
| 3 | Proration | Revenue (verify payments match NRA) |
| 4 | GHL Prep | GHL send (bulk import) |

**GOOD - Post-export next-step suggestion:**
```typescript
// After Extract CSV export
{exportComplete && (
  <div className="mt-4 p-4 bg-tre-teal/10 rounded-xl border border-tre-teal/20">
    <p className="text-sm font-semibold text-tre-navy">What's next?</p>
    <p className="text-sm text-gray-600 mt-1">
      Verify ownership for these parties using the Title tool.
    </p>
    <button
      onClick={() => navigate('/title')}
      className="mt-2 text-sm text-tre-teal font-medium hover:underline"
    >
      Open Title Tool →
    </button>
  </div>
)}
```

---

## Repeat Use Patterns

`useToolLayout` persists panel collapse state per user per tool in `localStorage`:

```typescript
// frontend/src/hooks/useToolLayout.ts
const panelKey = `${PANEL_COLLAPSED_PREFIX}-${tool}-${uid}`;
const [panelCollapsed, setPanelCollapsed] = useState(() =>
  localStorage.getItem(panelKey) === 'true'
);
```

Column visibility is also persisted per user. These preferences make repeat workflows faster — but there's no in-app discovery mechanism for the panel toggle or column customization.

---

## WARNING: Adoption Gaps

**No cross-session result persistence.** Users who upload a 300-row extract and close the tab lose all results. Firestore stores job metadata but tool pages don't re-hydrate results from a `job_id` on mount. This is the highest-impact repeat-use friction point.

**No per-tool success rate visible.** The `success_count`/`error_count` fields on `RecentJob` exist but aren't surfaced on the Dashboard. A batch with 60% errors reads identically to 0% errors.

**No workflow sequencing cues.** Users who don't know the Extract → Title → Proration sequence will use tools in isolation and miss the compound value.

For instrumentation of engagement events, see the **instrumenting-product-metrics** skill.
For designing adoption nudges, see the **orchestrating-feature-adoption** skill.
