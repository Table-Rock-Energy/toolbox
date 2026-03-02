---
name: docker
description: |
  Manages multi-stage Docker builds (Node 20 → Python 3.11) and docker-compose services for Table Rock Tools.
  Use when: configuring container builds, managing dev/prod environments, debugging Docker issues, optimizing image size, setting up local PostgreSQL
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Docker Skill

Table Rock Tools uses a **multi-stage Dockerfile** (Node 20 build → Python 3.11 runtime) for production Cloud Run deployment, and **docker-compose** for local development with PostgreSQL. The production image serves the built React frontend via FastAPI's static file mounting on port 8080. Local dev uses separate services (frontend:5173, backend:8000, db:5432).

## Quick Start

### Multi-Stage Production Build

```dockerfile
# Stage 1: Node 20 - Build React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python 3.11 - Runtime
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
EXPOSE 8080
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Local Development with docker-compose

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: toolbox
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
  
  backend:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/toolbox
    ports:
      - "8000:8000"
    depends_on:
      - db
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Multi-stage build | Separate build and runtime environments | `FROM node:20 AS builder` → `FROM python:3.11` |
| Static file mounting | Serve React SPA from FastAPI | `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` |
| Health checks | Cloud Run readiness probes | `curl -f http://localhost:8080/api/health` |
| Port mapping | Dev vs prod port differences | Dev: 5173/8000, Prod: 8080 |

## Common Patterns

### Build and Deploy to Cloud Run

**When:** Deploying production changes (via CI/CD or manual)

```bash
# Manual deployment (from toolbox/)
make deploy

# Which runs:
npm run build  # Build frontend to dist/
gcloud run deploy table-rock-tools \
  --source . \
  --project tablerockenergy \
  --region us-central1 \
  --allow-unauthenticated
```

### Local Dev with Hot Reload

**When:** Developing locally without Docker overhead

```bash
make dev  # Runs frontend + backend separately (no Docker)
```

### Local Dev with PostgreSQL

**When:** Testing PostgreSQL integration (disabled by default)

```bash
make docker-up    # Start all services
make docker-logs  # Stream logs
make docker-down  # Stop and remove containers
```

## See Also

- [docker](references/docker.md) - Multi-stage builds, optimization, troubleshooting
- [ci-cd](references/ci-cd.md) - GitHub Actions deployment pipeline
- [deployment](references/deployment.md) - Cloud Run configuration and deployment
- [monitoring](references/monitoring.md) - Health checks, logging, debugging

## Related Skills

- **fastapi** - Backend app configuration, static file mounting
- **python** - Runtime dependencies, requirements.txt management
- **vite** - Frontend build process, dev server proxy
- **node** - npm dependencies, frontend build stage

## Documentation Resources

> Fetch latest Docker documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "docker"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/websites/docs.docker.com` _(resolve using mcp__plugin_context7_context7__resolve-library-id)_

**Recommended Queries:**
- "docker multi-stage builds best practices"
- "docker compose healthcheck configuration"
- "optimize docker image size python node"