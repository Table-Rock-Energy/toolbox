# GCS Errors Reference

## Contents
- GCS Initialization Failures
- Upload/Download Errors
- Signed URL Failures
- Credential Issues
- Fallback Scenarios

---

## GCS Initialization Failures

### Missing Credentials

**Error:**
```
WARNING: GCS initialization failed: Could not automatically determine credentials, using local storage only
```

**Cause:** `GOOGLE_APPLICATION_CREDENTIALS` environment variable not set, or file doesn't exist.

**Impact:** All storage operations fall back to local filesystem (`backend/data/`).

**Fix (Local Development):**
```bash
# Download service account key from GCP Console
# IAM & Admin > Service Accounts > table-rock-tools-sa > Keys > Add Key > JSON

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Restart backend
make dev-backend
```

**Fix (Production/Cloud Run):**
No fix needed. Cloud Run uses Workload Identity (automatic authentication).

**When this is OK:** Local development without GCS is a valid use case. The warning is informational, not an error.

---

### Invalid Project ID

**Error:**
```
WARNING: GCS initialization failed: Invalid project ID: 'wrong-project', using local storage only
```

**Cause:** `GCS_PROJECT_ID` environment variable doesn't match actual GCP project.

**Fix:**
```bash
# Check GCP project ID
gcloud config get-value project
# Output: tablerockenergy

# Set correct project ID
export GCS_PROJECT_ID="tablerockenergy"
```

**Code location:**
```python
# backend/app/core/config.py
class Settings(BaseSettings):
    gcs_project_id: str = "tablerockenergy"  # Default is correct
```

---

### Bucket Does Not Exist

**Error:**
```
WARNING: GCS initialization failed: 404 GET https://storage.googleapis.com/storage/v1/b/wrong-bucket-name: Not Found
```

**Cause:** `GCS_BUCKET_NAME` doesn't exist or service account lacks permissions.

**Fix:**
```bash
# List accessible buckets
gcloud storage buckets list --project=tablerockenergy

# Create bucket if missing (one-time setup)
gcloud storage buckets create gs://table-rock-tools-storage \
  --project=tablerockenergy \
  --location=us-central1
```

**Permissions check:**
Service account needs `roles/storage.objectAdmin` on the bucket.

```bash
# Grant permission
gcloud storage buckets add-iam-policy-binding gs://table-rock-tools-storage \
  --member="serviceAccount:table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

---

## Upload/Download Errors

### WARNING: GCS Upload Failed, Falling Back to Local

**Log message:**
```
WARNING: GCS upload failed: 403 Forbidden, falling back to local storage
INFO: Uploaded to local storage: uploads/extract/file.pdf
```

**Cause:** Service account lacks write permissions to bucket.

**Impact:** File saved to `backend/data/uploads/extract/file.pdf` instead of GCS.

**Fix:**
```bash
# Check IAM permissions
gcloud storage buckets get-iam-policy gs://table-rock-tools-storage

