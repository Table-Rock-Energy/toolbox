# Architecture Patterns: v1.5 Enrichment Pipeline & Bug Fixes

**Domain:** Internal document-processing tools with post-processing enrichment
**Researched:** 2026-03-13
**Confidence:** HIGH (based on direct codebase analysis)

## Recommended Architecture

v1.5 integrates six feature areas into the existing tool-per-module pattern. The key architectural insight: **most v1.5 work modifies existing components rather than creating new ones**. Only the universal post-processing hook requires net-new frontend code. Everything else is wiring existing infrastructure to more tool pages or fixing data flow bugs.

### Integration Map: New vs Modified

| Feature | New Components | Modified Components |
|---------|---------------|-------------------|
| GHL Smart List | None (method on existing client) | `ghl/client.py` (add method), `bulk_send_service.py` (call after batch), `api/ghl.py` (thread smart_list_name) |
| Universal Validate/CleanUp/Enrich | `hooks/usePostProcess.ts` (shared hook) | `data_enrichment_pipeline.py` (add FIELD_MAPS), `api/title.py`, `api/proration.py`, `api/revenue.py` (add /enrich endpoints) |
| Preview updates | None | Each tool page (update entries state after enrichment stream completes) |
| Tool-specific Gemini prompts | None (already exist in gemini_service.py) | Possibly extend TOOL_PROMPTS for cleanup-specific use cases |
| ECF upload flow fix | None | `Extract.tsx` (decouple file selection from processing) |
| RRC fetch-missing repair | None | `api/proration.py` (use results directly), `models/proration.py` (add lease_results field) |

---

## Component Boundaries

### Backend Components

| Component | Responsibility | v1.5 Changes |
|-----------|---------------|--------------|
| `ghl/client.py` | GHL API HTTP client with rate limiting | Add `create_smart_list()` method |
| `ghl/bulk_send_service.py` | Batch validation, async processing, job persistence | Call smart list creation after batch completes, accept `smart_list_name` param |
| `api/ghl.py` | GHL route handlers, SSE streaming | Thread `smart_list_name` through to `process_batch_async()` |
| `data_enrichment_pipeline.py` | Multi-step enrichment orchestrator | Already tool-agnostic via `FIELD_MAPS`. Add maps for `proration` and `revenue` |
| `gemini_service.py` | AI validation with per-tool prompts | `TOOL_PROMPTS` already covers all 4 tools. No changes needed |
| `api/title.py` | Title route handlers | Add `/enrich` endpoint (3 lines, delegates to pipeline) |
| `api/proration.py` | Proration route handlers | Add `/enrich` endpoint + fix fetch-missing result consumption |
| `api/revenue.py` | Revenue route handlers | Add `/enrich` endpoint |
| `rrc_county_download_service.py` | County-level RRC downloads, individual lease fetch | No changes to fetch logic; fix is in how `api/proration.py` consumes results |
| `models/proration.py` | Proration Pydantic models | Add `lease_results` field to `FetchMissingResult` |

### Frontend Components

| Component | Responsibility | v1.5 Changes |
|-----------|---------------|-------------|
| `Extract.tsx` | Extract tool page | Fix ECF auto-detect flow (decouple file select from upload) |
| `Title.tsx` | Title tool page | Add Validate/CleanUp/Enrich buttons using `usePostProcess` hook |
| `Proration.tsx` | Proration tool page | Add Validate button + display fetch-missing lease results |
| `Revenue.tsx` | Revenue tool page | Add Validate/CleanUp buttons |
| `hooks/usePostProcess.ts` | **NEW** shared hook for enrichment state | Encapsulates streaming API call, progress tracking, entry replacement |
| `EnrichmentProgress.tsx` | Progress display for enrichment steps | Reuse as-is across all tools |
| `AiReviewPanel.tsx` | AI suggestion review/accept/reject | Reuse as-is across all tools |
| `GhlSendModal.tsx` | GHL bulk send configuration | Show smart list creation result after job completes |

---

## Detailed Integration Points

### 1. GHL Smart List Creation

**Current state:** `smart_list_name` is accepted in `BulkSendRequest` model (line 109 of `models/ghl.py`) but only used as a reference label stored in Firestore job docs. No GHL API call actually creates a smart list.

**Where it goes:** New method on `GHLClient` in `ghl/client.py`:

