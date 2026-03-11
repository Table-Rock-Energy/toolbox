# Codebase Structure

**Analysis Date:** 2026-03-10

## Directory Layout

```
toolbox/
├── frontend/                       # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── components/             # Reusable UI components (PascalCase.tsx)
│   │   ├── pages/                  # Tool page components (PascalCase.tsx)
│   │   ├── contexts/               # React Context providers
│   │   ├── hooks/                  # Custom React hooks (camelCase.ts)
│   │   ├── layouts/                # Layout wrapper components
│   │   ├── lib/                    # Third-party library config
│   │   ├── utils/                  # Utility modules
│   │   ├── assets/                 # Static assets (images, etc.)
│   │   ├── App.tsx                 # Root component + routes
│   │   ├── main.tsx                # Entry point
│   │   └── index.css               # Global styles + Tailwind
│   ├── public/                     # Static public assets
│   ├── dist/                       # Built output (generated, gitignored)
│   ├── package.json                # Node dependencies
│   ├── vite.config.ts              # Vite config with /api proxy
│   ├── tsconfig.json               # TypeScript project references
│   ├── tsconfig.app.json           # App TypeScript config (strict)
│   └── tailwind.config.js          # Tailwind with tre-* brand colors
├── backend/                        # FastAPI Python backend
│   ├── app/
│   │   ├── main.py                 # FastAPI app, router registration, startup/shutdown
│   │   ├── api/                    # Route handlers (one file per tool)
│   │   │   ├── extract.py          # /api/extract/* endpoints
│   │   │   ├── title.py            # /api/title/* endpoints
│   │   │   ├── proration.py        # /api/proration/* endpoints
│   │   │   ├── revenue.py          # /api/revenue/* endpoints
│   │   │   ├── ghl_prep.py         # /api/ghl-prep/* endpoints
│   │   │   ├── ghl.py              # /api/ghl/* GoHighLevel integration
│   │   │   ├── admin.py            # /api/admin/* user management
│   │   │   ├── history.py          # /api/history/* job retrieval
│   │   │   ├── ai_validation.py    # /api/ai/* Gemini validation
│   │   │   ├── enrichment.py       # /api/enrichment/* contact enrichment
│   │   │   └── etl.py              # /api/etl/* entity resolution
│   │   ├── models/                 # Pydantic models (one file per tool)
│   │   │   ├── extract.py          # PartyEntry, ExtractionResult, ExportRequest
│   │   │   ├── title.py            # OwnerEntry, ProcessingResult
│   │   │   ├── proration.py        # MineralHolderRow, RRCQueryResult
│   │   │   ├── revenue.py          # RevenueStatement, M1UploadRow
│   │   │   ├── ghl_prep.py         # GHL export models
│   │   │   ├── ghl.py              # GHL connection/send models
│   │   │   ├── etl.py              # Entity resolution models
│   │   │   ├── enrichment.py       # Enrichment request/response
│   │   │   ├── ai_validation.py    # AI validation models
│   │   │   └── db_models.py        # SQLAlchemy ORM models (optional)
│   │   ├── services/               # Business logic
│   │   │   ├── extract/            # Extract tool services
│   │   │   │   ├── parser.py           # Free-text Exhibit A parsing
│   │   │   │   ├── table_parser.py     # Table-format PDF parsing
│   │   │   │   ├── pdf_extractor.py    # PyMuPDF + PDFPlumber text extraction
│   │   │   │   ├── format_detector.py  # Auto-detect Exhibit A format
│   │   │   │   ├── name_parser.py      # Person name parsing
│   │   │   │   ├── address_parser.py   # Address component extraction
│   │   │   │   └── export_service.py   # CSV/Excel export
│   │   │   ├── title/              # Title tool services
│   │   │   │   ├── excel_processor.py       # Excel file processing
│   │   │   │   ├── csv_processor.py         # CSV file processing
│   │   │   │   ├── ownership_report_parser.py # Ownership report parsing
│   │   │   │   ├── text_parser.py           # Text extraction
│   │   │   │   ├── name_parser.py           # Name parsing
│   │   │   │   ├── address_parser.py        # Address parsing
│   │   │   │   ├── entity_detector.py       # Entity type detection
│   │   │   │   └── export_service.py        # CSV/Excel/Mineral export
│   │   │   ├── proration/          # Proration tool services
│   │   │   │   ├── csv_processor.py              # Mineral holders CSV processing
│   │   │   │   ├── rrc_data_service.py           # RRC download + SSL adapter + DB sync
│   │   │   │   ├── rrc_county_download_service.py # On-demand county-level downloads
│   │   │   │   ├── rrc_county_codes.py           # County code mappings
│   │   │   │   ├── calculation_service.py        # NRA calculations
│   │   │   │   ├── legal_description_parser.py   # Legal description parsing
│   │   │   │   └── export_service.py             # CSV/Excel/PDF export
│   │   │   ├── revenue/            # Revenue tool services
│   │   │   │   ├── pdf_extractor.py         # Revenue PDF text extraction
│   │   │   │   ├── format_detector.py       # Revenue format detection
│   │   │   │   ├── energylink_parser.py     # EnergyLink statement parser
│   │   │   │   ├── energytransfer_parser.py # Energy Transfer parser
│   │   │   │   ├── enverus_parser.py        # Enverus statement parser
│   │   │   │   ├── enverus_layout.py        # Enverus layout detection
│   │   │   │   ├── gemini_revenue_parser.py # AI-powered revenue parsing
│   │   │   │   ├── m1_transformer.py        # M1 CSV column transformation
│   │   │   │   └── export_service.py        # CSV export
│   │   │   ├── ghl_prep/           # GHL Prep tool services
│   │   │   │   ├── transform_service.py # Mineral -> GHL CSV transformation
│   │   │   │   └── export_service.py    # CSV export
│   │   │   ├── ghl/                # GoHighLevel integration services
│   │   │   │   ├── client.py              # GHL API HTTP client
│   │   │   │   ├── bulk_send_service.py   # Bulk contact import + SSE
│   │   │   │   ├── connection_service.py  # Sub-account management
│   │   │   │   └── normalization.py       # Phone/address normalization
│   │   │   ├── enrichment/         # Contact enrichment services
│   │   │   │   ├── enrichment_service.py  # Orchestrates enrichment
│   │   │   │   ├── pdl_provider.py        # People Data Labs provider
│   │   │   │   └── searchbug_provider.py  # SearchBug provider
│   │   │   ├── etl/                # Entity resolution services
│   │   │   │   ├── entity_resolver.py      # Fuzzy entity matching
│   │   │   │   ├── entity_registry.py      # Entity CRUD in Firestore
│   │   │   │   ├── relationship_tracker.py # Entity relationships
│   │   │   │   └── pipeline.py             # ETL orchestration
│   │   │   ├── shared/             # Cross-tool utilities
│   │   │   │   ├── address_parser.py  # Shared address parsing
│   │   │   │   ├── encryption.py      # Fernet encryption helpers
│   │   │   │   ├── export_utils.py    # Shared export utilities
│   │   │   │   └── http_retry.py      # HTTP retry with backoff
│   │   │   ├── firestore_service.py       # Firestore CRUD (primary DB)
│   │   │   ├── storage_service.py         # GCS + local file storage
│   │   │   ├── rrc_background.py          # Background RRC download manager
│   │   │   ├── gemini_service.py          # Gemini AI validation
│   │   │   ├── address_validation_service.py # Google Maps validation
│   │   │   ├── data_enrichment_pipeline.py   # Coordinated enrichment
│   │   │   ├── property_lookup_service.py    # Property data lookup
│   │   │   └── db_service.py              # PostgreSQL ops (optional)
│   │   ├── core/                   # Infrastructure + config
│   │   │   ├── config.py           # Pydantic Settings (env vars)
│   │   │   ├── auth.py             # Firebase auth + JSON allowlist
│   │   │   ├── ingestion.py        # Upload validation + job persistence + export helpers
│   │   │   └── database.py         # SQLAlchemy async engine (optional)
│   │   └── utils/                  # Low-level helpers
│   │       ├── patterns.py         # Regex patterns, US states, text cleanup
│   │       └── helpers.py          # Date/decimal parsing, UID generation
│   ├── data/                       # Local data storage (gitignored contents)
│   │   └── allowed_users.json      # Auth allowlist (local cache)
│   └── requirements.txt            # Python dependencies
├── .github/workflows/
│   └── deploy.yml                  # CI/CD: push to main -> Cloud Run
├── .claude/                        # Claude Code config
├── .planning/                      # GSD planning documents
│   └── codebase/                   # Codebase analysis (this directory)
├── test-data/                      # Test fixtures (gitignored)
├── docs/                           # Documentation
├── Dockerfile                      # Multi-stage build (Node 20 + Python 3.11)
├── docker-compose.yml              # Local dev services
├── Makefile                        # Development commands
├── CLAUDE.md                       # Project documentation
└── README.md                       # Quick start overview
```

