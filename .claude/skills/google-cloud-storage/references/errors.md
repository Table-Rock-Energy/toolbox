# GCS Errors Reference

## Contents
- Initialization Failures
- Upload/Download Errors
- Signed URL Failures
- Production Fallback (Critical)
- Debugging Checklist

---

## Initialization Failures

### Missing Credentials (Local Dev — Expected)

```
WARNING: GCS initialization failed: Could not automatically determine credentials
INFO: GCS not available, using local storage
```

All operations fall back to `backend/data/`. This is **normal** in local dev and requires no fix.

To enable GCS locally:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Package Not Installed

```
WARNING: google-cloud-storage not installed, using local storage only
```

GCS_AVAILABLE flag is set to `False` at import time. Fix:
```bash
pip install google-cloud-storage
```

### Bucket Does Not Exist

```
WARNING: Failed to initialize GCS: 404 GET .../b/wrong-bucket: Not Found
```

```bash
# Check correct bucket name
gcloud storage buckets list --project=tablerockenergy

# Create if missing (one-time)
gcloud storage buckets create gs://table-rock-tools-storage \
  --project=tablerockenergy --location=us-central1
```

---

## Upload/Download Errors

### WARNING: download_file Returns None (Not Raises)

A common mistake from reading the old (incorrect) docs: `download_file()` returns `None` on miss, it does NOT raise `FileNotFoundError`.

```python
# BAD — NoneType crash, not FileNotFoundError
try:
    content = storage_service.download_file("missing.csv")
    df = pd.read_csv(io.BytesIO(content))  # TypeError: bytes-like object required
except FileNotFoundError:
    ...  # Never reached
```

```python
# GOOD — check for None
content = storage_service.download_file("rrc-data/oil_proration.csv")
if content is None:
    raise HTTPException(503, "RRC data not available — trigger a download first")
df = pd.read_csv(io.BytesIO(content))
```

### GCS Upload 403 Forbidden

```
WARNING: GCS upload failed, falling back to local storage: 403 Forbidden
INFO: Saved locally: backend/data/uploads/...
```

Service account lacks write permissions. Fix:
```bash
gcloud storage buckets add-iam-policy-binding gs://table-rock-tools-storage \
  --member="serviceAccount:table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### BinaryIO Stream Position After GCS Failure

When `upload_file(content=file_obj)` is called with a file-like object and GCS fails, `StorageService` calls `content.seek(0)` before the local fallback. But only if `hasattr(content, 'seek')`. If you're passing a non-seekable stream, convert to bytes first:

```python
# Safe — bytes, no seek needed
stored = storage_service.upload_file(
    content=await file.read(),  # bytes
    path="uploads/doc.pdf"
)

# Risky — file-like object, only works if seekable
stored = storage_service.upload_file(
    content=open("file.pdf", "rb"),  # BinaryIO
    path="uploads/doc.pdf"
)
```

---

## Signed URL Failures

### WARNING: Silent Frontend Failure

`get_signed_url()` returns `None`. If you pass this directly to the frontend, the download button silently does nothing.

```python
# BAD — null URL sent to frontend
return {"download_url": storage_service.get_signed_url(path)}

# GOOD — always fallback
url = storage_service.get_signed_url(path, expiration_minutes=30)
return {"download_url": url or f"/api/files/download?path={path}"}
```

### Signed URL Permission Error (Production)

```
google.api_core.exceptions.Forbidden: 403 Permission 'iam.serviceAccounts.signBlob' denied
```

Requires `roles/iam.serviceAccountTokenCreator` on the service account:
```bash
gcloud iam service-accounts add-iam-policy-binding \
  table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com \
  --member="serviceAccount:table-rock-tools-sa@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

---

## Production Fallback (Critical)

### WARNING: Local Fallback in Cloud Run = Data Loss

Cloud Run containers are ephemeral. Files written to the local filesystem are lost on container restart, new deployment, or scale-out. If you see this in production logs, it's a critical issue:

```
WARNING: GCS upload failed, falling back to local storage: 403 Forbidden
INFO: Saved locally: /app/backend/data/uploads/file.pdf
```

The user sees success, but the file disappears within minutes or hours.

**Detection:**
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND textPayload:\"falling back to local storage\"" \
  --project=tablerockenergy --limit=20
```

**Fix:** Restore GCS permissions (see Upload 403 above). Production should never fall back to local storage.

### Mixed Backend Scenario (Dev)

If Firestore has a file path reference that points to a file that only exists in production GCS, local dev will return `None` on download:

```bash
# One-time sync production GCS → local dev
gsutil -m cp -r gs://table-rock-tools-storage/rrc-data backend/data/
gsutil -m cp -r gs://table-rock-tools-storage/uploads backend/data/
```

---

## Debugging Checklist

Copy and track progress when GCS isn't working:

- [ ] Check `GOOGLE_APPLICATION_CREDENTIALS` env var is set and the JSON file exists
- [ ] Verify `GCS_BUCKET_NAME=table-rock-tools-storage` and `GCS_PROJECT_ID=tablerockenergy`
- [ ] Test bucket access: `gsutil ls gs://table-rock-tools-storage`
- [ ] Check IAM: service account needs `roles/storage.objectAdmin`
- [ ] For signed URLs: service account needs `roles/iam.serviceAccountTokenCreator`
- [ ] Check backend logs on startup for "Failed to initialize GCS" messages
- [ ] Upload a file via API, confirm it appears in GCS (not just local)
- [ ] In production: search Cloud Run logs for "falling back to local storage"

GCS issues are almost always credential or permission problems, not code bugs.
