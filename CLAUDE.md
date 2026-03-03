# Table Rock Tools

Consolidated internal web application for Table Rock Energy. Provides five document-processing tools used by land and revenue teams: Extract (OCC Exhibit A party extraction), Title (title opinion consolidation), Proration (mineral holder NRA calculations with RRC data), Revenue (revenue statement to M1 CSV conversion), and GHL Prep (Mineral export transformation for GoHighLevel import).

## Claude Permissions

- Git commits, pushes to `main`, and GitHub operations are allowed
- Deploying to Google Cloud Run (via `git push` triggering CI/CD) is allowed
- Running `npx tsc`, `python3` syntax checks, and build commands is allowed
- Use `python3` not `python` on macOS (python command does not exist)

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Frontend | React | 19.x | SPA with protected routes |
| Build | Vite | 7.x | Dev server with API proxy to backend |
| Language (FE) | TypeScript | 5.x | Strict mode enabled with comprehensive linting |
| Styling | Tailwind CSS | 3.x | Utility-first with custom `tre-*` brand colors |
| Icons | Lucide React | 0.x | Consistent icon set |
| Auth | Firebase Auth | 12.x | Google Sign-In + email/password |
| Backend | FastAPI | 0.x | Async Python API |
| Validation | Pydantic | 2.x | Request/response models with Settings management |
| Data | Pandas | 2.x | CSV/Excel processing with in-memory caching |
| PDF Read | PyMuPDF + PDFPlumber | - | Primary + fallback PDF text extraction |
| PDF Write | ReportLab | 4.x | PDF generation (proration exports) |
| Database | Firestore | - | Primary persistence (jobs, entries, RRC data) |
| Storage | Google Cloud Storage | - | File storage with local filesystem fallback |
| Database (opt) | PostgreSQL + SQLAlchemy | - | Optional relational DB (disabled by default) |
| Scheduler | APScheduler | 3.x | Monthly RRC data downloads |
| AI (opt) | Google Gemini | 2.x | Optional AI-powered data validation |
| Enrichment (opt) | PDL + SearchBug | - | Optional contact enrichment services |
| Integration | GoHighLevel API | - | Bulk contact import with SSE progress tracking |
| Linting | Ruff + ESLint | - | Python backend + TypeScript frontend |
| Testing | Pytest + httpx | 7.x | Backend testing with async support |

## Quick Start

```bash
# Prerequisites: Node 20+, Python 3.11+

# Install all dependencies
make install

# Run both frontend and backend in development
make dev

# Or run with Docker (includes PostgreSQL)
make docker-up

# Run tests
make test

# Lint
make lint
```

### Development URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

## Project Structure

