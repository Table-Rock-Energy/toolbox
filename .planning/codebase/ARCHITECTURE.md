# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** Tool-per-module monolith with React SPA frontend and FastAPI backend

**Key Characteristics:**
- Each business tool (Extract, Title, Proration, Revenue, GHL Prep) has its own vertical slice: API routes, Pydantic models, and service layer
- Shared infrastructure services (storage, auth, Firestore, AI, enrichment) live at the top level of the services directory
- Frontend is a single-page application with one page component per tool, communicating via REST API
- Backend serves both the API and the built frontend static files in production (SPA fallback routing)

## Layers

**Frontend SPA (React + TypeScript):**
- Purpose: User interface for all tools
- Location: `frontend/src/`
- Contains: Pages, components, hooks, contexts, API client
- Depends on: Backend API via `fetch()` calls through `ApiClient`
- Used by: End users in browser

**API Router Layer (FastAPI):**
- Purpose: HTTP request handling, validation, response formatting
- Location: `backend/app/api/`
- Contains: One router file per tool + cross-cutting routers (admin, history, enrichment, AI, ETL, GHL)
- Depends on: Models layer, Service layer, Core layer
- Used by: Frontend SPA

**Pydantic Models Layer:**
- Purpose: Request/response validation, data contracts between API and services
- Location: `backend/app/models/`
- Contains: One model file per tool with request/response/domain models
- Depends on: Nothing (pure data definitions)
- Used by: API layer, Service layer

**Service Layer (Business Logic):**
- Purpose: All processing, parsing, transformation, and export logic
- Location: `backend/app/services/`
- Contains: One subdirectory per tool with multiple specialized service files + top-level shared services
- Depends on: Models, Core config, external APIs, Firestore, Storage
- Used by: API layer

**Core Layer (Infrastructure):**
- Purpose: App configuration, authentication, shared upload/export utilities
- Location: `backend/app/core/`
- Contains: `config.py` (Pydantic Settings), `auth.py` (Firebase + allowlist), `ingestion.py` (shared upload/export helpers), `database.py` (optional PostgreSQL)
- Depends on: Firebase Admin SDK, Firestore
- Used by: API layer, Service layer

**Persistence Layer:**
- Purpose: Data storage and retrieval
- Location: `backend/app/services/firestore_service.py` (primary), `backend/app/services/storage_service.py` (files), `backend/app/services/db_service.py` (optional PostgreSQL)
- Contains: Firestore CRUD for jobs/entries/RRC data/config, GCS file storage with local fallback
- Depends on: Google Cloud Firestore, Google Cloud Storage, local filesystem
- Used by: Service layer, Core layer (ingestion)

## Data Flow

**Standard Tool Upload Flow (Extract, Title, Proration, Revenue):**

1. User uploads file in React page component (e.g., `frontend/src/pages/Extract.tsx`)
2. `ApiClient.uploadFile()` sends `multipart/form-data` POST to `/api/{tool}/upload`
3. API router calls `validate_upload()` from `backend/app/core/ingestion.py` (checks extension, size, reads bytes)
4. Router delegates to tool-specific service functions (e.g., `extract_text_from_pdf()` -> `parse_exhibit_a()`)
5. Service returns structured result (Pydantic model)
6. Router calls `persist_job_result()` from `backend/app/core/ingestion.py` (fire-and-forget Firestore save)
7. Router returns `UploadResponse` with parsed data to frontend
8. Frontend renders results in `DataTable` component with filtering/sorting
9. User triggers export -> frontend sends POST to `/api/{tool}/export/{format}` with entry data
10. API router calls tool-specific export service -> returns file as download response

**RRC Data Pipeline (Proration-specific):**

1. Background download triggered via API endpoint `/api/proration/rrc/download`
2. `start_rrc_background_download()` in `backend/app/services/rrc_background.py` spawns async task
3. `rrc_data_service.py` downloads CSV from RRC website using custom SSL adapter
4. CSV saved to GCS (or local) via `StorageService`
5. Data parsed into pandas DataFrame, synced to Firestore (batch commits every 500 docs)
6. Frontend polls `/api/proration/rrc/download/{job_id}/status` for progress
7. On CSV upload, `ensure_counties_fresh()` triggers on-demand county-level downloads if stale

**GoHighLevel Bulk Send Flow:**

1. User prepares contacts in GHL Prep tool -> exports CSV
2. User opens GHL Send Modal, configures connection + campaign
3. Frontend calls `/api/ghl/contacts/bulk-send` via `ghlApi.startBulkSend()`
4. Backend returns `job_id` immediately, processes contacts asynchronously
5. Frontend connects to SSE endpoint `/api/ghl/send/{job_id}/progress` via `useSSEProgress` hook
6. Backend streams progress events; frontend displays real-time created/updated/failed counts

**State Management:**
- Frontend: `useState` for local page state, React Context (`AuthContext`) for auth only
- No global state library (Redux/Zustand); each page manages its own state independently
- Backend: Stateless request handling; Firestore for persistence; in-memory pandas DataFrame cache for RRC data

## Key Abstractions

