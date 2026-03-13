# Technology Stack — v1.5 Enrichment Pipeline & Bug Fixes

**Project:** Table Rock Tools v1.5
**Researched:** 2026-03-13

## Summary

**NO NEW DEPENDENCIES REQUIRED.** All v1.5 features are bug fixes, API integration corrections, and UI wiring using existing libraries. The key challenge is understanding external API capabilities and limitations, not adding new packages.

## Critical Finding: GHL Smart Lists

**GHL SmartLists are NOT creatable via API.** This was documented in earlier research (FEATURES-GHL-API.md) and confirmed by codebase review. SmartLists in GoHighLevel are filter-based saved views, not membership lists. The GHL API v2 (version `2021-07-28`, base URL `https://services.leadconnectorhq.com`) does not expose endpoints for creating or managing SmartLists.

**What the app currently does:** Applies a `campaign_tag` to all contacts during bulk send. The `smart_list_name` field in `BulkSendRequest` is stored for reference only -- it is never sent to GHL as a SmartList creation call.

**The fix is a workflow, not code:**
1. Tag contacts with campaign tag (already works)
2. User creates SmartList in GHL UI filtered by that tag (manual step)
3. Document this workflow clearly in the app's Help page and send confirmation modal

**Confidence:** HIGH -- Prior research confirmed this, codebase confirms `smart_list_name` is only used for Firestore job persistence (`campaign_name = data.smart_list_name or data.campaign_tag`), never sent to GHL API.

## Stack for Each v1.5 Feature

### 1. GHL Smart List "Fix" (Workflow Documentation)

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| GHL API v2 | Yes (`services/ghl/client.py`) | Contact upsert with tags | No change -- tagging already works |
| React frontend | Yes | Send modal UI | Clarify UI text: "Campaign Tag" creates a GHL tag, user creates SmartList manually |

**No new endpoints, no new libraries.** The "fix" is:
- Rename "SmartList Name" field to "Campaign Tag" in `GhlSendModal.tsx` (it already IS a tag)
- Add help text explaining the SmartList creation workflow
- Optionally add a post-send instruction: "Create a SmartList in GHL filtered by tag: [campaign_tag]"

### 2. Three-Button Enrichment UI (Validate / Clean Up / Enrich)

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| Gemini AI (`google-genai`) | Yes | "Validate" button -- QA pass | Tool-specific prompts already exist in `TOOL_PROMPTS` dict. Need to extend with "cleanup" prompts. |
| Google Maps Geocoding API | Yes (`address_validation_service.py`) | "Clean Up" button -- address standardization | Already implemented as `validate_addresses_batch()`. Need to wire to frontend. |
| PDL + SearchBug | Yes (`enrichment/`) | "Enrich" button -- contact data enrichment | Already implemented as `enrichment_service.py`. Need to wire to frontend. |
| React | Yes | Button bar component | New shared component: `EnrichmentButtonBar.tsx` with three conditional buttons |

**Key integration points (already exist in backend):**

| Service | Endpoint | Status |
|---------|----------|--------|
| Gemini validation | `POST /api/ai/review` | Working -- accepts `{tool, entries}` |
| Address validation | None (service-only) | Needs new endpoint: `POST /api/validate/addresses` |
| Contact enrichment | `POST /api/enrichment/enrich` | Working -- needs wiring to tool pages |

**Feature switches (already exist in `config.py`):**

| Setting | Property | Controls |
|---------|----------|----------|
| `gemini_enabled` + `gemini_api_key` | `settings.use_gemini` | Validate button visibility |
| `google_maps_enabled` + `google_maps_api_key` | `settings.use_google_maps` | Clean Up button visibility |
| `enrichment_enabled` + `pdl_api_key`/`searchbug_api_key` | `settings.use_enrichment` | Enrich button visibility |

**No new dependencies.** All three services are already installed and have backend implementations.

### 3. Preview Update Mechanism After Enrichment Steps

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| React state | Yes | Update preview data after each step | Pattern: POST entries to service endpoint, receive updated entries, replace React state |
| Pydantic models | Yes | Request/response models | `AiValidationResult` already has suggestions; address validation needs a batch response model |

**The pattern for all three buttons:**
```
Frontend state (entries[])
  --> POST to backend service endpoint
  --> Backend returns updated entries[] + change summary
  --> Frontend replaces state with updated entries[]
  --> DataTable re-renders with new data
```

**Existing model that works for this:** `PostProcessResult` in `models/ai_validation.py` already has `corrections` (auto-applied) and `ai_suggestions` (manual review). This pattern can be reused for all three enrichment steps.

**No new dependencies.** React state management with `useState` is sufficient -- no need for Redux/Zustand.

