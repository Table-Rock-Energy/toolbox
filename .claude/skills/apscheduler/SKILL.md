All three files have been rewritten with accurate, codebase-grounded content. Here's what changed and why:

**Key correction:** The previous SKILL.md documented APScheduler as the active scheduler — it's not. It was removed because Cloud Run scales to 0. The skill now leads with this fact prominently.

**SKILL.md** — Rewritten to:
- Open with a clear WARNING that APScheduler was removed
- Document the actual current pattern: GitHub Actions cron + `threading.Thread`
- Show the critical `_get_sync_firestore_client()` pattern for background threads
- Still document APScheduler usage for non-Cloud-Run deployments

**references/patterns.md** — Rewritten to:
- Explain the Cloud Run scaling-to-zero problem with the actual `main.py` comment as evidence
- Document the `threading.Thread` + `daemon=True` pattern from `rrc_background.py`
- Cover the sync-vs-async Firestore client split (most common gotcha)
- Cover `asyncio.run()` bridging from sync threads to async functions
- Include the Firestore job state schema
- Keep APScheduler patterns in a clearly-labeled non-Cloud-Run section

**references/workflows.md** — Rewritten to:
- Provide a complete checklist for adding a new background job using the current pattern
- Include a full template `*_background.py` that follows the existing `rrc_background.py` structure
- Cover debugging via Firestore document inspection + Cloud Run logs
- Include the job state machine diagram showing valid transitions
- Keep the APScheduler workflow for non-Cloud-Run deployments