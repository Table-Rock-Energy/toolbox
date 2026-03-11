# Technology Stack

**Analysis Date:** 2026-03-10

## Languages

**Primary:**
- TypeScript ~5.9.3 - Frontend SPA (`frontend/src/`)
- Python 3.11+ - Backend API (`backend/app/`)

**Secondary:**
- CSS (Tailwind utility classes) - Styling (`frontend/src/index.css`, inline classes)
- SQL - Optional PostgreSQL queries via SQLAlchemy (`backend/app/core/database.py`)

## Runtime

**Environment:**
- Node.js 20+ (build + dev server)
- Python 3.11 (production runtime, specified in `Dockerfile`)
- Uvicorn (ASGI server for FastAPI)

**Package Manager:**
- npm (frontend) - Lockfile: `frontend/package-lock.json`
- pip (backend) - No lockfile, pinned with `>=` constraints in `backend/requirements.txt`

## Frameworks

**Core:**
- React 19.2.x - SPA frontend (`frontend/package.json`)
- FastAPI 0.109+ - Async Python API (`backend/requirements.txt`)
- React Router 7.13.x - Client-side routing with nested routes (`frontend/src/App.tsx`)
- Pydantic 2.5+ / pydantic-settings 2.1+ - Request/response models + config (`backend/app/core/config.py`, `backend/app/models/`)

**Testing:**
- Pytest 7.4+ - Backend test runner (`backend/requirements.txt`)
- pytest-asyncio 0.23+ - Async test support
- httpx 0.26+ - Async HTTP test client for FastAPI

**Build/Dev:**
- Vite 7.2.x - Frontend dev server + production bundler (`frontend/vite.config.ts`)
- @vitejs/plugin-react 5.1.x - React fast refresh
- PostCSS 8.5.x + Autoprefixer 10.4.x - CSS processing pipeline
- Tailwind CSS 3.4.x - Utility-first CSS (`frontend/tailwind.config.js`)
- Ruff 0.1+ - Python linting (`backend/`)
- ESLint 9.39.x + typescript-eslint 8.46.x - TypeScript linting (`frontend/`)

## Key Dependencies

**Critical (Frontend):**
- `firebase` 12.9.x - Firebase Auth client SDK (Google Sign-In + email/password) (`frontend/src/lib/firebase.ts`)
- `lucide-react` 0.563.x - Icon library used throughout UI
- `react-router-dom` 7.13.x - All page routing and protected routes

**Critical (Backend):**
- `pandas` 2.1+ - Core data processing for all tools (CSV/Excel parsing, in-memory caching for RRC data)
- `pymupdf` 1.23+ - Primary PDF text extraction (Extract, Revenue tools)
- `pdfplumber` 0.10+ - Fallback PDF extraction
- `reportlab` 4.0+ - PDF generation (proration exports)
- `google-cloud-firestore` 2.14+ - Primary database (`backend/app/services/firestore_service.py`)
- `google-cloud-storage` 2.14+ - File storage with local fallback (`backend/app/services/storage_service.py`)
- `firebase-admin` 6.2+ - Server-side auth token verification (`backend/app/core/auth.py`)

**Infrastructure (Backend):**
- `uvicorn[standard]` 0.27+ - ASGI server
- `python-multipart` 0.0.6+ - File upload parsing
- `requests` 2.31+ - Synchronous HTTP for RRC data downloads
- `httpx` 0.26+ - Async HTTP client for GHL API and enrichment providers
- `sse-starlette` 2.0+ - Server-Sent Events for progress streaming
- `beautifulsoup4` 4.12+ / `lxml` 4.9+ - HTML parsing for RRC data
- `openpyxl` 3.1+ - Excel file read/write
- `cryptography` 42.0+ - Fernet encryption for API key storage
- `phonenumbers` 8.13+ - Phone number parsing/normalization (GHL integration)

**Optional (Backend):**
- `google-genai` 1.0+ - Gemini AI validation (`backend/app/services/gemini_service.py`)
- `sqlalchemy[asyncio]` 2.0+ / `asyncpg` 0.29+ / `alembic` 1.13+ - PostgreSQL (disabled by default)
- `apscheduler` 3.10+ - Listed in requirements but removed from runtime (Cloud Run scales to 0)
- `pytesseract` 0.3.10+ / `pdf2image` 1.16+ / `pillow` 10.0+ - OCR support for revenue tool
- `psycopg2-binary` 2.9+ - PostgreSQL sync driver (for Alembic migrations)

## Configuration

**Environment:**
- Pydantic Settings loads from `.env` file and environment variables (`backend/app/core/config.py`)
- `.env` files exist but are not committed (no `.env.example` provided)
- All settings have sensible defaults; only GCP credentials needed for full functionality
- Feature flags control optional services: `GEMINI_ENABLED`, `ENRICHMENT_ENABLED`, `GOOGLE_MAPS_ENABLED`, `DATABASE_ENABLED`
- Firebase config is hardcoded in `frontend/src/lib/firebase.ts` (project: `tablerockenergy`)

**Build:**
- `frontend/vite.config.ts` - Vite config with `/api` proxy to `localhost:8000`
- `frontend/tsconfig.app.json` - TypeScript strict mode, target ES2022, bundler module resolution
- `frontend/tailwind.config.js` - Custom `tre-*` brand colors, Oswald font
- `Makefile` - All dev/build/deploy commands
- `Dockerfile` - Multi-stage build (Node 20 frontend build + Python 3.11 runtime)

**TypeScript Config:**
- Strict mode enabled with `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`
- Target: ES2022, JSX: react-jsx
- `verbatimModuleSyntax: true` - Requires `type` keyword for type-only imports

## Platform Requirements

**Development:**
- Node.js 20+
- Python 3.11+
- `make` for command orchestration
- Docker + Docker Compose (optional, for PostgreSQL)
- macOS note: Use `python3` not `python`

**Production:**
- Google Cloud Run (us-central1)
- GCP project: `tablerockenergy`
- Container: Python 3.11-slim with system deps (poppler-utils, tesseract-ocr, curl)
- Resources: 1 CPU, 1Gi memory, 1200s timeout, 0-10 instances
- Port: 8080 (Cloud Run default)
- Health check: `GET /api/health` every 30s

**CI/CD:**
- GitHub Actions (`.github/workflows/deploy.yml`)
- Trigger: push to `main` or manual dispatch
- Uses `google-github-actions/auth@v2` + `setup-gcloud@v2`
- Deploys via `gcloud run deploy --source .` (Cloud Build on GCP side)

---

*Stack analysis: 2026-03-10*
