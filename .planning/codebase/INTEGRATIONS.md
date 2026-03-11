# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**Texas Railroad Commission (RRC):**
- Purpose: Download oil and gas proration data (lease acreage, operators, fields) for NRA calculations
- Oil URL: `https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do`
- Gas URL: `https://webapps2.rrc.texas.gov/EWA/gasProQueryAction.do`
- Client: Custom `requests.Session` with `RRCSSLAdapter` for legacy SSL (`backend/app/services/proration/rrc_data_service.py`)
- Auth: None (public data, but requires custom SSL cipher config + browser-like headers)
- Schedule: Was monthly via APScheduler, now triggered externally (Cloud Run scales to 0)
- Caveat: RRC site has outdated SSL requiring `verify=False`, custom cipher suites, and `OP_LEGACY_SERVER_CONNECT`

**GoHighLevel (GHL) CRM:**
- Purpose: Bulk contact import with upsert logic (search by email, create or update)
- Base URL: `https://services.leadconnectorhq.com`
- API Version: `2021-07-28`
- SDK/Client: Custom async `GHLClient` class using `httpx.AsyncClient` (`backend/app/services/ghl/client.py`)
- Auth: Bearer token (Private Integration Token) per sub-account, stored encrypted in Firestore
- Rate limits: Token bucket (50 req/10s), exponential backoff on 429, daily limit tracking (200k/day)
- Features: Contact upsert, custom field mapping, campaign tagging, owner assignment
- Progress: Real-time SSE streaming via `sse-starlette` (`GET /api/ghl/send/{job_id}/progress`)
- Connection management: `backend/app/services/ghl/connection_service.py`
- Normalization: Phone/address normalization for GHL compatibility (`backend/app/services/ghl/normalization.py`)

**Google Gemini AI (Optional):**
- Purpose: AI-powered data validation/correction suggestions for all tools
- SDK: `google-genai` (`from google import genai`)
- Client: `backend/app/services/gemini_service.py`
- Model: `gemini-2.5-flash` (configurable via `GEMINI_MODEL`)
- Auth: API key via `GEMINI_API_KEY` env var
- Rate limits: 10 RPM, 250 RPD (free tier), monthly budget cap ($15 default)
- Features: Structured JSON output with response schema, batched validation (25 entries/batch), tool-specific prompts
- Enable: `GEMINI_ENABLED=true` + `GEMINI_API_KEY`

**People Data Labs (PDL) (Optional):**
- Purpose: Contact enrichment (phones, emails, social profiles)
- Base URL: `https://api.peopledatalabs.com/v5`
- Client: Direct `httpx` calls in `backend/app/services/enrichment/pdl_provider.py`
- Auth: API key via `X-Api-Key` header, configured via `PDL_API_KEY` env var
- Enable: `ENRICHMENT_ENABLED=true` + `PDL_API_KEY`

**SearchBug (Optional):**
- Purpose: Public records enrichment (deceased status, bankruptcy, liens, phone lookup)
- Base URL: `https://api.searchbug.com/api`
- Client: Direct `httpx` calls with retry logic in `backend/app/services/enrichment/searchbug_provider.py`
- Auth: API key as query parameter, configured via `SEARCHBUG_API_KEY` env var
- Enable: `ENRICHMENT_ENABLED=true` + `SEARCHBUG_API_KEY`