### 4. Tool-Specific Gemini QA Prompts

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| `google-genai` | Yes | Gemini API client | No package changes |
| Gemini 2.5 Flash | Yes (model: `gemini-2.5-flash`) | QA validation | No model changes |

**Current prompts already exist in `gemini_service.py`:**

| Tool | Prompt Key | Current Focus | v1.5 Enhancement |
|------|-----------|---------------|------------------|
| `extract` | `TOOL_PROMPTS["extract"]` | Name casing, entity type, address completeness | Add: cleanup-specific prompt for ALL CAPS to Title Case batch correction |
| `title` | `TOOL_PROMPTS["title"]` | Name casing, entity type, duplicate detection | Add: cleanup-specific prompt for first/last name splitting |
| `proration` | `TOOL_PROMPTS["proration"]` | County spelling, interest range, legal description | Add: cleanup-specific prompt for county name standardization |
| `revenue` | `TOOL_PROMPTS["revenue"]` | Product code, interest sanity, financial math | No change needed -- `REVENUE_VERIFY_PROMPT` already handles verification |

**Implementation approach:** Add a second prompt set (`CLEANUP_PROMPTS`) alongside existing `TOOL_PROMPTS`. The "Validate" button uses `TOOL_PROMPTS` (review-only, suggestions). The "Clean Up" button uses `CLEANUP_PROMPTS` (apply corrections directly).

**Structured output already works:** `RESPONSE_SCHEMA` defines the JSON schema for Gemini responses. `response_mime_type="application/json"` and `response_json_schema=RESPONSE_SCHEMA` are already configured. Temperature is 0.1 (deterministic). No changes needed to the API call pattern.

**Rate limiting already handled:** `_check_rate_limit()` enforces MAX_RPM=10, MAX_RPD=250, monthly budget cap. Batch size is 25 entries per API call with 6s delay between batches.

**No new dependencies.** Prompt engineering only.

### 5. Google Maps Address Validation (Clean Up Button)

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| Google Maps Geocoding API | Yes | Address standardization | Already implemented in `address_validation_service.py` |
| `requests` | Yes | HTTP client for Maps API | Already used by the service |