## Directory Purposes

**`frontend/src/pages/`:**
- Purpose: One React component per tool, each managing its own state and UI
- Contains: Large page-level components (many 1000+ lines) with upload handling, data display, filtering, and export
- Key files: `Extract.tsx` (56K), `Title.tsx` (65K), `Proration.tsx` (71K), `Revenue.tsx` (61K), `GhlPrep.tsx` (33K), `AdminSettings.tsx` (54K)

**`frontend/src/components/`:**
- Purpose: Reusable UI building blocks shared across pages
- Contains: Generic components (DataTable, FileUpload, Modal, Sidebar, StatusBadge, LoadingSpinner) and domain-specific components (GhlSendModal, GhlConnectionCard, EnrichmentPanel, AiReviewPanel)
- Key files: `DataTable.tsx` (generic sortable/paginated table), `FileUpload.tsx` (drag-drop upload), `Sidebar.tsx` (navigation)

**`frontend/src/contexts/`:**
- Purpose: React Context providers for shared state
- Contains: `AuthContext.tsx` only -- provides auth state, sign-in/out, token management
- Key files: `AuthContext.tsx`

**`frontend/src/hooks/`:**
- Purpose: Custom React hooks for reusable logic
- Contains: `useLocalStorage.ts` (persistent state), `useSSEProgress.ts` (SSE with reconnection), `useToolLayout.ts` (panel collapse state)
- Key files: All three hooks