```
toolbox/
├── frontend/                   # React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/         # Reusable UI (PascalCase.tsx)
│   │   │   ├── DataTable.tsx   # Generic sortable/paginated table with TypeScript generics
│   │   │   ├── FileUpload.tsx  # Drag-drop upload with file type validation
│   │   │   ├── Modal.tsx       # Dialog with backdrop + ESC close + focus trap
│   │   │   ├── Sidebar.tsx     # Navigation sidebar with Lucide icons
│   │   │   ├── StatusBadge.tsx # Color-coded status indicators
│   │   │   ├── LoadingSpinner.tsx # Animated loading indicator
│   │   │   ├── GhlSendModal.tsx   # GoHighLevel send configuration modal
│   │   │   ├── GhlConnectionCard.tsx # GHL sub-account connection card
│   │   │   ├── EnrichmentPanel.tsx   # Contact enrichment UI panel
│   │   │   ├── EnrichmentProgress.tsx # Real-time enrichment progress
│   │   │   ├── AiReviewPanel.tsx     # AI validation review panel
│   │   │   ├── MineralExportModal.tsx # Mineral format export modal
│   │   │   └── index.ts       # Barrel exports
│   │   ├── pages/              # Tool pages (PascalCase.tsx)
│   │   │   ├── Dashboard.tsx   # Overview with tool cards + recent jobs
│   │   │   ├── Extract.tsx     # OCC Exhibit A processing
│   │   │   ├── Title.tsx       # Title opinion processing
│   │   │   ├── Proration.tsx   # Mineral holders + RRC
│   │   │   ├── Revenue.tsx     # Revenue PDF extraction
│   │   │   ├── GhlPrep.tsx     # GoHighLevel CSV preparation
│   │   │   ├── Settings.tsx    # Profile + preferences
│   │   │   ├── AdminSettings.tsx # User management + API keys
│   │   │   ├── MineralRights.tsx # Mineral rights management
│   │   │   ├── Login.tsx       # Firebase auth login
│   │   │   ├── Help.tsx        # FAQ + resources
│   │   │   └── index.ts       # Barrel exports
│   │   ├── contexts/           # React Context providers
│   │   │   └── AuthContext.tsx  # Firebase auth state + user data
│   │   ├── hooks/              # Custom React hooks (camelCase.ts)
│   │   │   ├── useLocalStorage.ts # Persistent local storage hook
│   │   │   ├── useSSEProgress.ts  # Server-Sent Events progress tracking
│   │   │   └── useToolLayout.ts   # Shared tool page layout logic
│   │   ├── layouts/
│   │   │   └── MainLayout.tsx  # Sidebar + Outlet wrapper for protected routes
│   │   ├── lib/
│   │   │   └── firebase.ts     # Firebase config + init (auth only)
│   │   ├── utils/
│   │   │   └── api.ts          # ApiClient class + per-tool clients
│   │   ├── App.tsx             # Root component with router setup
│   │   ├── main.tsx            # Entry point + React DOM render
│   │   └── index.css           # Global styles + Tailwind directives
│   ├── public/                 # Static assets
│   ├── dist/                   # Built production assets (generated)
│   ├── package.json            # Node dependencies + scripts
│   ├── vite.config.ts          # Vite config with /api proxy
│   ├── tsconfig.json           # TypeScript project references
│   ├── tsconfig.app.json       # App TypeScript config (strict mode)
│   └── tailwind.config.js      # Tailwind config with tre-* brand colors
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # App entry, routers, startup/shutdown hooks
│   │   ├── api/                # Route handlers (snake_case.py)
│   │   │   ├── extract.py      # /api/extract/* endpoints
│   │   │   ├── title.py        # /api/title/* endpoints
│   │   │   ├── proration.py    # /api/proration/* endpoints
│   │   │   ├── revenue.py      # /api/revenue/* endpoints
│   │   │   ├── ghl_prep.py     # /api/ghl-prep/* GoHighLevel prep
│   │   │   ├── ghl.py          # /api/ghl/* GoHighLevel integration
│   │   │   ├── enrichment.py   # /api/enrichment/* contact enrichment
│   │   │   ├── ai_validation.py # /api/ai-validation/* Gemini validation
│   │   │   ├── etl.py          # /api/etl/* entity resolution
│   │   │   ├── admin.py        # /api/admin/* user management
│   │   │   └── history.py      # /api/history/* job retrieval
│   │   ├── models/             # Pydantic models (snake_case.py)
│   │   │   ├── extract.py      # PartyEntry, ExtractionResult, EntityType enum
│   │   │   ├── title.py        # OwnerEntry, ProcessingResult
│   │   │   ├── proration.py    # MineralHolderRow, RRCQueryResult
│   │   │   ├── revenue.py      # RevenueStatement, M1UploadRow
│   │   │   ├── ghl_prep.py     # GHL export models
│   │   │   └── db_models.py    # SQLAlchemy ORM models (optional)
│   │   ├── services/           # Business logic by tool
│   │   │   ├── extract/        # PDF extraction + party parsing (6 files)
│   │   │   ├── title/          # Excel/CSV processing + entity detection
│   │   │   ├── proration/      # RRC data + NRA calculations (8 files)
│   │   │   │   ├── rrc_data_service.py  # RRC download with custom SSL adapter
│   │   │   │   ├── csv_processor.py     # In-memory pandas lookup
│   │   │   │   ├── calculation_service.py
│   │   │   │   ├── export_service.py
│   │   │   │   └── legal_description_parser.py
│   │   │   ├── revenue/        # Revenue parsing + M1 transformation
│   │   │   ├── ghl_prep/       # GoHighLevel CSV transformation
│   │   │   ├── ghl/            # GoHighLevel API integration + bulk send
│   │   │   │   ├── client.py           # GHL API client
│   │   │   │   ├── bulk_send_service.py # Bulk contact import with SSE
│   │   │   │   ├── connection_service.py # Sub-account management
│   │   │   │   └── normalization.py     # Phone/address normalization
│   │   │   ├── enrichment/     # Contact enrichment (PDL + SearchBug)
│   │   │   │   ├── enrichment_service.py
│   │   │   │   ├── pdl_provider.py
│   │   │   │   └── searchbug_provider.py
│   │   │   ├── etl/            # Entity resolution + relationship tracking
│   │   │   │   ├── entity_resolver.py
│   │   │   │   ├── entity_registry.py
│   │   │   │   ├── relationship_tracker.py
│   │   │   │   └── pipeline.py
│   │   │   ├── shared/         # Shared utilities across tools
│   │   │   ├── storage_service.py   # GCS + local file storage with transparent fallback
│   │   │   ├── firestore_service.py # Firestore CRUD operations with lazy init
│   │   │   ├── gemini_service.py    # Google Gemini AI validation
│   │   │   ├── address_validation_service.py # Google Maps address validation
│   │   │   ├── property_lookup_service.py    # Property data lookup
│   │   │   ├── data_enrichment_pipeline.py   # Coordinated enrichment pipeline
│   │   │   └── db_service.py        # PostgreSQL operations (optional, disabled by default)
│   │   ├── core/               # App configuration
│   │   │   ├── config.py       # Pydantic Settings (env vars) with @property helpers
│   │   │   ├── auth.py         # Firebase token verification + JSON allowlist
│   │   │   ├── ingestion.py    # Shared upload/export utilities
│   │   │   └── database.py     # SQLAlchemy async engine (optional)
│   │   └── utils/              # Shared helpers
│   │       ├── patterns.py     # Regex patterns, US states, text cleanup
│   │       └── helpers.py      # Date/decimal parsing, UID generation
│   ├── data/                   # Local data storage (RRC CSVs, uploads, allowlist)
│   ├── requirements.txt        # Python dependencies with version constraints
│   └── pytest.ini              # Pytest configuration (if exists)
├── .claude/                    # Claude Code config (agents, skills, hooks)
├── .github/workflows/
│   └── deploy.yml              # CI/CD: push to main → Cloud Run (tablerockenergy project)
├── test-data/                  # Test fixtures by tool (gitignored)
│   ├── extract/                # Sample OCC PDFs + CSV
│   ├── title/                  # Sample Excel files
│   ├── proration/              # Sample mineral holder files
│   ├── revenue/                # Sample revenue PDFs + M1 CSV
│   └── ghl/                    # Sample GHL CSV
├── .gitignore                  # Git ignore patterns
├── Dockerfile                  # Multi-stage: Node 20 build + Python 3.11 runtime
├── docker-compose.yml          # Dev: PostgreSQL + backend + frontend services
├── Makefile                    # Development commands (install, dev, test, lint, deploy)
├── README.md                   # High-level project overview
└── CLAUDE.md                   # This file - primary project documentation
```

