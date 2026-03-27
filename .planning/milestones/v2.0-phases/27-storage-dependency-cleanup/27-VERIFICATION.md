---
phase: 27-storage-dependency-cleanup
verified: 2026-03-25T23:10:00Z
status: gaps_found
score: 5/7 must-haves verified
gaps:
  - truth: "All five tools process uploads and exports using local filesystem"
    status: partial
    reason: "AdminSettings.tsx has 13 TypeScript errors: GoogleCloudSettings type undefined, apiSettings/setApiSettings/apiSettingsApiKey/setApiSettingsApiKey all undeclared. Partial rename — state vars still named googleCloud/googleCloudApiKey but render references apiSettings/apiSettingsApiKey. The settings save handler and status indicator both reference undeclared names, causing runtime ReferenceErrors on save and initial render."
    artifacts:
      - path: "frontend/src/pages/AdminSettings.tsx"
        issue: "GoogleCloudSettings type undefined (line 88). apiSettings used on lines 634/636/661 but never declared. setApiSettings called on line 267 but never declared. apiSettingsApiKey used on lines 257-259/659/661 but never declared. setApiSettingsApiKey called on lines 268/660 but never declared. Declared googleCloudApiKey/setGoogleCloudApiKey never read (stale). ApiSettings interface declared but never used."
    missing:
      - "Rename state var: `const [googleCloud, setGoogleCloud]` -> `const [apiSettings, setApiSettings]`"
      - "Rename state var: `const [googleCloudApiKey, setGoogleCloudApiKey]` -> `const [apiSettingsApiKey, setApiSettingsApiKey]`"
      - "Replace `interface GoogleCloudSettings` with `interface ApiSettings` (already defined as ApiSettings at line 45) and remove duplicate"
      - "Remove unused `ApiSettings` interface declaration (line 45) after renaming the state type"

  - truth: "Zero stale GoogleCloudSettingsResponse references in test suite"
    status: failed
    reason: "test_pipeline.py line 501 imports GoogleCloudSettingsResponse from app.api.admin — name no longer exists, causes ImportError. The test body correctly uses ApiSettingsResponse but the import line was not updated. Running the test produces: ImportError: cannot import name 'GoogleCloudSettingsResponse' from 'app.api.admin'."
    artifacts:
      - path: "backend/tests/test_pipeline.py"
        issue: "Line 500-501: test description says GoogleCloudSettingsResponse and imports it, but that name was deleted. The test body uses ApiSettingsResponse correctly. The from-import on line 501 is the broken line."
    missing:
      - "Line 501: change `from app.api.admin import GoogleCloudSettingsResponse` to `from app.api.admin import ApiSettingsResponse`"
      - "Line 499-500: update test name and docstring from GoogleCloudSettingsResponse to ApiSettingsResponse"
---

# Phase 27: Storage Dependency Cleanup Verification Report

**Phase Goal:** App runs fully on-prem with zero Google cloud dependencies in code or requirements.txt
**Verified:** 2026-03-25T23:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | App starts with zero GCS warnings or errors in logs | VERIFIED | `from app.services.storage_service import storage_service` succeeds; no google.cloud imports in storage_service.py or config.py |
| 2 | All five tools process uploads and exports using local filesystem | PARTIAL | storage_service.py is clean; AdminSettings.tsx has 13 TypeScript errors from incomplete state variable rename (apiSettings/apiSettingsApiKey undeclared) — runtime ReferenceErrors on render/save |
| 3 | requirements.txt has zero google-* dependencies | VERIFIED | No google, firebase, or gcs entries found anywhere in backend/requirements.txt (65 lines) |
| 4 | GitHub Actions deploy workflow is disabled | VERIFIED | deploy.yml absent; deploy.yml.disabled confirmed present |
| 5 | Script reads all Firestore collections and writes to PostgreSQL tables | VERIFIED | 16 `def migrate_*` functions found; syntax valid; --help shows correct CLI |
| 6 | Script reports per-table row counts before and after migration | VERIFIED | "Migration Summary" table present; `--dry-run` flag confirmed in CLI |
| 7 | Script accepts service account JSON path as CLI argument | VERIFIED | `--service-account` and `--database-url` required args confirmed via --help |