```python
async def create_smart_list(self, name: str, tag_filter: str) -> dict | None:
    """Create a GHL smart list filtered by tag.

    Smart lists in GHL are saved search filters, not static contact lists.
    Creates a filter matching contacts with the given campaign tag.
    """
    try:
        return await self._request(
            "POST",
            "/contacts/search/",
            json={
                "locationId": self.location_id,
                "name": name,
                "filters": [{"field": "tags", "operator": "contains", "value": tag_filter}],
            },
        )
    except GHLAPIError as e:
        logger.warning("Smart list creation failed: %s", e)
        return None
```

**Threading through bulk_send_service.py:** `process_batch_async()` currently accepts `(job_id, connection_id, contacts, tags, assigned_to_list)`. Add `smart_list_name: str | None = None` parameter. After the completion block (around line 557), add smart list creation:

```python
# After updating job status to "completed"
if smart_list_name and tags:
    try:
        await client.create_smart_list(name=smart_list_name, tag_filter=tags[0])
        await doc_ref.update({"smart_list_created": True})
    except Exception as e:
        logger.warning("Smart list creation failed for job %s: %s", job_id, e)
        await doc_ref.update({"smart_list_created": False, "smart_list_error": str(e)})
```

**In api/ghl.py `bulk_send_endpoint()`:** Pass `smart_list_name` through to the background task (line 355):

```python
asyncio.create_task(
    process_batch_async(
        job_id=job_id,
        connection_id=data.connection_id,
        contacts=valid_contacts,
        tags=tags,
        assigned_to_list=data.assigned_to_list,
        smart_list_name=data.smart_list_name,  # ADD THIS
    )
)
```

**IMPORTANT CAVEAT:** The exact GHL v2 API for smart list creation needs verification. Prior research (PITFALLS-GHL-API.md line 327) confirms smart lists are NOT created by sending a `smartList` field with contact upsert -- they require a separate API call. The endpoint path and payload format need phase-specific research against the current GHL API docs. **Flag for validation before implementation.**

### 2. Universal Validate/CleanUp/Enrich Across All Tools

**Current state:**
- `data_enrichment_pipeline.py` has two entry points:
  - `auto_enrich()` -- synchronous pipeline run during upload (returns `PostProcessResult`)
  - `enrich_entries()` -- streaming pipeline yielding NDJSON events
- `FIELD_MAPS` currently only maps `extract` and `title`
- Extract.tsx has full enrichment UI; other tool pages do not

**Shared hook design (`hooks/usePostProcess.ts`):**

```typescript
interface UsePostProcessOptions {
  toolName: string
  getAuthHeaders: () => Promise<Record<string, string>>
}

function usePostProcess({ toolName, getAuthHeaders }: UsePostProcessOptions) {
  const [isRunning, setIsRunning] = useState(false)
  const [steps, setSteps] = useState<EnrichmentStep[]>([])
  const [summary, setSummary] = useState<EnrichmentSummary | null>(null)
  const [isComplete, setIsComplete] = useState(false)

  const runPipeline = async (entries: unknown[]): Promise<unknown[] | null> => {
    setIsRunning(true)
    setIsComplete(false)
    setSteps(DEFAULT_STEPS.map(s => ({ ...s, status: 'pending' })))

    const headers = await getAuthHeaders()
    const response = await fetch(`/api/${toolName}/enrich`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries }),
    })

    // Stream NDJSON, update steps, return final entries
    // (Extract logic from Extract.tsx lines 285-360)
    ...
    return finalEntries
  }

  return { isRunning, steps, summary, isComplete, runPipeline }
}
```

**Backend per-tool enrich endpoints (3 lines each):**

```python
# In api/title.py
@router.post("/enrich")
async def enrich_title_entries(request: EnrichRequest):
    from app.services.data_enrichment_pipeline import enrich_entries
    return StreamingResponse(enrich_entries("title", request.entries), media_type="application/x-ndjson")

# In api/proration.py
@router.post("/enrich")
async def enrich_proration_entries(request: EnrichRequest):
    from app.services.data_enrichment_pipeline import enrich_entries
    return StreamingResponse(enrich_entries("proration", request.entries), media_type="application/x-ndjson")

# In api/revenue.py
@router.post("/enrich")
async def enrich_revenue_entries(request: EnrichRequest):
    from app.services.data_enrichment_pipeline import enrich_entries
    return StreamingResponse(enrich_entries("revenue", request.entries), media_type="application/x-ndjson")
```

**`FIELD_MAPS` additions in `data_enrichment_pipeline.py`:**

