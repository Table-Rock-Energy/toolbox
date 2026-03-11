The skill files are updated. Here's a summary of what changed and what's in each file:

**SKILL.md** — Rewritten to reflect actual codebase patterns:
- Uses `validate_upload()` and `file_response()` from `core/ingestion.py` (the real shared helpers)
- Uses `persist_job_result()` for job tracking
- Added SSE streaming endpoint pattern (used in `ghl.py`)
- Added "New Tool Checklist" for building new tools from scratch
- Removed the legacy inline validation boilerplate

**references/routes.md** — Updated two sections:
- File upload now shows `validate_upload()` instead of manual inline checks
- Export now shows `file_response()` instead of manual `Response()` construction

The other three reference files (`services.md`, `database.md`, `auth.md`, `errors.md`) were already comprehensive and accurate — they correctly document the actual patterns in the codebase including the lazy GCS init, Firestore batching (500-doc limit), Firebase allowlist, and the `success=False` vs `HTTPException` distinction.