## Architecture Overview

The app follows a **tool-per-module** pattern. Each tool (Extract, Title, Proration, Revenue, GHL Prep) has its own API routes, Pydantic models, and service layer. Shared infrastructure (storage, auth, database, enrichment, AI) lives in `services/` and `core/`.

**Request flow:** Frontend uploads file → API validates & processes → Service layer extracts/transforms data → Response with structured results → Frontend displays with filtering → User exports to CSV/Excel/PDF.

**Storage strategy:** GCS is the primary storage backend. If GCS is unavailable (local dev without credentials), all operations fall back to the local `data/` directory transparently via `StorageService`. The `config.use_gcs` property returns `True` when `gcs_bucket_name` is set, but actual GCS availability is determined at runtime.

**Auth flow:** Firebase Auth (Google Sign-In or email/password) → Frontend gets ID token → Backend verifies token via Firebase Admin SDK → Checks email against JSON allowlist (`data/allowed_users.json`) → Primary admin: `james@tablerocktx.com`.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React SPA  │────▶│  FastAPI API  │────▶│  Firestore   │
│  (Vite:5173) │     │  (Uvicorn)   │     │  (primary DB)│
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐
                     │  GCS Bucket  │
                     │ (+ local fs) │
                     └──────────────┘
```

## Tools

| Tool | Route | Input | Output | Purpose |
|------|-------|-------|--------|---------|
| Extract | `/extract` | OCC Exhibit A PDFs | CSV, Excel | Extract party names, addresses, entity types |
| Title | `/title` | Excel/CSV title opinions | CSV, Excel, Mineral format | Consolidate owner info, detect entities, flag duplicates |
| Proration | `/proration` | Mineral holders CSV | Excel, PDF | NRA calculations using RRC lease data |
| Revenue | `/revenue` | Revenue statement PDFs | M1 CSV (29 columns) | Parse EnergyLink/Energy Transfer statements |
| GHL Prep | `/ghl-prep` | Mineral export CSV | CSV | Transform Mineral export for GoHighLevel import |

### RRC Data Pipeline (Proration)
1. APScheduler triggers monthly download (1st of month, 2 AM)
2. CSV downloaded from RRC website (requires custom SSL adapter for outdated SSL)
   - Oil: `https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do`
   - Gas: `https://webapps2.rrc.texas.gov/EWA/gasProQueryAction.do`