**ApiClient (`frontend/src/utils/api.ts`):**
- Purpose: Centralized HTTP client wrapping `fetch()` with auth token injection, timeout, error normalization
- Pattern: Singleton instance exported as `api`, plus domain-specific API objects (`ghlApi`, `aiApi`, `enrichmentApi`)
- All frontend-to-backend communication flows through this class

**StorageService (`backend/app/services/storage_service.py`):**
- Purpose: Transparent file storage with GCS primary and local filesystem fallback
- Pattern: Strategy pattern -- `is_gcs_enabled` determines which backend is used; callers never know
- Specialized helpers: `RRCDataStorage`, `UploadStorage`, `ProfileStorage` wrap `StorageService` with domain-specific paths
- Global singletons: `storage_service`, `rrc_storage`, `upload_storage`, `profile_storage`

**FirestoreService (`backend/app/services/firestore_service.py`):**
- Purpose: All Firestore CRUD operations organized by domain (users, jobs, entries, RRC, config, audit)
- Pattern: Module-level functions with lazy client initialization; batch operations commit every 500 docs
- Collections: `users`, `jobs`, `extract_entries`, `title_entries`, `proration_rows`, `revenue_statements`, `rrc_oil_proration`, `rrc_gas_proration`, `rrc_data_syncs`, `rrc_county_status`, `audit_logs`, `app_config`, `user_preferences`

**Ingestion Engine (`backend/app/core/ingestion.py`):**
- Purpose: Reusable scaffolding for file upload validation, Firestore job persistence, and export response building
- Pattern: Three utility functions (`validate_upload`, `persist_job_result`, `file_response`) that all tool routers share
- Persistence is fire-and-forget: Firestore failures never block the user's upload response

**Tool Service Modules:**
- Purpose: Each tool's business logic encapsulated in a directory of specialized services
- Pattern: `{tool}/` directory with `export_service.py` (always present), plus domain-specific parsers/processors
- Examples: `backend/app/services/extract/parser.py`, `backend/app/services/revenue/energylink_parser.py`, `backend/app/services/proration/csv_processor.py`

## Entry Points

**Backend Application (`backend/app/main.py`):**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` (dev: port 8000, prod: port 8080)
- Responsibilities: FastAPI app creation, CORS middleware, router registration (11 routers), startup/shutdown hooks (load allowlist, app settings, enrichment config, optional DB init), static file serving for production SPA

**Frontend Application (`frontend/src/main.tsx`):**
- Location: `frontend/src/main.tsx`
- Triggers: Vite dev server (port 5173) or served as static files from backend in production
- Responsibilities: React DOM render, BrowserRouter setup

**React Router (`frontend/src/App.tsx`):**
- Location: `frontend/src/App.tsx`
- Triggers: Browser navigation
- Responsibilities: Route definitions, `ProtectedRoute` auth wrapper, `AdminRoute` admin wrapper, `AuthProvider` context, `MainLayout` with `Outlet` for nested routes

**Dockerfile (`Dockerfile`):**
- Location: `Dockerfile`
- Triggers: `docker build` or Cloud Run deployment
- Responsibilities: Multi-stage build -- Node 20 builds frontend to `dist/`, Python 3.11 runs backend with built frontend copied to `static/`

## Error Handling

**Strategy:** Graceful degradation with explicit fallbacks at every infrastructure boundary

**Patterns:**
- **API layer:** `HTTPException` with status codes (400 for validation, 500 for processing errors). All route handlers wrap processing in try/except, re-raising `HTTPException` and catching generic `Exception` for 500 responses.
- **Storage fallback:** GCS unavailable -> transparent local filesystem fallback via `StorageService`. No error surfaced to user.
- **Firestore fire-and-forget:** `persist_job_result()` catches all Firestore exceptions and returns `None` -- upload succeeds even if persistence fails.
- **Auth fallback:** If Firebase Admin SDK not initialized, `verify_firebase_token()` returns `None` and routes proceed without server-side verification (dev mode).
- **Frontend:** `ApiClient` returns `{ data: null, error: string, status: number }` -- callers check `error` field. Timeout handling via `AbortController`. SSE reconnection with exponential backoff (up to 5 attempts) in `useSSEProgress`.

## Cross-Cutting Concerns

**Logging:**
- `logging.getLogger(__name__)` per module in backend
- `logging.basicConfig()` in `backend/app/main.py` with INFO level
- `console.error()` in frontend for auth and API errors

**Validation:**
- Backend: Pydantic models for request/response validation, `validate_upload()` for file checks
- Frontend: Minimal -- relies on backend validation, file type filtering in `FileUpload` component

**Authentication:**
- Firebase Auth (Google Sign-In + email/password) on frontend via `AuthContext`
- Backend: `HTTPBearer` security scheme, Firebase Admin SDK token verification, JSON allowlist (`data/allowed_users.json` + Firestore)
- `get_current_user` dependency: optional auth (returns `None` if no token)
- `require_auth` dependency: mandatory auth (raises 401)
- `require_admin` dependency: chains on `require_auth`, checks admin role
- Auth token injected into `ApiClient` on login via `api.setAuthToken()`

---

*Architecture analysis: 2026-03-10*
