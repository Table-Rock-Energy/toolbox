# Table Rock Tools

Consolidated internal web application for Table Rock Energy. Provides four document-processing tools used by land and revenue teams: Extract (OCC Exhibit A party extraction), Title (title opinion consolidation), Proration (mineral holder NRA calculations with RRC data), and Revenue (revenue statement to M1 CSV conversion).

## Claude Permissions

- Git commits, pushes to `main`, and GitHub operations are allowed
- Deploying to Google Cloud Run (via `git push` triggering CI/CD) is allowed
- Running `npx tsc`, `python3` syntax checks, and build commands is allowed

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Frontend | React | 19.x | SPA with protected routes |
| Build | Vite | 7.x | Dev server with API proxy to backend |
| Language | TypeScript | 5.x | Strict mode enabled |
| Styling | Tailwind CSS | 3.x | Utility-first with custom brand colors |
| Icons | Lucide React | 0.x | Consistent icon set |
| Auth | Firebase Auth | 12.x | Google Sign-In + email/password |
| Backend | FastAPI | 0.x | Async Python API |
| Validation | Pydantic | 2.x | Request/response models |
| Data | Pandas | 2.x | CSV/Excel processing |
| PDF Read | PyMuPDF + PDFPlumber | - | Primary + fallback PDF text extraction |
| PDF Write | ReportLab | 4.x | PDF generation (proration exports) |
| Database | Firestore | - | Primary persistence (jobs, entries, RRC data) |
| Storage | Google Cloud Storage | - | File storage with local filesystem fallback |
| Database (opt) | PostgreSQL + SQLAlchemy | - | Optional relational DB (disabled by default) |
| Scheduler | APScheduler | 3.x | Monthly RRC data downloads |

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
│   │   │   ├── DataTable.tsx   # Generic sortable/paginated table
│   │   │   ├── FileUpload.tsx  # Drag-drop upload with validation
│   │   │   ├── Modal.tsx       # Dialog with backdrop + ESC close
│   │   │   ├── Sidebar.tsx     # Navigation sidebar
│   │   │   ├── StatusBadge.tsx # Color-coded status indicators
│   │   │   ├── LoadingSpinner.tsx
│   │   │   └── index.ts       # Barrel exports
│   │   ├── pages/              # Tool pages (PascalCase.tsx)
│   │   │   ├── Dashboard.tsx   # Overview with tool cards
│   │   │   ├── Extract.tsx     # OCC Exhibit A processing
│   │   │   ├── Title.tsx       # Title opinion processing
│   │   │   ├── Proration.tsx   # Mineral holders + RRC
│   │   │   ├── Revenue.tsx     # Revenue PDF extraction
│   │   │   ├── Settings.tsx    # Profile + preferences
│   │   │   ├── Login.tsx       # Firebase auth login
│   │   │   └── Help.tsx        # FAQ + resources
│   │   ├── contexts/           # React Context providers
│   │   │   └── AuthContext.tsx  # Firebase auth state
│   │   ├── layouts/
│   │   │   └── MainLayout.tsx  # Sidebar + Outlet wrapper
│   │   ├── lib/
│   │   │   └── firebase.ts     # Firebase config + init
│   │   └── utils/
│   │       └── api.ts          # ApiClient class + per-tool clients
│   └── dist/                   # Built production assets
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # App entry, routers, startup/shutdown
│   │   ├── api/                # Route handlers (snake_case.py)
│   │   │   ├── extract.py      # /api/extract/* endpoints
│   │   │   ├── title.py        # /api/title/* endpoints
│   │   │   ├── proration.py    # /api/proration/* endpoints
│   │   │   ├── revenue.py      # /api/revenue/* endpoints
│   │   │   ├── admin.py        # /api/admin/* user management
│   │   │   └── history.py      # /api/history/* job retrieval
│   │   ├── models/             # Pydantic models (snake_case.py)
│   │   │   ├── extract.py      # PartyEntry, ExtractionResult
│   │   │   ├── title.py        # OwnerEntry, ProcessingResult
│   │   │   ├── proration.py    # MineralHolderRow, RRCQueryResult
│   │   │   ├── revenue.py      # RevenueStatement, M1UploadRow
│   │   │   └── db_models.py    # SQLAlchemy ORM models
│   │   ├── services/           # Business logic by tool
│   │   │   ├── extract/        # PDF extraction + party parsing
│   │   │   ├── title/          # Excel/CSV processing + entity detection
│   │   │   ├── proration/      # RRC data + NRA calculations
│   │   │   ├── revenue/        # Revenue parsing + M1 transformation
│   │   │   ├── storage_service.py   # GCS + local file storage
│   │   │   ├── firestore_service.py # Firestore CRUD operations
│   │   │   └── db_service.py        # PostgreSQL operations (optional)
│   │   ├── core/               # App configuration
│   │   │   ├── config.py       # Pydantic Settings (env vars)
│   │   │   ├── auth.py         # Firebase token verification + allowlist
│   │   │   └── database.py     # SQLAlchemy async engine
│   │   └── utils/              # Shared helpers
│   │       ├── patterns.py     # Regex patterns, US states, text cleanup
│   │       └── helpers.py      # Date/decimal parsing, UID generation
│   ├── data/                   # Local data storage (RRC CSVs, uploads)
│   └── requirements.txt
├── .claude/                    # Claude Code config (agents, skills, hooks)
├── .github/workflows/
│   └── deploy.yml              # CI/CD: push to main → Cloud Run
├── test-data/                  # Test fixtures by tool (gitignored)
│   ├── extract/                # Sample OCC PDFs + CSV
│   ├── title/                  # Sample Excel files
│   ├── proration/              # Sample mineral holder files
│   ├── revenue/                # Sample revenue PDFs + M1 CSV
│   └── ghl/                    # Sample GHL CSV
├── Dockerfile                  # Multi-stage: Node build + Python runtime
├── docker-compose.yml          # Dev: PostgreSQL + backend + frontend
└── Makefile                    # Development commands
```

## Architecture Overview

The app follows a **tool-per-module** pattern. Each tool (Extract, Title, Proration, Revenue) has its own API routes, Pydantic models, and service layer. Shared infrastructure (storage, auth, database) lives in `services/` and `core/`.

**Request flow:** Frontend uploads file → API validates & processes → Service layer extracts/transforms data → Response with structured results → Frontend displays with filtering → User exports to CSV/Excel/PDF.

**Storage strategy:** GCS is the primary storage backend. If GCS is unavailable (local dev without credentials), all operations fall back to the local `data/` directory transparently via `StorageService`.

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

### RRC Data Pipeline (Proration)
1. APScheduler triggers monthly download (1st of month, 2 AM)
2. CSV downloaded from RRC website (requires custom SSL adapter for outdated SSL)
3. Saved to GCS (or local) as `rrc-data/oil_proration.csv` and `gas_proration.csv`
4. Parsed into pandas DataFrame, cached in memory for fast lookups
5. Synced to Firestore for persistence and status tracking

## Development Guidelines

### File Naming
- **Frontend components/pages:** PascalCase (`DataTable.tsx`, `Extract.tsx`)
- **Frontend utils/lib:** camelCase (`api.ts`, `firebase.ts`)
- **Frontend contexts:** PascalCase (`AuthContext.tsx`)
- **Backend modules:** snake_case (`rrc_data_service.py`, `csv_processor.py`)
- **Backend convention:** `{domain}_service.py`, `{type}_parser.py`, `export_service.py`

### Code Naming
- **React components:** PascalCase functions (`export default function MainLayout()`)
- **TypeScript variables/functions:** camelCase (`const userData`, `function handleClick()`)
- **TypeScript interfaces:** PascalCase (`interface PartyEntry`, `interface DataTableProps<T>`)
- **Python functions/variables:** snake_case (`def process_csv()`, `total_count`)
- **Python classes:** PascalCase (`class StorageService`, `class Settings`)
- **Python constants:** SCREAMING_SNAKE (`USERS_COLLECTION`, `M1_COLUMNS`)
- **Enums (Python):** SCREAMING_SNAKE values (`class WellType: OIL, GAS, BOTH`)
- **CSS custom colors:** `tre-` prefix (`tre-navy`, `tre-teal`, `tre-tan`)

### Frontend Patterns
- **State:** `useState` for local state, Context API for auth only (no Redux/Zustand)
- **Data fetching:** Direct `fetch()` with async/await in `useEffect`
- **Styling:** Tailwind utility classes inline, no separate CSS files per component
- **Exports:** Barrel exports via `index.ts` in `components/` and `pages/`
- **Protected routes:** `ProtectedRoute` wrapper checks `useAuth()` context
- **Layout:** `MainLayout` with `<Outlet />` for nested route rendering
- **Export pattern:** Fetch blob from API → create download link → click programmatically

### Backend Patterns
- **Router structure:** One file per tool in `api/`, prefixed with `/api/{tool}`
- **Upload flow:** Validate file type/size → extract text → parse → return structured response
- **Error handling:** `HTTPException` with status codes, graceful fallbacks for storage/DB
- **Logging:** `logger = logging.getLogger(__name__)` per module
- **Async:** All route handlers and DB operations are `async def`
- **Storage fallback:** GCS → local filesystem (transparent via `StorageService`)
- **Imports:** `from __future__ import annotations` used in services, lazy imports for Firebase/Firestore

## Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install frontend (npm) and backend (pip) dependencies |
| `make dev` | Run frontend (Vite:5173) and backend (Uvicorn:8000) concurrently |
| `make test` | Run pytest test suite |
| `make lint` | Run ruff (Python) + eslint (TypeScript) |
| `make build` | Production frontend build to `dist/` |
| `make docker-build` | Build unified Docker image |
| `make docker-up` | Start all services via docker-compose |
| `make docker-down` | Stop docker-compose services |
| `make deploy` | Deploy to Cloud Run (`gcloud run deploy`) |
| `make clean` | Remove build artifacts |

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
| `PORT` | No | `8000` | Backend server port |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Max file upload size |
| `DATABASE_URL` | No | `postgresql+asyncpg://...` | PostgreSQL connection (if enabled) |
| `DATABASE_ENABLED` | No | `false` | Enable PostgreSQL |
| `FIRESTORE_ENABLED` | No | `true` | Enable Firestore persistence |
| `GCS_BUCKET_NAME` | No | `table-rock-tools-storage` | GCS bucket for file storage |
| `GCS_PROJECT_ID` | No | `tablerockenergy` | GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | - | Path to GCP service account key |