**Google Maps Geocoding (Optional):**
- Purpose: Address validation and standardization
- Client: `requests` in `backend/app/services/address_validation_service.py`
- Auth: API key via `GOOGLE_MAPS_API_KEY` env var
- Rate limit: Self-imposed 40 QPS (under Google's 50 QPS limit)
- Enable: `GOOGLE_MAPS_ENABLED=true` + `GOOGLE_MAPS_API_KEY`

## Data Storage

**Databases:**

*Firestore (Primary):*
- Project: `tablerockenergy`
- Database: `tablerocktools` (named database, not default)
- Client: `google.cloud.firestore.AsyncClient` with lazy init (`backend/app/services/firestore_service.py`)
- Connection: Uses Application Default Credentials or `GOOGLE_APPLICATION_CREDENTIALS`
- Collections:
  - `users` - User profiles synced from Firebase Auth
  - `jobs` - Processing job records (all tools)
  - `extract_entries` - Extract tool results
  - `title_entries` - Title tool results
  - `proration_rows` - Proration tool results
  - `revenue_statements` - Revenue tool results (deterministic IDs for upsert)
  - `rrc_oil_proration` - RRC oil data (keyed by `{district}-{lease_number}`)
  - `rrc_gas_proration` - RRC gas data (same key pattern)
  - `rrc_data_syncs` - RRC sync history/status
  - `rrc_county_status` - County-level download freshness tracking
  - `audit_logs` - User action audit trail
  - `app_config` - Application settings (allowlist, enrichment config)
  - `user_preferences` - Per-user preferences
- Batch limit: 500 documents per batch commit

*PostgreSQL (Optional, disabled by default):*
- Version: 16 (Alpine, via Docker Compose)
- Connection: `postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox`
- ORM: SQLAlchemy 2.0+ with async engine (`backend/app/core/database.py`)
- Migrations: Alembic (`backend/requirements.txt`)
- Models: `backend/app/models/db_models.py`
- Enable: `DATABASE_ENABLED=true` + `DATABASE_URL`
- Purpose: Optional local dev alternative to Firestore

**File Storage:**

*Google Cloud Storage (Primary):*
- Bucket: `table-rock-tools-storage`
- Project: `tablerockenergy`
- Client: `google.cloud.storage.Client` with lazy init (`backend/app/services/storage_service.py`)
- Folders:
  - `rrc-data/` - RRC CSV files (`oil_proration.csv`, `gas_proration.csv`)
  - `uploads/` - User file uploads (organized by `{tool}/{user_id}/{timestamp}_{filename}`)
  - `profiles/` - User profile images
- Features: Signed URLs for temporary access, automatic bucket creation
- Fallback: Transparent local filesystem fallback to `backend/data/` when GCS unavailable

*Local Filesystem (Fallback):*
- Base path: `backend/data/`
- Used when: GCS credentials not available (local dev without service account)
- Contains: `allowed_users.json` (auth allowlist), RRC CSVs, uploads

**Caching:**
- In-memory pandas DataFrame caching for RRC data lookups (`backend/app/services/proration/csv_processor.py`)
- No Redis or external cache service

## Authentication & Identity

**Auth Provider: Firebase Authentication**
- Project: `tablerockenergy`
- Methods: Google Sign-In + email/password
- Frontend SDK: `firebase` 12.9.x (`frontend/src/lib/firebase.ts`)
- Backend verification: `firebase-admin` SDK (`backend/app/core/auth.py`)
- Flow:
  1. User authenticates via Firebase (Google OAuth or email/password)
  2. Frontend obtains ID token from Firebase
  3. Backend verifies token via `firebase_admin.auth.verify_id_token()`
  4. Backend checks email against JSON allowlist
- Allowlist: `backend/data/allowed_users.json` (local cache), Firestore `app_config/allowed_users` (source of truth)
- Default admin: `james@tablerocktx.com`
- Roles: `admin`, `user`, `viewer`
- Scopes: `all`, `land`, `revenue`, `operations`
- Password management: Backend can create/update Firebase user passwords via Admin SDK (`set_user_password()`)
- Initialization: Lazy (Firebase Admin SDK initialized on first auth request)
- Dev fallback: If Firebase Admin not configured, auth verification is skipped with a warning

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, or similar)
- Errors logged to stdout via Python `logging` module

**Logs:**
- Python `logging.getLogger(__name__)` per module
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s` (`backend/app/main.py`)
- Level: INFO by default, DEBUG when `DEBUG=true`
- Cloud Run captures stdout/stderr to Cloud Logging automatically

**Audit:**
- Custom audit log in Firestore `audit_logs` collection (`backend/app/services/firestore_service.py`)
- Tracks: action, user_id, resource_type, resource_id, IP address, user agent

## CI/CD & Deployment

**Hosting:**
- Google Cloud Run (serverless containers)
- Region: us-central1
- Service name: `table-rock-tools`
- URL: `https://tools.tablerocktx.com`
- Min instances: 0 (scales to zero)
- Max instances: 10

**CI Pipeline:**
- GitHub Actions (`.github/workflows/deploy.yml`)
- Trigger: Push to `main` branch or manual `workflow_dispatch`
- Steps:
  1. Checkout code
  2. Authenticate to GCP via service account key (`GCP_SA_KEY` secret)
  3. Setup gcloud SDK
  4. Deploy via `gcloud run deploy --source .` (Cloud Build builds container on GCP)
- No test/lint step in CI pipeline (only deploy)

**Container Build:**
- `Dockerfile` - Multi-stage (Node 20-slim + Python 3.11-slim)
- System deps installed: `poppler-utils`, `tesseract-ocr`, `build-essential`, `curl`
- Frontend built to `static/` directory, served by FastAPI catch-all route

## Environment Configuration

**Required env vars (production):**
- `GOOGLE_APPLICATION_CREDENTIALS` or GCP metadata (for Firestore + GCS + Firebase Admin)
- All other vars have defaults that work for production on Cloud Run

**Optional env vars (feature flags):**
- `GEMINI_API_KEY` + `GEMINI_ENABLED=true` - AI validation
- `PDL_API_KEY` + `ENRICHMENT_ENABLED=true` - PDL enrichment
- `SEARCHBUG_API_KEY` + `ENRICHMENT_ENABLED=true` - SearchBug enrichment
- `GOOGLE_MAPS_API_KEY` + `GOOGLE_MAPS_ENABLED=true` - Address validation
- `ENCRYPTION_KEY` - Fernet key for encrypting stored API keys (GHL tokens)
- `DATABASE_URL` + `DATABASE_ENABLED=true` - PostgreSQL

**Secrets location:**
- GitHub Actions secret: `GCP_SA_KEY` (GCP service account JSON)
- Runtime: GCP Application Default Credentials (Cloud Run service account)
- API keys: Environment variables on Cloud Run service
- GHL tokens: Encrypted in Firestore using Fernet (`ENCRYPTION_KEY`)

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- GoHighLevel contact upsert (push contacts via REST API)
- RRC data download (pull CSV data via form submission)
- PDL person enrichment (pull enrichment data via REST API)
- SearchBug people search (pull public records via REST API)
- Google Maps geocoding (pull address validation via REST API)
- Gemini AI content generation (pull validation suggestions via REST API)

---

*Integration audit: 2026-03-10*