```python
FIELD_MAPS = {
    "extract": { ... },  # Exists
    "title": { ... },     # Exists
    "proration": {
        "name": "owner",
        "street": "address",
        "street_2": "",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
        "entity_type": "entity_type",
    },
    "revenue": {
        # Revenue enrichment is primarily financial QA, not contact enrichment
        # Only name_casing and AI steps apply; address/enrichment steps are skipped
        "name": "property_name",
        "street": "",
        "city": "",
        "state": "",
        "zip": "",
    },
}
```

**Which steps apply per tool:**

| Step | Extract | Title | Proration | Revenue |
|------|---------|-------|-----------|---------|
| Address validation (Google Maps) | Yes | Yes | Maybe | No |
| Places lookup (Google Places) | Yes | Yes | No | No |
| Contact enrichment (PDL/SB) | Yes | Yes | No | No |
| Name validation (Gemini) | Yes | Yes | Yes | No |
| Name splitting | Yes | Yes | No | No |
| Product code inference | No | No | No | Yes |
| Financial math verification | No | No | No | Yes |
| Revenue field propagation | No | No | No | Yes |

The pipeline already handles this via conditional checks (`if tool in ("extract", "title")`, `if tool == "revenue"`). No new branching needed.

**Conditional button rendering (frontend):**

```typescript
// On tool page mount, check which services are available
useEffect(() => {
  aiApi.getStatus().then(s => setAiEnabled(s.enabled))
  enrichmentApi.getStatus().then(s => setEnrichmentEnabled(s.enabled))
}, [])

// Render buttons conditionally
<button onClick={handleCleanUp}>Clean Up</button>               {/* Always */}
{aiEnabled && <button onClick={handleValidate}>Validate</button>}
{enrichmentEnabled && <button onClick={handleEnrich}>Enrich</button>}
```

### 3. Preview Updates After Enrichment

**Current state in Extract.tsx (working pattern):** After enrichment stream completes, the `complete` event includes the modified `entries` array. Frontend replaces entries in component state (lines 341-348):

```typescript
if (event.step === 'complete' && event.entries) {
  setActiveJob({
    ...activeJob,
    result: { ...activeJob.result, entries: event.entries },
  })
}
```

**Replication pattern:** Each tool page must:
1. Call `/api/{tool}/enrich` with current entries
2. Read NDJSON stream, update progress UI via `usePostProcess` hook
3. On `complete` event, replace entries in component state
4. Table re-renders automatically (React state update triggers re-render)

**No backend persistence occurs.** Entries are ephemeral in frontend state until the user exports. This is the correct pattern -- there is no reason to save intermediate enrichment state to Firestore.

### 4. Tool-Specific Gemini Prompts

**Current state:** Already complete. `gemini_service.py` has `TOOL_PROMPTS` dict (lines 124-166) with prompts for all four tools:
- `extract`: Name casing, entity type mismatch, address completeness, state/ZIP format
- `title`: Name casing, entity type, duplicate detection, first/last parsing, address
- `proration`: County spelling, interest range, legal description, owner formatting
- `revenue`: Product code, interest sanity, financial math, date consistency, net revenue

Additionally, `data_enrichment_pipeline.py` has `NAME_VALIDATION_PROMPT` (line 83-92) for streaming pipeline name cleanup.

**No changes needed** unless the user wants specific new prompts. The separation is correct: `TOOL_PROMPTS` for the AI Review button, `NAME_VALIDATION_PROMPT` for the streaming pipeline's name step.

### 5. ECF Upload Flow Fix

**Current state:** `handleFilesSelected()` in Extract.tsx (line 362) immediately uploads the file. Format detection happens via the `formatHint` state which is set by a dropdown. The problem: when auto-detection should set the format, the upload has already started.

**Fix approach (Extract.tsx only):**

```typescript
// New state
const [pendingFile, setPendingFile] = useState<File | null>(null)

// Decouple: handleFilesSelected stores file, does NOT upload
const handleFilesSelected = async (files: File[]) => {
  if (files.length === 0) return
  const file = files[0]

  // Auto-detect format from filename
  const isEcf = file.name.toLowerCase().includes('ecf') ||
                file.name.toLowerCase().includes('multiunit')
  const detectedFormat = isEcf ? 'ECF' : ''

  setPendingFile(file)
  setFormatHint(detectedFormat)

  if (!isEcf) {
    // Standard: process immediately (existing behavior)
    await processUpload(file, null, '')
  }
  // ECF: user sees CSV upload slot + Process button, waits for click
}

// New handler for explicit ECF processing
const handleProcessEcf = async () => {
  if (!pendingFile) return
  await processUpload(pendingFile, csvFile, formatHint)
}
```

**UI change:** When `formatHint === 'ECF' && pendingFile`, show:
- Filename of pending PDF
- CSV upload slot (existing)
- Explicit "Process" button