## Deployment

Production is deployed to Google Cloud Run via GitHub Actions on push to `main`.

- **GCP Project:** tablerockenergy
- **Service:** table-rock-tools
- **Region:** us-central1
- **URL:** https://tools.tablerocktx.com
- **Resources:** 1 CPU, 1Gi memory, 600s timeout, 0-10 instances
- **Container:** Multi-stage Docker (Node 20 build → Python 3.11 runtime on port 8080)

### Manual Deploy
```bash
make deploy
```

## Branding

| Token | Value | Usage |
|-------|-------|-------|
| Primary Navy | `#0e2431` / `tre-navy` | Sidebar, headers, backgrounds |
| Accent Teal | `#90c5ce` / `tre-teal` | Links, active states, scrollbars |
| Tan | `#cab487` / `tre-tan` | Accent highlights |
| Font | Oswald (Google Fonts) | All UI text, weights 300-700 |

## Key Gotchas

- Use `python3` not `python` on macOS
- `storage_service.get_signed_url()` returns `None` when GCS is unavailable — always provide a local fallback URL
- `config.use_gcs` returns `True` when bucket name is set (always by default), but actual GCS may not be available at runtime
- RRC website requires a custom SSL adapter due to outdated SSL configuration — see `rrc_data_service.py`
- Firestore batch operations commit every 500 documents (Firestore limit)
- The frontend Vite dev server proxies `/api` requests to `http://localhost:8000` — no CORS issues in dev
- `test-data/` is gitignored — copy test fixtures locally, not committed to repo
- Legacy standalone tools have been moved to `../legacy/` for safekeeping