**`frontend/src/utils/`:**
- Purpose: Non-React utility modules
- Contains: `api.ts` -- `ApiClient` class + domain-specific API wrappers + TypeScript interfaces for all API types
- Key files: `api.ts`

**`backend/app/api/`:**
- Purpose: FastAPI route handlers, one file per tool/feature
- Contains: Router definitions with upload/export/health endpoints
- Key files: `extract.py`, `title.py`, `proration.py`, `revenue.py`, `ghl_prep.py`, `ghl.py`, `admin.py`

**`backend/app/models/`:**
- Purpose: Pydantic request/response models and domain types
- Contains: One model file per tool with `UploadResponse`, `ExportRequest`, domain-specific entry/row models
- Key files: `extract.py`, `proration.py`, `revenue.py`, `ghl.py`, `db_models.py`

**`backend/app/services/`:**
- Purpose: All business logic, organized by tool in subdirectories
- Contains: Tool-specific service directories + top-level shared services (Firestore, Storage, AI, enrichment)
- Key files: `firestore_service.py` (30K, primary DB), `storage_service.py` (17K, file storage), `rrc_data_service.py` (29K, RRC pipeline)

**`backend/app/core/`:**
- Purpose: App infrastructure -- config, auth, shared ingestion utilities
- Contains: Pydantic Settings, Firebase auth, upload/export helpers, optional DB engine
- Key files: `config.py`, `auth.py`, `ingestion.py`

**`backend/app/utils/`:**
- Purpose: Low-level helpers with no domain logic
- Contains: Regex patterns, US state abbreviations, text cleanup, date/decimal parsing
- Key files: `patterns.py`, `helpers.py`

**`backend/data/`:**
- Purpose: Local file storage fallback directory
- Contains: `allowed_users.json` (auth allowlist), RRC CSV files (when downloaded locally), uploaded files
- Generated: Partially (RRC data downloaded at runtime)
- Committed: Only `allowed_users.json`; file contents are gitignored

## Key File Locations

**Entry Points:**
- `frontend/src/main.tsx`: React DOM render + BrowserRouter
- `frontend/src/App.tsx`: Route definitions + auth wrappers
- `backend/app/main.py`: FastAPI app creation + router registration + startup hooks

**Configuration:**
- `backend/app/core/config.py`: All backend settings via Pydantic Settings (env vars)
- `frontend/vite.config.ts`: Vite dev server + API proxy + build config
- `frontend/tailwind.config.js`: Tailwind CSS with `tre-*` brand colors
- `frontend/tsconfig.app.json`: TypeScript strict mode config
- `Dockerfile`: Multi-stage production build
- `Makefile`: All dev/build/deploy commands