3. Saved to GCS (or local) as `rrc-data/oil_proration.csv` and `gas_proration.csv`
4. Parsed into pandas DataFrame, cached in memory for fast lookups
5. Synced to Firestore for persistence and status tracking (batch operations commit every 500 docs)

**RRC SSL Issue:** The RRC website uses an outdated SSL configuration that requires a custom `HTTPAdapter` with legacy TLS settings. See `rrc_data_service.py` for the `RRCSSLAdapter` implementation.

### GoHighLevel Integration
- **Bulk contact import** via GoHighLevel API with real-time progress tracking
- **Server-Sent Events (SSE)** for live progress updates to frontend
- **Sub-account management** with connection storage in Firestore
- **Phone/address normalization** for GHL compatibility
- **Campaign tagging** + optional contact owner assignment
- **Batch processing** with error handling and retry logic

### Optional Features
- **AI Validation** (Gemini): Review extracted data for accuracy with configurable budget
- **Contact Enrichment** (PDL + SearchBug): Enhance contact data with phone, email, property info
- **Entity Resolution** (ETL): Deduplicate and link related entities across tools
- **Address Validation** (Google Maps): Standardize and validate US addresses

## Development Guidelines

### File Naming

**Frontend:**
- **Component files:** PascalCase (`DataTable.tsx`, `Extract.tsx`, `Modal.tsx`)
- **Utility/lib files:** camelCase (`api.ts`, `firebase.ts`)
- **Hook files:** camelCase with `use` prefix (`useAuth.ts`, `useSSEProgress.ts`)
- **Context files:** PascalCase (`AuthContext.tsx`)
- **Entry points:** camelCase (`main.tsx`)
- **Barrel exports:** `index.ts`

**Backend:**
- **Python modules:** snake_case (`rrc_data_service.py`, `csv_processor.py`, `export_service.py`)
- **Naming convention:** `{domain}_service.py`, `{type}_parser.py`, `export_service.py`

### Code Naming

