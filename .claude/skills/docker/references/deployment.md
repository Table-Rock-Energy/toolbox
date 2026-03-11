# Deployment Reference

## Contents
- Cloud Run Configuration
- Environment Variables
- Static File Serving
- Domain Mapping
- Scaling Configuration
- Common Deployment Issues

---

## Cloud Run Configuration

### Production Service Spec

```bash
gcloud run deploy table-rock-tools \
  --source . \
  --project tablerockenergy \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600s \
  --max-instances 10 \
  --min-instances 0 \
  --platform managed \
  --ingress all \
  --vpc-connector "" \
  --clear-vpc-connector
```

**Key Settings:**
- **CPU:** 1 vCPU (sufficient for FastAPI + pandas CSV processing)
- **Memory:** 1Gi (handles RRC data in-memory caching)
- **Timeout:** 600s (10 minutes for large PDF uploads)
- **Autoscaling:** 0-10 instances (scale to zero when idle)
- **Auth:** `--allow-unauthenticated` (Firebase Auth handles authentication in-app)

---

## Environment Variables

### Set via gcloud

```bash
gcloud run services update table-rock-tools \
  --update-env-vars \
    ENVIRONMENT=production,\
    FIRESTORE_ENABLED=true,\
    GCS_BUCKET_NAME=table-rock-tools-storage,\
    GCS_PROJECT_ID=tablerockenergy,\
    MAX_UPLOAD_SIZE_MB=50,\
    PORT=8080
```

**CRITICAL:** Do NOT set these via command line:
- `GOOGLE_APPLICATION_CREDENTIALS` - Cloud Run uses implicit service account auth
- `DATABASE_URL` - PostgreSQL is disabled in production (Firestore only)

### Secrets Management (Not Currently Used)

If storing Firebase Admin SDK key as secret:

```bash
# Create secret
echo -n "$(cat firebase-adminsdk-key.json)" | \
  gcloud secrets create firebase-admin-key --data-file=-

# Grant Cloud Run service account access
gcloud secrets add-iam-policy-binding firebase-admin-key \
  --member="serviceAccount:1234567890-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Mount in Cloud Run
gcloud run services update table-rock-tools \
  --update-secrets=/secrets/firebase-admin-key=firebase-admin-key:latest
```

**Current State:** No secrets used. Firebase Admin SDK auto-discovers credentials via Application Default Credentials (ADC).

---

## Static File Serving

### FastAPI Static Files Mount (backend/app/main.py)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# API routes (must be registered BEFORE static mount)
app.include_router(extract_router, prefix="/api/extract")
# ... other routers

# Static dir = /app/static (Dockerfile copies frontend/dist → ./static)
STATIC_DIR = Path(__file__).parent.parent / "static"  # /app/static
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
    # SPA routing handled by custom middleware (not a single mount)
```

**CRITICAL Order:**
1. API routes MUST be registered BEFORE static file mount
2. Static mount uses `html=True` to serve `index.html` for all unmatched routes (SPA routing)

**Why:** If static mount comes first, it intercepts `/api/*` requests and returns 404.

---

### Verify Static Files in Container

```bash
# Build locally
docker build -t test-deploy .

# Check dist/ exists
docker run --rm test-deploy ls -la static

# Expected output:
# drwxr-xr-x  index.html
# drwxr-xr-x  assets/
# drwxr-xr-x  vite.svg
```

**If missing:** Check `COPY --from=frontend-builder` line in Dockerfile.

---

## Domain Mapping

### Custom Domain: tools.tablerocktx.com

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service table-rock-tools \
  --domain tools.tablerocktx.com \
  --region us-central1

# Get DNS records to configure
gcloud run domain-mappings describe \
  --domain tools.tablerocktx.com \
  --region us-central1
```

**DNS Configuration (in domain registrar):**

```
CNAME  tools.tablerocktx.com  ghs.googlehosted.com.
```

**SSL Certificate:** Auto-provisioned by Cloud Run (Let's Encrypt). Takes 10-15 minutes after DNS propagation.

---

## Scaling Configuration

### Zero-Scaling Behavior

**Current:** `--min-instances 0` (scale to zero when idle)

**Trade-off:**
- **Cold start:** 3-10 seconds for first request after idle period
- **Cost savings:** $0 when idle (no traffic outside business hours)

**Alternatives:**

```bash
# Keep 1 instance warm (costs ~$10/month but eliminates cold starts)
gcloud run services update table-rock-tools --min-instances 1

# Keep warm during business hours only
gcloud run services update table-rock-tools --min-instances 0  # Default
# Use Cloud Scheduler to ping /api/health every 5 minutes 8am-6pm CT
```

---

### Request Concurrency

**Default:** 80 concurrent requests per instance

**Current workload:** 3-5 users, mostly synchronous uploads. Default is sufficient.

**If experiencing timeouts under load:**

```bash
# Increase concurrency (max 1000)
gcloud run services update table-rock-tools --concurrency 250

# OR reduce concurrency + increase max instances (more stable)
gcloud run services update table-rock-tools \
  --concurrency 40 \
  --max-instances 20
```

---

## Common Deployment Issues

### Error: "Revision failed health checks"

**Symptom:** Deployment succeeds but no traffic routes to new revision

**Debugging:**

```bash
# Check recent logs
gcloud run services logs read table-rock-tools --limit 100

# Common causes:
# 1. App not listening on PORT env var
# 2. /api/health endpoint returns non-200
# 3. App crashes on startup
```

**Fix for port mismatch:**

```python
# backend/app/main.py startup
import os
port = int(os.getenv("PORT", 8080))  # Read PORT env var
# Then run: uvicorn ... --port {port}
```

---

### Error: "Service account lacks permissions"

**Symptom:** GCS upload fails, Firestore writes fail in production

**Cause:** Cloud Run service account missing IAM roles

**Fix:**

```bash
# Get service account email
gcloud run services describe table-rock-tools --region us-central1 \
  --format "value(spec.template.spec.serviceAccountName)"

# Grant GCS permissions
gcloud projects add-iam-policy-binding tablerockenergy \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/storage.objectAdmin"

# Grant Firestore permissions
gcloud projects add-iam-policy-binding tablerockenergy \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/datastore.user"
```

---

### WARNING: No Deployment Previews

**The Problem:**

Every deployment is instant-live. No way to test deployment in prod-like environment before routing traffic.

**Why This Breaks:**
1. **Database Migrations:** Schema changes hit production DB immediately
2. **Frontend Bugs:** Broken UI deploys to all users instantly
3. **API Breaking Changes:** No gradual rollout

**The Fix (Gradual Rollout):**

```bash
# Deploy new revision without traffic
gcloud run deploy table-rock-tools --no-traffic --tag preview

# Get preview URL
gcloud run services describe table-rock-tools \
  --format "value(status.traffic[0].url)"
# Returns: https://preview---table-rock-tools-abc123.run.app

# Test preview URL manually, then route 10% traffic
gcloud run services update-traffic table-rock-tools \
  --to-revisions=table-rock-tools-00123-abc=10,LATEST=90

# If successful, route 100%
gcloud run services update-traffic table-rock-tools --to-latest
```

**Current State:** All deployments are instant 100% traffic. Acceptable for internal tools but NOT recommended for customer-facing apps.