**Core Logic:**
- `backend/app/services/extract/parser.py`: Free-text Exhibit A parsing (14K)
- `backend/app/services/extract/pdf_extractor.py`: PDF text extraction with PyMuPDF + PDFPlumber (11K)
- `backend/app/services/proration/csv_processor.py`: Mineral holders processing + RRC lookup (15K)
- `backend/app/services/proration/rrc_data_service.py`: RRC data download/parse/sync (29K)
- `backend/app/services/revenue/enverus_parser.py`: Enverus revenue statement parser (27K)
- `backend/app/services/title/excel_processor.py`: Title opinion Excel processing (23K)
- `backend/app/services/ghl/bulk_send_service.py`: GHL bulk contact import (22K)

**Shared Infrastructure:**
- `backend/app/services/firestore_service.py`: All Firestore CRUD operations (30K)
- `backend/app/services/storage_service.py`: GCS + local file storage with fallback (17K)
- `backend/app/core/auth.py`: Firebase token verification + allowlist management
- `backend/app/core/ingestion.py`: Upload validation + job persistence + export response
- `frontend/src/utils/api.ts`: ApiClient + all API type definitions (484 lines)
- `frontend/src/contexts/AuthContext.tsx`: Auth state + Firebase integration

**Testing:**
- `backend/`: Tests run via `pytest` from backend directory (test files in backend, structure TBD)
- `test-data/`: Test fixture files organized by tool (gitignored)

## Naming Conventions

**Files:**
- Frontend components/pages: PascalCase (`DataTable.tsx`, `Extract.tsx`, `MainLayout.tsx`)
- Frontend hooks: camelCase with `use` prefix (`useSSEProgress.ts`, `useLocalStorage.ts`)
- Frontend utils/lib: camelCase (`api.ts`, `firebase.ts`)
- Backend Python modules: snake_case (`csv_processor.py`, `rrc_data_service.py`)
- Backend service pattern: `{domain}_service.py`, `{type}_parser.py`, `export_service.py`
- Barrel exports: `index.ts` (frontend), `__init__.py` (backend)

**Directories:**
- Frontend: lowercase (`components/`, `pages/`, `hooks/`, `contexts/`, `layouts/`, `utils/`, `lib/`)
- Backend: snake_case (`services/extract/`, `services/ghl_prep/`, `services/shared/`)

## Where to Add New Code

**New Tool (e.g., "Lease"):**
- Backend API router: `backend/app/api/lease.py` -- register in `backend/app/main.py`
- Backend models: `backend/app/models/lease.py`
- Backend services: `backend/app/services/lease/` with `__init__.py`, processing files, and `export_service.py`
- Frontend page: `frontend/src/pages/Lease.tsx` -- add route in `frontend/src/App.tsx`
- Use `validate_upload()`, `persist_job_result()`, `file_response()` from `backend/app/core/ingestion.py`

**New Reusable Component:**
- Component file: `frontend/src/components/NewComponent.tsx`
- Add to barrel export: `frontend/src/components/index.ts`

**New Custom Hook:**
- Hook file: `frontend/src/hooks/useNewHook.ts`

**New Backend Shared Service:**
- Top-level: `backend/app/services/new_service.py`
- Cross-tool utility: `backend/app/services/shared/new_util.py`

**New API Endpoint on Existing Tool:**
- Add route to existing router file in `backend/app/api/{tool}.py`
- Add request/response models to `backend/app/models/{tool}.py`

**New Pydantic Model:**
- Add to existing `backend/app/models/{tool}.py` or create new file for new domain

**Utilities:**
- Frontend: `frontend/src/utils/` (new file or extend `api.ts` for API types)
- Backend regex/text: `backend/app/utils/patterns.py`
- Backend date/number: `backend/app/utils/helpers.py`

## Special Directories

**`backend/data/`:**
- Purpose: Local file storage fallback, auth allowlist cache
- Generated: Partially -- RRC CSVs downloaded at runtime, uploads stored here when GCS unavailable
- Committed: `allowed_users.json` only; rest is gitignored

**`frontend/dist/`:**
- Purpose: Built production frontend assets
- Generated: Yes (by `npm run build`)
- Committed: No (gitignored)

**`test-data/`:**
- Purpose: Test fixture files organized by tool (PDFs, CSVs, Excel files)
- Generated: No (manually created)
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: By GSD mapping/planning commands
- Committed: Yes

**`.claude/`:**
- Purpose: Claude Code configuration (agents, hooks, skills references)
- Generated: Partially (some auto-generated, some manual)
- Committed: Yes

---

*Structure analysis: 2026-03-10*