**Frontend (TypeScript/React):**
- **Component functions:** PascalCase (`export default function MainLayout()`, `function DataTable()`)
- **Regular functions:** camelCase with verb prefix (`function handleClick()`, `const fetchData = async () => {}`)
- **Variables:** camelCase (`const userData`, `let isLoading`)
- **Boolean variables:** `is/has/should` prefix (`isLoading`, `hasPermission`, `shouldUpdate`)
- **Interfaces:** PascalCase (`interface PartyEntry`, `interface DataTableProps<T>`)
- **Type parameters:** Single capital letter or PascalCase (`<T>`, `<T extends object>`)
- **Constants:** SCREAMING_SNAKE_CASE (`const MAX_RETRIES = 3`)

**Backend (Python):**
- **Functions/variables:** snake_case (`def process_csv()`, `total_count`)
- **Classes:** PascalCase (`class StorageService`, `class Settings`)
- **Constants:** SCREAMING_SNAKE_CASE (`USERS_COLLECTION`, `M1_COLUMNS`, `DEFAULT_ALLOWED_USERS`)
- **Enum values (str, Enum):** PascalCase strings (`EntityType.INDIVIDUAL`, `EntityType.TRUST`)
- **Private/internal:** Leading underscore (`_cache`, `_init_firebase`)
- **Pydantic model fields:** snake_case with `Field(...)` descriptors

**CSS/Styling:**
- **Custom Tailwind colors:** `tre-` prefix (`tre-navy`, `tre-teal`, `tre-tan`, `tre-brown-dark`)

### Frontend Patterns

- **State:** `useState` for local state, Context API for auth only (no Redux/Zustand)
- **Data fetching:** `ApiClient` class wrapping `fetch()` with async/await in `useEffect`
- **Styling:** Tailwind utility classes inline, no separate CSS files per component
- **Exports:** Default exports for components, named exports for utilities, barrel re-exports via `index.ts`
- **Protected routes:** `ProtectedRoute` wrapper checks `useAuth()` context
- **Layout:** `MainLayout` with React Router `<Outlet />` for nested route rendering
- **Routing:** React Router v7 with nested routes under protected layout
- **Export pattern:** Fetch blob from API → create download link → click programmatically
- **TypeScript:**
  - Prefer `interface` for props/contracts
  - Use generics with `extends` constraints (`<T extends object>`)
  - Strict mode enabled with comprehensive linting rules
  - Use `type` keyword for type-only imports
- **Import order:**
  1. External packages (React, lucide-react, etc.)
  2. Internal absolute imports (if path aliases exist)
  3. Relative imports
  4. Types (with `type` keyword)
  5. Styles

### Backend Patterns

- **Router structure:** One file per tool in `api/`, prefixed with `/api/{tool}`
- **Upload flow:** Validate file type/size → extract text → parse → return structured response
- **Error handling:** `HTTPException` with status codes, graceful fallbacks for storage/DB
- **Logging:** `logger = logging.getLogger(__name__)` per module
- **Async:** All route handlers and DB operations are `async def`
- **Storage fallback:** GCS → local filesystem (transparent via `StorageService`)
- **Imports:**
  - `from __future__ import annotations` used in services for forward references
  - Lazy imports for Firebase/Firestore to avoid initialization errors
  - TYPE_CHECKING imports for type hints without runtime overhead
- **Pydantic models:**
  - `Field(...)` for required fields with description
  - `Field(default, description=...)` for optional fields
  - Use `str, Enum` for enums with string values
- **Firestore:**
  - Lazy client initialization (import only when needed)
  - Batch operations commit every 500 documents (Firestore limit)
- **Configuration:** Pydantic Settings with `@property` methods for computed values

## Available Commands