**Current implementation is complete and production-ready:**
- `validate_address()` -- single address validation via Geocoding API
- `validate_addresses_batch()` -- batch validation with progress callback
- Rate limiting at 40 QPS (under Google's 50 QPS limit)
- Change detection with before/after comparison
- Property type classification (residential/commercial/PO box)

**What's missing is only the API endpoint.** The service exists but is only called internally. Need:
- `POST /api/validate/addresses` endpoint that accepts entries and returns corrected entries
- Frontend button to trigger it

**Important note on Google Maps Address Validation API vs Geocoding API:**
The current service uses the **Geocoding API** (`maps.googleapis.com/maps/api/geocode/json`), not the dedicated **Address Validation API** (`addressvalidation.googleapis.com`). The Geocoding API is sufficient for address standardization (correcting street/city/state/zip). The Address Validation API provides deeper validation (USPS deliverability, component-level confirmation) but costs $0.005/request vs Geocoding's $0.005/request (same price tier). The Geocoding API approach is already working -- no reason to switch.

**Confidence:** HIGH -- existing service is tested and functional. The Geocoding API is the correct choice for address cleanup (standardize components, detect changes). Switching to Address Validation API would add complexity without meaningful benefit for this use case.

### 6. RRC Multi-Lease Number Lookups

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| `requests` | Yes | HTTP to RRC website | Already used in `rrc_data_service.py` and `rrc_county_download_service.py` |
| BeautifulSoup4 + lxml | Yes | HTML parsing | Already used for individual lease lookups |
| pandas | Yes | CSV parsing | Already used for RRC data processing |

**Multi-lease lookup already works in-memory:**
`rrc_data_service.lookup_multiple_acres()` already handles comma-separated RRC lease strings (e.g., `"08-41100, 08-41101"`), parsing them and summing acres from the in-memory DataFrame.

**The bug is in `fetch_individual_leases()`:** When a row has multiple RRC lease numbers (comma-separated), the fetch-missing endpoint parses only the first district-lease pair from `rrc_lease`. The fix:
1. Parse ALL lease numbers from `row.rrc_lease` or `row.raw_rrc` (using existing `parse_all_rrc_leases()`)
2. Query each lease individually (already supported by `fetch_individual_leases()`)
3. Sum acres across all matched leases (pattern already in `lookup_multiple_acres()`)

**RRC scraping constraints (already coded):**
- `MAX_INDIVIDUAL_QUERIES = 25` per fetch-missing call
- `COUNTY_BUDGET_SECONDS = 180` (3 min per county)
- `TOTAL_BUDGET_SECONDS = 300` (5 min total)
- Human-like delays between queries (2-5s)
- Custom SSL adapter required (`RRCSSLAdapter` with `verify=False`)

**No new dependencies.** Bug fix in parsing logic only.

### 7. ECF Upload Flow Fix

| Technology | Already Installed | Purpose | What Changes |
|------------|------------------|---------|--------------|
| React | Yes | Upload UI | Fix auto-detect/auto-select/Process button flow |
| FastAPI | Yes | Upload endpoint | No backend changes -- fix is frontend-only |

**No new dependencies.** Frontend UX fix only.

## What NOT to Add

| Technology | Why NOT Needed |
|------------|----------------|
| GoHighLevel SmartList API | Does not exist. SmartLists are filter-based saved views, not API-creatable. Use tags instead. |
| Google Address Validation API | Geocoding API already provides address standardization. Same pricing, simpler integration. |
| `google-maps-services-python` | The `requests`-based Geocoding call in `address_validation_service.py` is simpler and already works. No need for a wrapper library. |
| Redux / Zustand | React `useState` is sufficient for preview state management. App already uses this pattern successfully across all tools. |
| WebSocket / Socket.IO | SSE (Server-Sent Events) via `sse-starlette` is already used for GHL send progress. No need for full duplex. |
| Celery / Redis | Background tasks use `asyncio.create_task()` and `BackgroundTasks`. App runs on single Cloud Run instance (1Gi memory). No need for distributed task queue. |
| New Gemini model | `gemini-2.5-flash` is already configured and working. No need to switch to a different model for QA prompts. |

## Configuration Status

All required environment variables already exist:

| Variable | Current Status | Needed For |
|----------|---------------|------------|
| `GEMINI_API_KEY` | Configured | Validate button |
| `GEMINI_ENABLED` | `false` (toggle) | Validate button visibility |
| `GOOGLE_MAPS_API_KEY` | Configured | Clean Up button |
| `GOOGLE_MAPS_ENABLED` | `false` (toggle) | Clean Up button visibility |
| `PDL_API_KEY` | Configured | Enrich button |
| `SEARCHBUG_API_KEY` | Configured | Enrich button |
| `ENRICHMENT_ENABLED` | `false` (toggle) | Enrich button visibility |
| `ENCRYPTION_KEY` | Required in production | GHL token encryption |

**No new environment variables needed.**

## New Endpoints Needed

| Method | Endpoint | Purpose | Backend Service |
|--------|----------|---------|-----------------|
| `POST` | `/api/validate/addresses` | Batch address validation for Clean Up button | `address_validation_service.validate_addresses_batch()` |
| `GET` | `/api/services/status` | Combined status of all enrichment services | Aggregate `use_gemini`, `use_google_maps`, `use_enrichment` |

All other endpoints already exist.

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| GHL Smart Lists | **HIGH** | Prior research + codebase confirms SmartLists are not API-creatable. The "fix" is UX documentation, not code. |
| Gemini QA prompts | **HIGH** | `google-genai` SDK with structured JSON output is already working. Adding new prompt templates is low-risk. |
| Address validation | **HIGH** | `address_validation_service.py` is fully implemented with batch support. Only needs API endpoint wiring. |
| Contact enrichment | **MEDIUM** | PDL + SearchBug services exist but have not been extensively tested in production. Wiring to frontend may surface edge cases. |
| RRC multi-lease | **HIGH** | `lookup_multiple_acres()` and `parse_all_rrc_leases()` already handle multi-lease parsing. Bug is in the fetch-missing path not using these functions. |
| ECF upload flow | **HIGH** | Frontend-only fix. No stack implications. |
| Preview updates | **MEDIUM** | Pattern is straightforward (POST/response/setState) but needs careful design to handle partial failures and maintain undo capability. |

## Sources

- Existing codebase analysis (all file paths referenced above)
- Prior GHL API research: `.planning/research/FEATURES-GHL-API.md` (2026-02-26) -- confirmed SmartLists are filter-based
- GHL API client: `backend/app/services/ghl/client.py` -- API version `2021-07-28`, base URL `services.leadconnectorhq.com`
- Google Maps Geocoding API: already integrated at `maps.googleapis.com/maps/api/geocode/json`
- Gemini SDK: already integrated via `google-genai` with structured output (`response_json_schema`)
- RRC scraping: `backend/app/services/proration/rrc_county_download_service.py` and `rrc_data_service.py`

**Note:** WebSearch and WebFetch were unavailable during this research. All findings are based on codebase analysis and prior research. GHL API endpoint availability should be re-verified against current GHL API documentation if the team wants to pursue SmartList creation. **Confidence on GHL SmartList unavailability: MEDIUM** -- while prior research and codebase both confirm this, the GHL API may have added new endpoints since the v1.2 research (Feb 2026). Recommend a manual check of `https://highlevel.stoplight.io/docs/integrations` before finalizing.