# Should include:
# - serviceAccount:table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com
# - role: roles/storage.objectAdmin
```

**When this is expected:** Local dev without GCS credentials. Fallback is automatic and correct.

---

### FileNotFoundError on Download

**Error:**
```python
FileNotFoundError: File not found: uploads/missing.pdf
```

**Cause:** File doesn't exist in GCS or local storage.

**The Problem:**
```python
# BAD - Unhandled exception crashes the route
content = await storage.download_file("uploads/missing.pdf")
```

**The Fix:**
```python
# GOOD - Handle exception, return 404 to client
try:
    content = await storage.download_file(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    raise HTTPException(status_code=404, detail="File not found")
```

**Prevention pattern:**
```python
# Check existence first (avoids exception for control flow)
if not await storage.file_exists(file_path):
    raise HTTPException(status_code=404, detail="File not found")

content = await storage.download_file(file_path)
```

---

### Blob Does Not Exist (GCS-Specific)

**Error:**
```
WARNING: GCS download failed: Blob does not exist: uploads/file.pdf, trying local storage
```

**Cause:** File exists in local storage but not in GCS (or vice versa).

**Common scenario:**
1. Upload to GCS in production
2. Download local database backup to dev environment
3. Firestore has file path reference, but file only exists in production GCS
4. Local download fails with FileNotFoundError

**Fix (Development):**
Download production GCS files to local:
```bash
# One-time sync from production GCS to local dev
gsutil -m cp -r gs://table-rock-tools-storage/uploads backend/data/
gsutil -m cp -r gs://table-rock-tools-storage/rrc-data backend/data/
```

---

## Signed URL Failures

### WARNING: Signed URL Returns None

**Code:**
```python
signed_url = storage.get_signed_url("uploads/file.pdf")
# Returns: None
```

**Causes:**
1. GCS client not initialized (local dev without credentials)
2. Blob doesn't exist in GCS
3. Service account lacks `iam.serviceAccountTokenCreator` permission

**The Problem:**
```python
# BAD - Frontend gets null URL, download button fails silently
signed_url = storage.get_signed_url("exports/report.pdf")
return {"download_url": signed_url}  # May be None!
```

**Why This Breaks:**
Frontend receives:
```json
{"download_url": null}
```
Download button has `href={null}`, clicking does nothing. No error shown to user.

**The Fix:**
```python
# GOOD - Always provide fallback
signed_url = storage.get_signed_url("exports/report.pdf", expiration_minutes=30)

if signed_url:
    return {"download_url": signed_url}
else:
    # Serve via local API route
    return {"download_url": f"/api/files/download?path=exports/report.pdf"}
```

---

### Signed URL Permissions Error

**Error:**
```
google.api_core.exceptions.Forbidden: 403 Permission 'iam.serviceAccounts.signBlob' denied
```

**Cause:** Service account lacks permission to generate signed URLs.

**Fix:**
```bash
# Grant signBlob permission (one-time setup)
gcloud iam service-accounts add-iam-policy-binding \
  table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com \
  --member="serviceAccount:table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

**When this happens:** Production Cloud Run deployment with new service account.

---

## Credential Issues

### Default Credentials Not Found (Local Dev)

**Error:**
```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials. Please set GOOGLE_APPLICATION_CREDENTIALS or explicitly create credentials and re-run the application.
```

**Cause:** No service account key configured in local environment.

**Impact:** GCS initialization fails, all operations use local fallback.

**Fix:**
```bash
# Download service account key
# GCP Console > IAM & Admin > Service Accounts > Keys > Add Key > JSON

export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gcp-keys/table-rock-tools-sa.json"

# Add to shell profile for persistence
echo 'export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gcp-keys/table-rock-tools-sa.json"' >> ~/.zshrc
```

**Alternative (gcloud CLI):**
```bash
# Use your personal account for local dev (not recommended for production)
gcloud auth application-default login
```

---

### Workload Identity Issues (Cloud Run)

**Error (in Cloud Run logs):**
```
WARNING: GCS initialization failed: Unable to acquire impersonated credentials, using local storage only
```

**Cause:** Cloud Run service account not configured for Workload Identity.

**Fix:**
```bash
# Link Cloud Run service account to GCS
gcloud iam service-accounts add-iam-policy-binding \
  table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com \
  --role="roles/storage.objectAdmin" \
  --member="serviceAccount:tablerockenergy.svc.id.goog[default/table-rock-tools]"
```

**Deployment configuration:**
```yaml
# .github/workflows/deploy.yml
- name: Deploy to Cloud Run
  run: |
    gcloud run deploy table-rock-tools \
      --source . \
      --service-account=table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com \
      --region=us-central1
```

---

## Fallback Scenarios

### Expected Fallback (Local Dev)

**Log sequence:**
```
INFO: Starting FastAPI application...
WARNING: GCS initialization failed: Could not automatically determine credentials, using local storage only
INFO: Local storage directory: /Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox/backend/data
INFO: Application startup complete
```

**This is normal.** Local dev without GCS credentials is a supported workflow.

**Verification:**
```bash
# Upload a file via API
curl -X POST http://localhost:8000/api/extract/upload \
  -F "file=@test.pdf"

# Check local filesystem
ls backend/data/uploads/extract/
# Output: test.pdf
```

---

### Unexpected Fallback (Production)

**Log sequence (in Cloud Run):**
```
WARNING: GCS upload failed: 403 Forbidden, falling back to local storage
INFO: Uploaded to local storage: uploads/extract/file.pdf
```

**This is a problem.** Production should use GCS, not local filesystem.

**Why This Breaks:**
Cloud Run containers are **ephemeral**. Files saved to local filesystem are lost when:
- Container restarts
- New deployment
- Auto-scaling creates new instances

**Impact:** User uploads a file, gets a success message, but file disappears within minutes/hours.

**Fix:**
Check service account permissions (see "Bucket Does Not Exist" above).

**Monitoring:**
```bash
# Check Cloud Run logs for fallback warnings
gcloud logging read "resource.type=cloud_run_revision AND jsonPayload.message=~'falling back to local storage'" \
  --project=tablerockenergy \
  --limit=50
```

If fallback warnings appear in production, **this is a critical issue** requiring immediate fix.

---

### Partial Fallback (Mixed Backends)

**Scenario:**
1. File uploaded to GCS in production
2. Production database exported to local dev
3. Firestore has path reference: `"file_path": "uploads/file.pdf"`
4. Local dev tries to download → fails (file only in GCS)

**Error:**
```
FileNotFoundError: File not found: uploads/file.pdf
```

**Fix 1: Sync GCS to Local**
```bash
# One-time download of production files
gsutil -m cp -r gs://table-rock-tools-storage/uploads backend/data/
```

**Fix 2: Mock in Tests**
```python
# For unit tests, mock storage service
from unittest.mock import AsyncMock

async def test_download_file():
    storage = AsyncMock()
    storage.download_file = AsyncMock(return_value=b"mock content")
    
    content = await storage.download_file("uploads/file.pdf")
    assert content == b"mock content"
```

For testing patterns, see the **pytest** skill.

---

### Checklist: Debugging GCS Issues

Copy and track progress:

- [ ] Check `GOOGLE_APPLICATION_CREDENTIALS` is set and file exists
- [ ] Verify service account key is valid (not expired)
- [ ] Confirm `GCS_BUCKET_NAME` and `GCS_PROJECT_ID` are correct
- [ ] Test bucket access: `gsutil ls gs://table-rock-tools-storage`
- [ ] Check service account IAM permissions (`roles/storage.objectAdmin`)
- [ ] Review backend logs for "GCS initialization failed" warnings
- [ ] Test upload via API, check if file appears in GCS or local
- [ ] For signed URL issues, verify `roles/iam.serviceAccountTokenCreator` permission
- [ ] In production, check Cloud Run service account is linked to Workload Identity

**Iterate until all checks pass.** GCS issues are usually credential or permission related, not code bugs.