All commands run from the `toolbox/` directory.

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands with descriptions |
| `make install` | Install frontend (npm) and backend (pip) dependencies |
| `make install-frontend` | Install frontend dependencies only |
| `make install-backend` | Install backend dependencies only |
| `make dev` | Run frontend (Vite:5173) and backend (Uvicorn:8000) concurrently |
| `make dev-frontend` | Run frontend dev server only |
| `make dev-backend` | Run backend dev server only |
| `make test` | Run all tests (currently backend only) |
| `make test-backend` | Run pytest test suite with verbose output |
| `make lint` | Run ruff (Python) + eslint (TypeScript) |
| `make build` | Production frontend build to `dist/` |
| `make docker-build` | Build unified Docker image |
| `make docker-up` | Start all services via docker-compose (db + backend + frontend) |
| `make docker-down` | Stop docker-compose services |
| `make docker-logs` | Stream docker-compose logs |
| `make deploy` | Build + deploy to Cloud Run (`gcloud run deploy`) |
| `make clean` | Remove build artifacts, caches, and __pycache__ |
| `make preflight` | Run pre-push checks (TS build, Python syntax, linting) |
| `make setup-hooks` | Configure git pre-push hook |

## API Endpoints

All endpoints prefixed with `/api`. Full Swagger docs at `/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Service health check |
| POST | `/api/extract/upload` | Upload PDF, extract parties |
| POST | `/api/extract/export/csv` | Export to CSV |
| POST | `/api/extract/export/excel` | Export to Excel |
| POST | `/api/title/upload` | Upload Excel/CSV |
| POST | `/api/title/export/csv` | Export to CSV |
| POST | `/api/title/export/excel` | Export to Excel |
| GET | `/api/proration/rrc/status` | RRC data status (CSV + DB counts) |
| POST | `/api/proration/rrc/download` | Download RRC data + sync to Firestore |
| POST | `/api/proration/upload` | Process mineral holders CSV |
| POST | `/api/proration/export/excel` | Export to Excel |
| POST | `/api/proration/export/pdf` | Export to PDF |
| POST | `/api/revenue/upload` | Upload revenue PDFs (multiple) |
| POST | `/api/revenue/export/csv` | Export to M1 CSV |
| POST | `/api/ghl-prep/upload` | Upload Mineral export CSV |
| POST | `/api/ghl-prep/export/csv` | Export GHL-ready CSV |
| POST | `/api/ghl/send` | Bulk send contacts to GoHighLevel |
| GET | `/api/ghl/send/{job_id}/progress` | SSE stream for send progress |
| POST | `/api/enrichment/enrich` | Enrich contacts with PDL/SearchBug |
| POST | `/api/ai-validation/review` | AI review extracted data |
| GET | `/api/admin/users` | List allowed users |
| POST | `/api/admin/users` | Add user to allowlist |
| GET | `/api/admin/users/{email}/check` | Check if user is authorized |
| GET | `/api/history/jobs` | Get recent jobs (filter by tool) |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No | `/api` | Frontend API base URL |
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `DEBUG` | No | `false` | Enable debug logging |
| `PORT` | No | `8000` | Backend server port (8080 in production/Cloud Run) |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Max file upload size |
| `DATABASE_URL` | No | `postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox` | PostgreSQL connection (if enabled) |
| `DATABASE_ENABLED` | No | `false` | Enable PostgreSQL (disabled by default, use Firestore) |
| `FIRESTORE_ENABLED` | No | `true` | Enable Firestore persistence |
| `GCS_BUCKET_NAME` | No | `table-rock-tools-storage` | GCS bucket for file storage |
| `GCS_PROJECT_ID` | No | `tablerockenergy` | GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | - | Path to GCP service account key JSON |
| `GEMINI_API_KEY` | No | - | Google Gemini API key (optional AI validation) |
| `GEMINI_ENABLED` | No | `false` | Enable Gemini AI validation |
| `GOOGLE_MAPS_API_KEY` | No | - | Google Maps API key (optional address validation) |
| `GOOGLE_MAPS_ENABLED` | No | `false` | Enable Google Maps address validation |
| `PDL_API_KEY` | No | - | People Data Labs API key (optional enrichment) |
| `SEARCHBUG_API_KEY` | No | - | SearchBug API key (optional enrichment) |
| `ENRICHMENT_ENABLED` | No | `false` | Enable contact enrichment |
| `ENCRYPTION_KEY` | No | - | Fernet key for encrypting sensitive data |

**Note:** No `.env.example` file exists. Environment variables are documented in `backend/app/core/config.py` via Pydantic Settings.

## Deployment

Production is deployed to Google Cloud Run via GitHub Actions on push to `main`.

- **GCP Project:** tablerockenergy
- **Service:** table-rock-tools
- **Region:** us-central1
- **URL:** https://tools.tablerocktx.com
- **Resources:** 1 CPU, 1Gi memory, 600s timeout, 0-10 instances
- **Container:** Multi-stage Docker (Node 20 build → Python 3.11 runtime on port 8080)
- **Health check:** `curl -f http://localhost:8080/api/health` (30s interval)