**Score:** 5/7 truths verified (truth 2 is partial; separate implicit truth about test suite failing added below)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/storage_service.py` | Local-only storage service | VERIFIED | No GCS imports, no _init_client, no GCS methods. Uses settings.storage_rrc_data_folder, storage_uploads_folder, storage_profiles_folder. Python import succeeds. |
| `backend/app/core/config.py` | Config with no GCS defaults | VERIFIED | gcs_bucket_name, gcs_project_id, use_gcs all absent. gcp_project_id present for Firestore client (correct per plan decision). |
| `backend/requirements.txt` | Clean dependency list | VERIFIED | Zero google/firebase/gcs entries in 65-line file. |
| `backend/scripts/migrate_firestore_to_postgres.py` | One-time Firestore to PostgreSQL migration | VERIFIED | 928 lines, valid syntax, 16 migrate_ functions, argparse CLI, dry-run, Migration Summary table. |
| `frontend/src/pages/AdminSettings.tsx` | Updated to api-config endpoint | STUB | Fetch URLs updated to /admin/settings/api-config (correct), but state variable rename is incomplete — GoogleCloudSettings type undefined, apiSettings/apiSettingsApiKey undeclared, 13 TS errors. |
| `backend/tests/test_pipeline.py` | Updated model import | STUB | Test body uses ApiSettingsResponse correctly but still imports GoogleCloudSettingsResponse (deleted name) on line 501. Causes ImportError. |
| `.github/workflows/deploy.yml.disabled` | CI/CD disabled | VERIFIED | File present; deploy.yml absent. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/services/storage_service.py` | `backend/app/core/config.py` | `settings.data_dir` | VERIFIED | Line 80: `return settings.data_dir / path`. storage_* folder fields confirmed used (lines 156, 199, 240). |
| `backend/app/api/admin.py` | `backend/app/services/storage_service.py` | storage_service imports | VERIFIED | `ApiSettingsRequest`, `ApiSettingsResponse` models confirmed at lines 218/230. Endpoint `/settings/api-config` confirmed at lines 443/464. |
| `backend/scripts/migrate_firestore_to_postgres.py` | `backend/app/models/db_models.py` | SQLAlchemy model imports | VERIFIED | `from app.models.db_models import` confirmed at line 51. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `frontend/src/pages/AdminSettings.tsx` | apiSettings (render) | fetchApiSettings -> /admin/settings/api-config -> admin.py | Yes (real DB-backed config) | HOLLOW_PROP — fetch stores into setGoogleCloud but render reads apiSettings (undeclared). Data never reaches the render path. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| storage_service imports cleanly | `python3 -c "from app.services.storage_service import storage_service..."` | OK | PASS |
| Migration script syntax valid | `python3 -c "import ast; ast.parse(...)"` | Syntax OK | PASS |
| Migration script CLI works | `python3 scripts/migrate_firestore_to_postgres.py --help` | Correct usage output | PASS |
| Stale test import | `pytest tests/test_pipeline.py -k test_google_cloud_settings` | ImportError: cannot import name 'GoogleCloudSettingsResponse' | FAIL |
| TypeScript build (app config) | `npx tsc -p tsconfig.app.json --noEmit` | 13 errors in AdminSettings.tsx | FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| STOR-01 | 27-01 | Local filesystem is default storage — no GCS warnings or errors when GCS_BUCKET_NAME unset | SATISFIED | storage_service.py local-only, config has no gcs_bucket_name, Python import succeeds |
| STOR-02 | 27-01 | google-cloud-storage dependency and GCS-specific code paths removed from codebase | SATISFIED | No google-cloud-storage in requirements.txt; no google.cloud imports in any backend .py files |
| CLEAN-01 | 27-01 | All Google dependencies removed from requirements.txt (firebase-admin, google-cloud-firestore, google-cloud-storage, google-genai) | SATISFIED | Zero google/firebase entries in requirements.txt confirmed |
| DB-04 | 27-02 | One-time migration script exports all Firestore collections and imports into PostgreSQL (service account JSON as CLI arg) | SATISFIED | migrate_firestore_to_postgres.py: 16 collection handlers, argparse CLI with --service-account, dry-run mode, per-table summary |

All 4 declared requirements are satisfied. No orphaned requirements found for Phase 27 in REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/pages/AdminSettings.tsx` | 88 | `useState<GoogleCloudSettings>` — type undefined | Blocker | TypeScript error TS2304; runtime type mismatch |
| `frontend/src/pages/AdminSettings.tsx` | 634, 636, 661 | `apiSettings.has_key` — variable undeclared | Blocker | Runtime ReferenceError on render; settings status indicator broken |
| `frontend/src/pages/AdminSettings.tsx` | 267 | `setApiSettings(data)` — function undeclared | Blocker | Runtime ReferenceError after save; fetched data is lost |
| `frontend/src/pages/AdminSettings.tsx` | 257-259, 659-660 | `apiSettingsApiKey` / `setApiSettingsApiKey` — undeclared | Blocker | API key input field broken; save handler cannot read input value |
| `frontend/src/pages/AdminSettings.tsx` | 93 | `googleCloudApiKey` / `setGoogleCloudApiKey` declared but never read | Warning | Dead code from incomplete rename |
| `frontend/src/pages/AdminSettings.tsx` | 45 | `interface ApiSettings` declared but never used | Warning | Dead code (type used wrong name GoogleCloudSettings) |
| `backend/tests/test_pipeline.py` | 501 | `from app.api.admin import GoogleCloudSettingsResponse` — name deleted | Blocker | ImportError: test suite fails for this test |

### Human Verification Required

None — all gaps are code-level and verifiable programmatically.

### Gaps Summary

Two focused fixes needed:

**Gap 1 — AdminSettings.tsx incomplete rename (13 TS errors, runtime-broken)**

The state variable rename from `googleCloud`/`googleCloudApiKey` to `apiSettings`/`apiSettingsApiKey` was done in the render/handler code but not in the `useState` declarations. The result: render references 5 undeclared identifiers. The API key input field cannot be read or cleared. The status indicator throws ReferenceError on every render. Fetched data from the backend is stored into `setGoogleCloud` but render reads `apiSettings` — the two are disconnected.

Fix: Rename `const [googleCloud, setGoogleCloud]` to `const [apiSettings, setApiSettings]` and `const [googleCloudApiKey, setGoogleCloudApiKey]` to `const [apiSettingsApiKey, setApiSettingsApiKey]`. Also fix the type reference from `GoogleCloudSettings` to `ApiSettings` (already defined on line 45, so remove the duplicate).

**Gap 2 — test_pipeline.py stale import (ImportError)**

The test method at line 499 still imports `GoogleCloudSettingsResponse` which was deleted and replaced with `ApiSettingsResponse`. The test body uses `ApiSettingsResponse` correctly — only the import line and docstring were not updated. One-line fix.

---

_Verified: 2026-03-25T23:10:00Z_
_Verifier: Claude (gsd-verifier)_
