All three files rewritten. Here's what changed:

**SKILL.md** — Corrected the description from "Firebase Auth" to "Firestore collections, documents, and batch operations". Quick start examples now show the actual patterns from `firestore_service.py`: lazy `AsyncClient` init with module-level `_db`, batch writes, and the composite index fallback query.

**references/patterns.md** — Replaced Firebase Auth content with 7 Firestore-specific patterns grounded in the actual codebase:
- Lazy async client initialization (with the `database="tablerocktools"` named DB)
- Batch writes with the 500-doc limit + remainder check
- Deterministic document IDs via SHA-256 hash (revenue statements) and composite keys (RRC records)
- `get_all()` for batch reads (county status)
- Count aggregation queries (`.count()` vs fetching all docs)
- Composite index fallback (the actual try/except pattern from the codebase)
- Background thread sync client requirement

**references/workflows.md** — Replaced auth-focused workflows with 4 Firestore-specific workflows: job lifecycle, RRC sync, county status tracking, and adding a new collection.