### Manual Deploy
```bash
cd toolbox
make deploy
```

This runs:
1. `npm run build` (frontend to `dist/`)
2. `gcloud run deploy table-rock-tools --source . --project tablerockenergy --region us-central1 --allow-unauthenticated`

## Branding

| Token | Value | Usage |
|-------|-------|-------|
| Primary Navy | `#0e2431` / `tre-navy` | Sidebar, headers, backgrounds |
| Accent Teal | `#90c5ce` / `tre-teal` | Links, active states, scrollbars |
| Tan | `#cab487` / `tre-tan` | Accent highlights |
| Brown Dark | `#5b4825` / `tre-brown-dark` | Dark brown accents |
| Brown Medium | `#775723` / `tre-brown-medium` | Medium brown accents |
| Brown Light | `#966e35` / `tre-brown-light` | Light brown accents |
| Font | Oswald (Google Fonts) | All UI text, weights 300-700 |

Colors are defined in `frontend/tailwind.config.js` and used via Tailwind utility classes (e.g., `bg-tre-navy`, `text-tre-teal`).

## Key Gotchas

- **Python command:** Use `python3` not `python` on macOS (python command does not exist)
- **GCS signed URLs:** `storage_service.get_signed_url()` returns `None` when GCS is unavailable — always provide a local fallback URL
- **GCS availability:** `config.use_gcs` returns `True` when `gcs_bucket_name` is set (always by default), but actual GCS may not be available at runtime. Storage service handles this transparently with local fallback.
- **RRC SSL:** RRC website requires a custom SSL adapter (`RRCSSLAdapter` in `rrc_data_service.py`) due to outdated SSL configuration. Uses `verify=False` and custom cipher suites.
- **Firestore batching:** Firestore batch operations commit every 500 documents (Firestore limit). See `firestore_service.py`.
- **Vite proxy:** The frontend Vite dev server proxies `/api` requests to `http://localhost:8000` — no CORS issues in dev
- **Legacy tools:** Archived in `legacy/` — `toolbox/` is the active consolidated version
- **Docker port mapping:** Docker Compose maps backend to 8000, frontend to 5173. Production Dockerfile uses 8080 (Cloud Run default).
- **Auth allowlist:** Default admin is `james@tablerocktx.com`. Allowlist stored in `backend/data/allowed_users.json`.
- **Test data:** `test-data/` is gitignored — copy test fixtures locally, not committed to repo
- **File count:** Backend has ~60+ Python files, frontend has ~25+ TypeScript/TSX files (as of current state)

## Testing

- **Backend:** pytest with async support (`pytest-asyncio`), httpx for API testing
- **Frontend:** No test suite currently configured (ESLint for linting only)
- **Run tests:** `make test` or `cd backend && pytest -v`

## Additional Resources

- **Production URL:** https://tools.tablerocktx.com
- **API Documentation:** http://localhost:8000/docs (Swagger UI, dev only)
- **README:** @README.md for quick project overview
- **Detailed toolbox docs:** @toolbox/CLAUDE.md (this file)
