All 7 files rewritten. Here's what changed and why:

**SKILL.md**
- Added GHL Prep as the 5th tool (was missing)
- Fixed `track_event` to be fire-and-forget with try/except (analytics should never crash the app)
- Fixed `datetime.utcnow()` → `datetime.now(tz=timezone.utc)` (utcnow is naive/deprecated)
- Streamlined allowed-tools (removed irrelevant MCP tools from a metrics skill)

**activation-onboarding.md**
- Fixed critical bug: original code called `len(list(signups))` twice — the async generator is exhausted after the first iteration, second call always returns 0
- Fixed `localStorage` for first-upload detection → replaced with Firestore jobs query (persistent, cross-device)
- Batched Firestore `in` queries properly (10-item limit)
- Added GHL Prep to Proration gate tracking

**product-analytics.md**
- Fixed `datetime.utcnow()` → `datetime.now(tz=timezone.utc)` throughout
- Fixed funnel query to batch `in` operator in chunks of 10
- Added GHL Prep to the tool union type

**feedback-insights.md**
- Fixed **security vulnerability**: raw `str(e)` was being returned to clients in HTTP 500 responses, leaking internal paths and implementation details. Now logs internally and returns a sanitized message.
- Added `Field(pattern=...)` validation on feedback category
- Truncated component stack in error boundary to 500 chars (avoids large payloads)

**engagement-adoption.md** / **in-app-guidance.md** / **roadmap-experiments.md**
- Fixed `datetime.utcnow()` → `datetime.now(tz=timezone.utc)`
- Batched Firestore `in` queries where missing
- Minor cleanup and accuracy improvements