All three corrections are done. Here's a summary of what was updated:

**Files already existed** — the skill was previously generated. I corrected three factual inaccuracies grounded in reading the actual source code:

| File | What was wrong | What was fixed |
|------|---------------|----------------|
| `SKILL.md` | "Job history NOT yet displayed in UI" | Dashboard already fetches and shows recent jobs at `Dashboard.tsx:104-123`; corrected description + noted actual gap (missing CTA in empty state) |
| `references/activation-onboarding.md` | Used `recentActivity` variable (doesn't exist), line number wrong (`127` vs `196`) | Fixed to `recentJobs` and correct line `196-201` matching actual code |
| `references/engagement-adoption.md` | "Static usage counts hardcoded to 0" | Usage counts are already dynamic — corrected with the actual `toolCounts` implementation from `Dashboard.tsx:104-123` |

The remaining 4 reference files (`in-app-guidance.md`, `product-analytics.md`, `roadmap-experiments.md`, `feedback-insights.md`) were factually accurate and substantive — no changes needed.