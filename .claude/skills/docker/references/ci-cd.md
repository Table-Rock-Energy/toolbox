# CI/CD Reference

## Contents
- GitHub Actions Deployment Pipeline
- Cloud Run Deployment Configuration
- Build Optimization
- Troubleshooting Failed Deployments
- Anti-Patterns

---

## GitHub Actions Deployment Pipeline

### Workflow File (.github/workflows/deploy.yml)

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  PROJECT_ID: tablerockenergy
  REGION: us-central1
  SERVICE_NAME: table-rock-tools

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - uses: google-github-actions/setup-gcloud@v2
        with:
          project_id: ${{ env.PROJECT_ID }}

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE_NAME }} \
            --source . \
            --project ${{ env.PROJECT_ID }} \
            --region ${{ env.REGION }} \
            --allow-unauthenticated \
            --memory 1Gi \
            --cpu 1 \
            --timeout 1200 \
            --min-instances 0 \
            --max-instances 10
```

**Key Points:**
- **Trigger:** Every push to `main` (no PR checks, no staging)
- **Authentication:** GitHub secret `GCP_SA_KEY` contains service account JSON
- **Build Location:** `--source .` triggers Cloud Build (automatic Dockerfile detection)
- **Resources:** 1 CPU, 1Gi RAM, 0-10 instances (autoscaling)

---

## Cloud Run Deployment Configuration

### Manual Deployment from Local Machine

```bash
cd toolbox
make deploy
```

**What it does:**
1. Runs `npm run build` (builds frontend to `dist/`)
2. Executes `gcloud run deploy` with `--source .` flag
3. Cloud Build:
   - Detects `Dockerfile`
   - Builds multi-stage image
   - Pushes to Artifact Registry (`us-central1-docker.pkg.dev/tablerockenergy/cloud-run-source-deploy/...`)
   - Deploys to Cloud Run

**Deployment time:** 3-5 minutes (2-3 min build, 1-2 min rollout)

---

## Build Optimization

### DO: Cache Docker Layers in Cloud Build

**Current limitation:** Cloud Run `--source` deployment does NOT cache Docker layers between builds. Every deployment rebuilds from scratch.

**Workaround (manual builds):**

```bash
# Pre-build and push to Artifact Registry
docker build -t us-central1-docker.pkg.dev/tablerockenergy/tools/app:latest .
docker push us-central1-docker.pkg.dev/tablerockenergy/tools/app:latest

# Deploy pre-built image
gcloud run deploy table-rock-tools \
  --image us-central1-docker.pkg.dev/tablerockenergy/tools/app:latest \
  --project tablerockenergy \
  --region us-central1
```

**Why:** Reusing cached layers cuts build time from 3 minutes to 30 seconds when only Python code changes.

**Trade-off:** Requires manual Docker build step. Loses convenience of `--source .` auto-build.

---

### DON'T: Run Tests in Dockerfile

```dockerfile
# BAD - Tests run on every production build
FROM python:3.11-slim
COPY backend/ ./backend/
RUN pip install -r backend/requirements.txt
RUN pytest backend/  # Fails build if tests fail
```

**Why This Breaks:**
1. **Slow:** Adds 30-60 seconds to every production build
2. **Fragile:** Flaky tests block deployments
3. **Wrong Place:** Tests belong in CI, not container build

**The Fix:** Run tests in GitHub Actions BEFORE deploying:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: cd toolbox/backend && pip install -r requirements.txt && pytest
  
  deploy:
    needs: test  # Only deploy if tests pass
    runs-on: ubuntu-latest
    steps:
      - # ... deploy steps
```

**Current State:** No test step in CI/CD. Tests run manually via `make test`.

---

## Troubleshooting Failed Deployments

### Error: "Service account does not have permission"

**Symptom:** GitHub Actions fails with `403 Forbidden` on `gcloud run deploy`

**Cause:** Service account lacks `roles/run.admin` permission

**Fix:**

```bash
# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding tablerockenergy \
  --member="serviceAccount:github-actions@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Also grant Storage Admin for Artifact Registry
gcloud projects add-iam-policy-binding tablerockenergy \
  --member="serviceAccount:github-actions@tablerockenergy.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

---

### Error: "Container failed to start"

**Symptom:** Deployment succeeds but service shows "Unhealthy"

**Debugging steps:**

1. **Check logs:**
```bash
gcloud run services logs read table-rock-tools \
  --project tablerockenergy \
  --region us-central1 \
  --limit 50
```

2. **Common causes:**
   - Port mismatch (not listening on 8080)
   - Missing environment variables
   - Python import errors
   - GCS/Firestore auth failures

3. **Test locally:**
```bash
docker build -t test-image .
docker run -p 8080:8080 \
  -e GCS_BUCKET_NAME=table-rock-tools-storage \
  -e FIRESTORE_ENABLED=true \
  test-image
curl http://localhost:8080/api/health
```

---

### Error: "Build exceeded time limit"

**Symptom:** Cloud Build fails after 10 minutes

**Cause:** npm install hangs, pip install downloads large packages, network issues

**Fix:**

```dockerfile
# Add timeouts and retry logic
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit --network-timeout=60000
```

**Alternative:** Pre-build and cache base images:

```dockerfile
# Use pre-built base image with dependencies
FROM us-central1-docker.pkg.dev/tablerockenergy/tools/python-base:latest
COPY backend/ ./backend/
# Skip pip install - already in base image
```

---

## WARNING: No Staging Environment

**The Problem:**

Every push to `main` deploys directly to production (`tools.tablerocktx.com`). No staging environment exists.

**Why This Breaks:**
1. **No Safe Testing:** Can't validate changes in prod-like environment
2. **Instant User Impact:** Bugs deploy immediately to live users
3. **Rollback Complexity:** Must redeploy previous commit or fix forward

**The Fix:**

Deploy to staging on PR, production on merge:

```yaml
on:
  pull_request:
    branches: [main]
  
jobs:
  deploy-staging:
    if: github.event_name == 'pull_request'
    steps:
      - run: |
          gcloud run deploy table-rock-tools-staging \
            --project tablerockenergy \
            --region us-central1
```

**Current State:** Table Rock Tools is an internal tool with 3-5 users. Direct-to-production deployment is acceptable but NOT a best practice.

---

## WARNING: Missing Rollback Strategy

**The Problem:**

If a bad deployment reaches production, the only rollback method is:

```bash
git revert <commit-hash>
git push origin main
# Wait 5 minutes for new deployment
```

**Why This Breaks:**
1. **Slow:** 5-minute rollback window
2. **Manual:** Requires developer intervention
3. **No Instant Revert:** Can't click "revert to previous revision" in UI

**The Fix:**

Cloud Run keeps previous revisions. Instant rollback:

```bash
# List revisions
gcloud run revisions list --service table-rock-tools --region us-central1

# Roll back to previous revision
gcloud run services update-traffic table-rock-tools \
  --to-revisions=table-rock-tools-00042-abc=100 \
  --region us-central1
```

**Better:** Add rollback button to GitHub Actions:

```yaml
on:
  workflow_dispatch:
    inputs:
      revision:
        description: 'Revision ID to deploy'
        required: true

jobs:
  rollback:
    steps:
      - run: |
          gcloud run services update-traffic table-rock-tools \
            --to-revisions=${{ github.event.inputs.revision }}=100
```

**Current State:** No automated rollback mechanism. Relies on git revert and redeploy.