**No backend changes.** Backend already accepts `format_hint` query param and optional `csv_file`.

### 6. RRC Fetch-Missing Multi-Lease Repair

**The bug:** In `api/proration.py` `fetch_missing_rrc_data()`, after `fetch_individual_leases()` returns results, the code re-looks up Firestore (lines 437-439) instead of using the returned data directly. If the Firestore upsert from the individual fetch hasn't committed yet (async timing), the re-lookup misses.

**Fix in `api/proration.py` (lines 434-442):**

```python
# BEFORE (broken):
if individual_results:
    for row_idx, district, lease_number, _cc in missing_leases:
        row = updated_rows[row_idx]
        rrc_info = await lookup_rrc_acres(district, lease_number)     # Re-lookup Firestore
        if rrc_info is None:
            rrc_info = await lookup_rrc_by_lease_number(lease_number)  # Fallback
        if rrc_info:
            _apply_rrc_info(row, rrc_info, WellType)
            matched += 1

# AFTER (fixed):
if individual_results:
    for row_idx, district, lease_number, _cc in missing_leases:
        key = (district, lease_number)
        rrc_info = individual_results.get(key)  # Use fetched data directly
        if rrc_info:
            row = updated_rows[row_idx]
            _apply_rrc_info(row, rrc_info, WellType)
            matched += 1
```

**Surface results to user:** Add `lease_results` to `FetchMissingResult`:

```python
# models/proration.py
class FetchMissingResult(BaseModel):
    updated_rows: list[MineralHolderRow]
    matched_count: int
    still_missing_count: int
    counties_downloaded: list[dict] = Field(default_factory=list)
    lease_results: list[dict] = Field(default_factory=list)  # NEW
```

Populate in the endpoint:

```python
lease_results = []
for d, ln in individual_results:
    info = individual_results[(d, ln)]
    lease_results.append({
        "district": d,
        "lease_number": ln,
        "acres": info.get("acres"),
        "operator": info.get("operator"),
        "status": "found",
    })

return FetchMissingResult(
    ...,
    lease_results=lease_results,
)
```

---

## Data Flow: Enrichment Pipeline (Universal)

```
Frontend Tool Page
  |
  | POST /api/{tool}/enrich  { entries: [...] }
  v
api/{tool}.py -> enrich endpoint
  |
  | StreamingResponse (NDJSON)
  v
data_enrichment_pipeline.enrich_entries(tool, entries)
  |
  +-- Step 1: Address validation (Google Maps)    -> yield progress events
  +-- Step 2: Places lookup (Google Places)       -> yield progress events
  +-- Step 3: Contact enrichment (PDL/SearchBug)  -> yield progress events
  +-- Step 4: Name validation (Gemini AI)         -> yield progress events
  +-- Step 5: Name splitting                      -> yield progress events
  +-- Final: yield { step: "complete", entries: [...modified...] }
  |
  v
Frontend reads NDJSON stream via ReadableStream
  -> Updates EnrichmentProgress component with step status
  -> On "complete": replaces entries in activeJob/activeResult state
  -> Table re-renders with enriched/corrected data
```

## Data Flow: GHL Bulk Send + Smart List

```
Frontend GhlSendModal
  |
  | POST /api/ghl/contacts/bulk-send
  |   { connection_id, contacts, campaign_tag, smart_list_name, ... }
  v
api/ghl.py -> bulk_send_endpoint()
  |
  +-- validate_batch(contacts) -> valid + invalid split
  +-- create_send_job(job_id, ..., campaign_name=smart_list_name)
  +-- asyncio.create_task(process_batch_async(..., smart_list_name))
        |
        +-- For each contact: upsert_contact() via GHLClient
        +-- Update Firestore progress after each contact
        +-- On completion:
        |     +-- create_smart_list(smart_list_name, tag_filter)  <- NEW
        |     +-- Update job: smart_list_created = true/false
        +-- Update job status to "completed"
  |
  v (parallel)
Frontend SSE: GET /api/ghl/send/{job_id}/progress
  -> Progress bar updates as contacts are processed
  -> On "complete" event: show results + smart list creation status
```

---

## Patterns to Follow

### Pattern 1: Streaming Enrichment via NDJSON
Already proven in Extract.tsx enrichment flow. Backend yields newline-delimited JSON; frontend reads via `ReadableStream.getReader()`. Use this for any multi-step processing taking more than 2 seconds.

### Pattern 2: Feature-Gated UI Buttons
Check `/api/ai/status` and `/api/enrichment/status` on page mount. Only render action buttons when the backing service is configured. Clean Up button always shows (no external dependency).

