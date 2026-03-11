All corrections made. Here's what changed and why:

**`SKILL.md`**
- "four document-processing tools" → "five document-processing tools" (GHL Prep exists in the codebase)

**`engagement-adoption.md`**
- Replaced the incorrect "BAD: Static counts" / "GOOD: Fetch from analytics API" pattern — `Dashboard.tsx` already fetches from `/api/history/jobs` and aggregates dynamically. The example now shows the real code and notes the limitation (last 50 jobs, no rolling window), then shows how to add a dedicated analytics endpoint if per-period breakdowns are needed
- `len(tools) == 4` → `len(tools) == 5` in the retention query (5 tools now)

**`product-analytics.md`**
- Added `"ghl_prep"` to the `Literal` type in `UsageEvent.tool` — previously the type excluded GHL Prep entirely, which would cause a Pydantic validation error when tracking GHL Prep usage events