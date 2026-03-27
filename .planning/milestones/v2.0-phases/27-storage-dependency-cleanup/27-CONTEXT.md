# Phase 27: Storage & Dependency Cleanup - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Make local filesystem the default storage (no GCS warnings). Remove google-cloud-storage dependency and GCS code paths. Create one-time Firestore→PostgreSQL migration script. Remove ALL remaining Google dependencies from requirements.txt. Disable GitHub Actions CI/CD workflow (no auto-deploy to Cloud Run). App starts and serves all 5 tools with only PostgreSQL, local filesystem, and optionally LM Studio.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — final cleanup phase.

Key items:
- Default gcs_bucket_name to None in config.py (was "table-rock-tools-storage")
- Default gcs_project_id to None (was "tablerockenergy")
- Suppress GCS warnings in storage_service.py (change logger.info to logger.debug or remove)
- Remove google-cloud-storage from requirements.txt
- Remove GCS-specific code paths in storage_service.py (keep local filesystem logic)
- Migration script: backend/scripts/migrate_firestore_to_postgres.py — CLI arg for service account JSON
- Disable .github/workflows/deploy.yml (rename to deploy.yml.disabled or delete)
- Final check: zero google-* packages in requirements.txt
- Do NOT touch Dockerfile or docker-compose files

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/storage_service.py` — has local fallback already, GCS is primary path to remove
- `backend/app/core/config.py` — GCS settings to default to None
- `backend/requirements.txt` — remaining Google deps to remove
- `.github/workflows/deploy.yml` — CI/CD to disable

### Integration Points
- storage_service.py is used by all tools for file uploads/downloads
- config.py GCS settings affect storage_service behavior
- deploy.yml triggers on push to main

</code_context>

<specifics>
## Specific Ideas

User requirement: "we don't want to push from github to gcloud" — disable CI/CD workflow.
Migration script takes service account JSON key path as CLI arg, exports ALL Firestore collections, imports to PostgreSQL with count verification.

</specifics>

<deferred>
## Deferred Ideas

None — final phase.

</deferred>