### Pattern 3: Delegate to Shared Pipeline
Per-tool `/enrich` endpoints are thin wrappers (3 lines) around `data_enrichment_pipeline.enrich_entries(tool, entries)`. The pipeline handles tool-specific logic via `FIELD_MAPS` and conditional step execution.

### Pattern 4: Entry State Replacement (not mutation)
After enrichment, create a new entries array and set it via React state setter. Never mutate the existing array in place. This ensures React re-renders correctly.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shared Mega-Component for Post-Processing
Each tool page has different entry shapes, different applicable enrichment steps, and different UI layouts. A single `<PostProcessPanel>` component would need excessive configuration and become unmaintainable. Use a shared hook for logic, tool-specific rendering in each page.

### Anti-Pattern 2: Backend Persistence of Enriched Entries
Entries are ephemeral in frontend state. Saving to Firestore after enrichment creates stale data and complex invalidation. Only export results (files) get persisted.

### Anti-Pattern 3: Duplicating Enrichment Endpoint Logic
Do not copy the streaming response setup into each tool router file. Use thin delegating endpoints that call the shared pipeline.

### Anti-Pattern 4: Re-Looking Up Firestore After Individual Fetch
The current fetch-missing bug. When `fetch_individual_leases()` returns data, use it directly rather than re-querying Firestore where the upsert may not have committed yet.

---

## Suggested Build Order

### Phase 1: ECF Upload Flow Fix (frontend only, no dependencies)
- Modify `Extract.tsx`: decouple file selection from processing
- Add `pendingFile` state, auto-detect from filename, explicit Process button
- Self-contained, immediate UX improvement, zero backend risk

### Phase 2: RRC Fetch-Missing Repair (backend + frontend)
- Fix `api/proration.py` to use `individual_results` directly (not Firestore re-lookup)
- Add `lease_results` to `FetchMissingResult` model
- Update `Proration.tsx` to display per-lease lookup outcomes
- Fixes existing broken flow, low risk

### Phase 3: GHL Smart List Creation (backend, needs API verification)
- **Research first:** verify exact GHL v2 API endpoint for smart list/saved search creation
- Add `create_smart_list()` to `GHLClient`
- Thread `smart_list_name` through `process_batch_async()`
- Call after batch completes, update job doc with result
- Medium risk: GHL API behavior may differ from expectations

### Phase 4: Universal Enrichment UI (backend + frontend, largest scope)
- Add `FIELD_MAPS` entries for proration and revenue in `data_enrichment_pipeline.py`
- Add `/enrich` endpoints to title, proration, revenue routers
- Create `hooks/usePostProcess.ts` shared hook (extract logic from Extract.tsx)
- Add Validate/CleanUp/Enrich buttons to Title.tsx, Proration.tsx, Revenue.tsx
- Wire `EnrichmentProgress` and `AiReviewPanel` components to each tool page
- Follows established Extract.tsx pattern, but largest scope

### Phase 5: Preview Updates (frontend, depends on Phase 4)
- Wire enrichment stream completion to entry state replacement in each tool page
- Pattern exists in Extract.tsx -- replicate to other tool pages
- Low risk once Phase 4 is done

**Phase ordering rationale:**
- Phases 1 and 2 are independent bug fixes -- do first for quick wins
- Phase 3 (GHL) is independent but needs API research -- can run in parallel
- Phase 4 is the core feature work -- depends on understanding from Phase 1 (Extract.tsx patterns)
- Phase 5 is a natural continuation of Phase 4

---

## Sources

- Direct codebase analysis (HIGH confidence)
- `backend/app/services/data_enrichment_pipeline.py` -- existing enrichment orchestrator with streaming
- `backend/app/services/ghl/client.py` -- GHL API client with rate limiting
- `backend/app/services/ghl/bulk_send_service.py` -- bulk send with async processing
- `backend/app/api/ghl.py` -- GHL route handlers
- `backend/app/services/gemini_service.py` -- AI validation with TOOL_PROMPTS for all 4 tools
- `backend/app/api/proration.py` -- fetch-missing endpoint (bug identified at lines 434-442)
- `backend/app/services/proration/rrc_county_download_service.py` -- individual lease HTML scraping
- `frontend/src/pages/Extract.tsx` -- existing enrichment UI pattern (the template for other tools)
- `backend/app/models/ghl.py` -- BulkSendRequest with smart_list_name field
- `.planning/research/PITFALLS-GHL-API.md` line 327 -- smart list requires separate API call
