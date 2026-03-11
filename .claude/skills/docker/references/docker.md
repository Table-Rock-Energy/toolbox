# Docker Reference

## Contents
- Multi-Stage Build Architecture
- Image Size Optimization
- Port Configuration (Dev vs Prod)
- Health Checks
- Common Errors and Solutions
- Anti-Patterns

---

## Multi-Stage Build Architecture

The Dockerfile uses **two stages**: Node 20 for frontend build, Python 3.11 for runtime.

### DO: Minimal Runtime Image

```dockerfile
# GOOD - Only copy built artifacts to runtime
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --only=production=false  # Use ci for reproducible builds
COPY frontend/ ./
RUN npm run build  # Outputs to dist/

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app/ ./app/
COPY backend/data/ ./data/
# dist/ copied to /app/static — FastAPI serves from Path(__file__).parent.parent / "static"
COPY --from=frontend-builder /app/frontend/dist ./static
# Node toolchain is NOT in final image - saves ~200MB
```

**Why:** The final image only contains Python runtime + built static files. Node toolchain (~200MB) is discarded after build stage.

### DON'T: Single-Stage Build

```dockerfile
# BAD - Ships unnecessary build tools to production
FROM node:20
RUN apt-get update && apt-get install -y python3
COPY . .
RUN npm install && npm run build
RUN pip install -r requirements.txt
# Result: 1.2GB image with Node + Python + build tools
```

**Why This Breaks:** Wastes 400-600MB on unused Node toolchain and dev dependencies. Increases attack surface with unnecessary binaries.

---

## Image Size Optimization

### DO: Layer-Aware Caching

```dockerfile
# GOOD - Dependencies cached separately from source code
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt  # Cached layer
COPY backend/ ./backend/  # Source code changes don't invalidate pip cache
```

**Why:** `requirements.txt` changes less frequently than source code. Docker caches the pip install layer until requirements change.

### DON'T: Copy Everything First

```dockerfile
# BAD - Source code changes invalidate pip cache
COPY backend/ ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
# Any code change forces full pip reinstall
```

**Why This Breaks:** Every code change (even a typo fix) triggers a full `pip install`, wasting 2-5 minutes per build.

---

## Port Configuration (Dev vs Prod)

### Dev (docker-compose.yml)

```yaml
services:
  backend:
    ports:
      - "8000:8000"  # Host:Container
    command: uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
  
  frontend:
    ports:
      - "5173:5173"
    command: npm run dev -- --host 0.0.0.0
```

**Why:** Matches `make dev` ports. Vite dev server proxies `/api` to `http://localhost:8000`.

### Prod (Dockerfile)

```dockerfile
EXPOSE 8080  # Cloud Run default
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Why:** Cloud Run requires port 8080 (cannot be changed). Backend serves both API (`/api/*`) and static files (`/*`).

---

## Health Checks

### Dockerfile Health Check (Enabled)

```dockerfile
# Production Dockerfile — health check IS enabled
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1
```

**Why:** Cloud Run uses this to determine container health before routing traffic. The `start-period=5s` gives FastAPI time to start up.

**Testing locally:**
```bash
docker build -t test-image .
docker run -d -p 8080:8080 test-image
# After 5 seconds:
docker inspect --format='{{.State.Health.Status}}' $(docker ps -q)
# Expected: healthy
```

---

## Common Errors and Solutions

### Error: "Port 8080 is not defined"

**Symptom:** Cloud Run deployment fails with "Container failed to start"

**Cause:** `CMD` specifies wrong port (8000 instead of 8080)

**Fix:**
```dockerfile
# Before
CMD ["uvicorn", "backend.app.main:app", "--port", "8000"]

# After
CMD ["uvicorn", "backend.app.main:app", "--port", "8080"]
```

---

### Error: "Module not found: frontend/dist"

**Symptom:** FastAPI raises `StaticFiles` directory not found error

**Cause:** Multi-stage build didn't copy `dist/` from builder

**Fix:**
```dockerfile
# Ensure this line exists:
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
```

**Verify locally:**
```bash
docker build -t test-build .
docker run --rm test-build ls -la frontend/dist
```

---

### Error: "Database connection refused"

**Symptom:** Backend crashes with `asyncpg.exceptions.ConnectionRefusedError`

**Cause:** `DATABASE_URL` points to `localhost` instead of Docker service name

**Fix (docker-compose.yml):**
```yaml
backend:
  environment:
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/toolbox
    # NOT localhost - use service name 'db'
  depends_on:
    - db
```

---

## WARNING: Development Dependencies in Production

**The Problem:**

```dockerfile
# BAD - Installs dev dependencies in production
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt  # Includes pytest, ruff, etc.
```

**Why This Breaks:**
1. **Bloat:** Adds 50-100MB of unused testing/linting tools
2. **Security:** More dependencies = larger attack surface
3. **Startup Time:** More imports to validate on cold start

**The Fix:**

Split requirements into `requirements.txt` (prod) and `requirements-dev.txt` (dev only):

```dockerfile
# GOOD - Prod dependencies only
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
```

```bash
# Dev environment
pip install -r requirements.txt -r requirements-dev.txt
```

**Current State:** Table Rock Tools does NOT split requirements (all deps in production). This is acceptable for internal tools but violates best practices for public SaaS.

---

## WARNING: Missing .dockerignore

**The Problem:**

Without `.dockerignore`, `COPY backend/ ./backend/` includes:
- `__pycache__/` (500KB-2MB)
- `.pytest_cache/`
- `*.pyc` files
- `node_modules/` (if accidentally created in backend/)

**The Fix:**

Create `toolbox/.dockerignore`:

```
**/__pycache__
**/*.pyc
**/.pytest_cache
**/node_modules
.git
.env
.vscode
*.log
```

**Current State:** No `.dockerignore` exists. This wastes 1-3MB per build and risks leaking `.env` files.

---

## docker-compose Service Dependencies

### DO: Explicit depends_on with Health Checks

```yaml
services:
  db:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5
  
  backend:
    depends_on:
      db:
        condition: service_healthy  # Wait for pg_isready
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/toolbox
```

**Why:** Prevents race condition where backend starts before PostgreSQL is ready to accept connections.

### DON'T: Assume Service Availability

```yaml
# BAD - Backend may start before PostgreSQL is ready
services:
  backend:
    depends_on:
      - db  # Only waits for container start, not readiness
```

**Why This Breaks:** Backend crashes on startup with connection refused errors. Requires manual restart or retry logic.

**Current State:** `toolbox/docker-compose.yml` correctly uses `depends_on` with `condition: service_healthy` — waits for `pg_isready` before starting backend.