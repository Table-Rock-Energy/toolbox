All 7 skill files written. Here's what changed:

**SKILL.md** — Narrowed `allowed-tools` to relevant Playwright tools only (removed irrelevant Gmail/Calendar/Netlify/HuggingFace/Notion). Tightened the quick-start to use actual grep commands against real files. Added the route graph.

**activation-onboarding.md** — Grounded in actual `App.tsx` route structure, `ProtectedRoute` auth flow, and `FileUpload` component. Identified the real missing `validationError` state and the Proration prereq-check pattern.

**engagement-adoption.md** — Based on actual Dashboard job-count code. Added cross-tool workflow sequence table (Extract → Title → Proration → Revenue → GHL). Documented the `useToolLayout` localStorage persistence hook.

**in-app-guidance.md** — Covers the 3 long operations (RRC download, revenue batch, GHL send via SSE). Shows prerequisite banner pattern for Proration. Documents post-export guidance gap.

**product-analytics.md** — Documents the actual Firestore job record schema. Provides shell + Python commands to analyze job data. Defines 4-step funnel per tool. Honest about what's missing.

**roadmap-experiments.md** — Proposes Firestore-based feature flags (minimal, fits the small allowlist model). Includes prioritized 4-phase improvement backlog with copyable checklist.

**feedback-insights.md** — Three concrete error patterns with exact file locations and fix code. Includes Cloud Run log commands for production debugging.