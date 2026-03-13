# Feature Landscape: v1.5 Enrichment Pipeline & Bug Fixes

**Domain:** Multi-step document enrichment, GHL smart list integration, RRC data completeness
**Researched:** 2026-03-13
**Confidence:** MEDIUM (web search unavailable; based on codebase analysis, prior GHL API research, and domain knowledge)

## Table Stakes

Features users expect given the existing UI promises and broken flows. Missing = product feels broken.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|-------------|-------|
| GHL smart list creation during bulk send | Modal has SmartList name field that does nothing; users expect contacts to appear in a named list in GHL | MEDIUM | Existing bulk send service, GHL client | SmartLists in GHL are filter-based, NOT manual membership lists. Smart lists filter by tags/attributes, so the correct approach is ensuring the campaign tag matches a SmartList filter. See Anti-Features. |
| Preview updates after enrichment steps | Validate/Cleanup buttons exist but results never update the preview table; users click, wait, see nothing change | MEDIUM | Existing AiReviewPanel, address validation service, enrichment service | Core bug: enrichment endpoints return data but frontend doesn't merge results back into preview state. All three tool pages (Extract, Title, Proration) have this issue. |
| ECF upload: explicit Process button | ECF auto-processes on PDF upload before user can add CSV; users must upload both files first, THEN process | LOW | Existing Extract page dual-file upload | Currently `useEffect` triggers processing on PDF upload. Need to gate processing behind explicit button when ECF format detected. |
| RRC fetch-missing returns usable data | Endpoint exists, makes queries, but matched data doesn't surface to user or update the preview table | MEDIUM | Existing fetch-missing endpoint, Proration page | Two issues: (1) multi-lease rows (e.g., "02-12345/02-12346") not parsed; (2) results not merged back into Proration preview. |

## Differentiators

Features that elevate the app beyond basic document processing.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|-------------|-------|
| Universal 3-button enrichment bar | Validate (Google Maps) / Clean Up (Gemini) / Enrich (PDL/SearchBug) as conditional buttons across all tools | MEDIUM | Address validation service, Gemini service, enrichment service, feature flags per API key | Each button only appears when its API key is configured. This makes the enrichment pipeline discoverable without cluttering UI when services aren't available. |
| Tool-specific Gemini QA prompts | Gemini already has per-tool prompts, but they're generic. Specialized prompts: Extract = name/entity cleanup, Revenue = figure verification, Proration = legal description validation | LOW | Existing gemini_service.py TOOL_PROMPTS | TOOL_PROMPTS already exist with per-tool instructions. Enhancement is refining prompts and adding new ones (e.g., address cleaning prompt separate from entity validation). |
| Multi-step enrichment progress modal | EnrichmentProgress component already built with step indicators; wire it to actual enrichment steps | LOW | Existing EnrichmentProgress.tsx component | Component exists but is only partially wired. Needs state management to track which steps completed and merge results. |
| RRC multi-lease parsing | Handle rows with combined lease numbers like "02-12345/02-12346" or "12345, 12346" | LOW | Existing fetch_missing_rrc_data endpoint | Parse slash-separated or comma-separated lease numbers, query each independently, combine acres/well-type from best match. |

## Anti-Features

Features that seem needed but should NOT be built.

| Anti-Feature | Why Requested | Why Avoid | What to Do Instead |
|--------------|---------------|-----------|-------------------|
| Direct SmartList creation via GHL API | Users see "SmartList Name" field in send modal | GHL SmartLists are dynamic filter views, not static membership lists. There is no API endpoint to "add a contact to a SmartList." SmartLists are defined by filter rules (e.g., "tag contains X"). Creating a SmartList via API would require knowing the exact filter schema, and contacts are included automatically by matching filters. | Apply the campaign tag reliably during upsert. The SmartList name field should be renamed or clarified: it IS the campaign tag. Users create the matching SmartList in GHL with filter "tag = [campaign tag]". Add help text explaining this. The field already maps `smart_list_name` to `campaign_tag` in the backend. |
| Auto-apply all AI suggestions without review | Users want one-click cleanup | AI suggestions have varying confidence. Auto-applying low-confidence changes corrupts data. The existing AiReviewPanel with accept/reject per suggestion is the correct UX. | Keep the review panel. Add "Accept All High Confidence" as a convenience button (only auto-accepts high confidence suggestions). |
| Real-time streaming enrichment via SSE | Each enrichment step could stream progress | Overengineered for batch sizes of 50-500 entries. Address validation runs at 40 QPS (done in seconds). Gemini batches of 25 with 6s delays are the bottleneck but total time is under 2 minutes. | Use polling or simple loading states. The EnrichmentProgress modal already handles step-by-step display. Endpoint returns when complete; frontend shows progress locally. |
| Automatic enrichment on upload | Skip the manual button clicks | Users need to see raw extracted data before corrections. Auto-enrichment masks extraction errors and burns API credits on bad data. | Keep enrichment as explicit opt-in steps. Post-upload preview shows raw data. User chooses which enrichment steps to run. |
| Combined single "Enrich All" button | One button to run all three steps | Different steps have different API key requirements. Running all three serially could take 2+ minutes. Users may only want address validation, not full enrichment. | Three separate buttons with individual loading states. Allow running in any order. Each updates preview independently. |

## Feature Dependencies

```
[API Key Configuration] (existing in Admin Settings)
    |
    +---> [Validate Button visibility] (needs GOOGLE_MAPS_API_KEY)
    +---> [Clean Up Button visibility] (needs GEMINI_API_KEY + GEMINI_ENABLED)
    +---> [Enrich Button visibility] (needs PDL_API_KEY or SEARCHBUG_API_KEY + ENRICHMENT_ENABLED)

[Upload + Parse] (existing per tool)
    |
    +---> [Preview Table with entries state] (existing)
              |
              +---> [Validate Button] --> calls address_validation_service.validate_addresses_batch()
              |         |
              |         +---> [Merge validated addresses into entries state]
              |         +---> [Show AutoCorrectionsBanner with undo]
              |
              +---> [Clean Up Button] --> calls gemini_service.validate_entries()
              |         |
              |         +---> [Show AiReviewPanel with accept/reject]
              |         +---> [On apply: merge accepted suggestions into entries state]
              |
              +---> [Enrich Button] --> calls enrichment_service.enrich_persons()
                        |
                        +---> [Show EnrichmentPanel with results]
                        +---> [Merge phone/email data into entries state]

[ECF Upload Flow]
    [PDF Upload] --> [Format Detection] --> [ECF detected?]
        YES --> [Show CSV upload area] --> [Both files ready?]
            YES --> [Enable "Process" button]
            NO --> [Process button disabled, "Add CSV" prompt]
        NO --> [Auto-process as before]

[GHL Smart List]
    [Bulk Send Request] --> [Apply campaign_tag to all contacts]
        |
        +---> [campaign_tag IS the smart list filter key]
        +---> [Rename field label from "SmartList Name" to "Campaign Tag"]
        +---> [Add help text: "Create matching SmartList in GHL using this tag as filter"]

[RRC Fetch Missing]
    [Parse lease numbers] --> [Split multi-lease strings]
        |
        +---> [Query each lease independently]
        +---> [Combine results: use first match with valid acres]
        +---> [Update preview table with matched data]
```

## Feature Details

### 1. GHL Smart List Resolution

**Current state:** `smart_list_name` field in BulkSendRequest is stored for reference in job metadata but has no functional effect. The `campaign_tag` is already applied as a GHL tag during upsert. The backend code at `ghl.py:343` already does `campaign_name = data.smart_list_name or data.campaign_tag`, treating them interchangeably.

**What to do:**
- SmartLists in GHL work via saved search filters (e.g., "tag contains 'Spring 2026 Campaign'")
- The app already applies the campaign tag during upsert, which is the correct mechanism
- Fix: Clarify the UI -- the "SmartList Name" field IS the campaign tag. Either:
  - Option A: Remove the separate SmartList field, keep campaign_tag (simpler)
  - Option B: Keep the field but add explicit help text explaining tag-based filtering
- Add inline help text: "Contacts will be tagged with this value. Create a matching SmartList in GHL by filtering contacts with this tag."
- The `smart_list_name` field in BulkSendRequest can stay as an alias for `campaign_tag` or be removed
- **Confidence:** HIGH (based on prior research in FEATURES-GHL-API.md and PITFALLS-GHL-API.md which already documented this: "SmartLists are filter-based, not manual membership lists")

### 2. Three Conditional Enrichment Buttons

**Current state:** Extract page has a "Validate Data" button that triggers AI review. EnrichmentPanel and AiReviewPanel components exist. Address validation service exists. But:
- Buttons are inconsistent across tools
- Preview doesn't update after enrichment
- No visibility gating based on API key availability

**What to build:**
- Unified button bar below preview table on all tool pages (Extract, Title, Proration, Revenue)
- Three buttons, each conditionally visible:
  - **Validate** (MapPin icon, green): Visible when `GOOGLE_MAPS_API_KEY` configured. Calls `validate_addresses_batch()`. Auto-applies address corrections, shows AutoCorrectionsBanner.
  - **Clean Up** (Sparkles/Wand2 icon, purple): Visible when `GEMINI_ENABLED=true`. Calls `validate_entries()`. Shows AiReviewPanel for accept/reject.
  - **Enrich** (Search icon, teal): Visible when enrichment enabled. Calls `enrich_persons()`. Shows EnrichmentPanel as slide-over.
- Check API status on page load: `GET /api/ai/status`, `GET /api/enrichment/status`
- Need new endpoint: `GET /api/address-validation/status` returning `{ enabled: boolean }` based on `google_maps_api_key` being set
- Consider extracting a shared `EnrichmentButtonBar` component used by all tool pages

**Complexity:** MEDIUM -- components exist, main work is: (a) status-checking endpoint for address validation, (b) uniform button bar component, (c) preview state merge after each step.

### 3. Preview Update After Enrichment

**Current state:** This is the core bug across all enrichment features. The enrichment endpoints return data, but the frontend doesn't merge results back into the `entries` state that drives the preview table.

**Pattern to follow:**
1. **Address validation:** `validate_addresses_batch()` returns updated entries with corrected fields. Endpoint needed: `POST /api/address-validation/batch` accepting entries, returning entries with corrections applied. Frontend: `setEntries(updatedEntries)` and show AutoCorrectionsBanner with undo (store pre-correction snapshot).
2. **AI cleanup:** `validate_entries()` returns suggestions. AiReviewPanel already has `onApplySuggestions` callback. Frontend should apply accepted suggestions to entries state. Extract.tsx partially implements this but the merge may not propagate correctly.
3. **Enrichment:** `enrich_persons()` returns phone/email data per person. Frontend should merge enriched fields into matching entries and update preview.

**Implementation pattern:**
```
Before enrichment: snapshot = [...entries]  // deep copy for undo
Call enrichment API with entries
On success: setEntries(mergedResults)
Show undo button: onClick={() => setEntries(snapshot)
Show banner summarizing changes
```

**Key insight:** Each enrichment step must be idempotent -- running Validate twice on already-validated addresses should produce no changes (the addresses already match Google's canonical form).

### 4. Tool-Specific Gemini QA Prompts

**Current state:** TOOL_PROMPTS in gemini_service.py already has per-tool system prompts for extract, title, proration, and revenue. These are good but could be more targeted.

**Enhancements needed:**
- **Extract:** Emphasize "Convert ALL CAPS names to Title Case" as highest priority correction (this is the most common issue with OCC/ECF data). Already partially in prompt.
- **Revenue:** Surface math verification more prominently: `owner_value approx= owner_volume * avg_price`. REVENUE_VERIFY_PROMPT exists but isn't connected to the general "Clean Up" button flow.
- **Proration:** Add Texas county name spelling validation and legal description format checking.
- **Title:** Strengthen duplicate detection emphasis -- similar names with different formatting.

**Complexity:** LOW -- prompt text changes only, no structural code changes.

### 5. ECF Upload Flow Fix

**Current state:** When user uploads an ECF PDF, format detection runs and processing starts automatically. User cannot add the optional Convey 640 CSV before processing begins.

**What to fix:**
- When format is detected as "ecf", DON'T auto-process
- Show the dual-file upload area with PDF already loaded
- Show "Add CSV (optional)" area alongside
- Show explicit "Process" button that triggers the actual upload/parse API call
- Standard OCC Exhibit A format continues to auto-process as before (no behavioral change)

**Complexity:** LOW -- frontend-only change in Extract.tsx. Gate the processing trigger behind format detection check.

### 6. RRC Fetch-Missing Repair

**Current state:** The endpoint at `POST /api/proration/rrc/fetch-missing` works mechanically but has two issues:
1. **Multi-lease parsing:** Rows with combined lease numbers like "02-12345/02-12346" aren't parsed -- the regex `re.findall(r"\d+", ...)` grabs all digits but doesn't understand slash-separated or comma-separated lease pairs
2. **Frontend integration:** Results aren't surfaced to the user -- matched data updates the `row` objects in the response but the Proration page frontend doesn't merge `updated_rows` back into the preview state

**Multi-lease parsing strategy:**
```python
# Parse "02-12345/02-12346" or "02-12345, 02-12346"
parts = re.split(r"[/,]", rrc_lease_string)
for part in parts:
    part = part.strip()
    if "-" in part:
        district, lease = part.split("-", 1)
    # Query each lease independently
    # Use first match with valid acres
```

**Frontend integration:**
- After fetch-missing returns, replace the Proration preview `rows` state with `updated_rows`
- Show a summary banner: "Matched 5 of 12 rows with RRC data. 7 still missing."
- Highlight newly-matched rows in the preview table (green background or icon)
- For still-missing rows, the `notes` field already contains a link to RRC search: `"Not found in RRC|{url}"` -- surface this as a clickable link in the table

**Complexity:** MEDIUM -- backend parsing fix is LOW, but frontend integration and state management adds complexity.

## MVP Recommendation

**Priority order based on user impact and dependencies:**

1. **ECF upload flow fix** -- LOW complexity, removes the most confusing UX bug. Users are actively confused by auto-processing.
2. **Preview update after enrichment** -- MEDIUM complexity, but this unlocks ALL three enrichment buttons. Without preview updates, enrichment buttons are useless regardless of whether they work.
3. **GHL smart list clarification** -- LOW complexity, rename field + add help text. Removes confusion about what the field does.
4. **Three conditional enrichment buttons** -- MEDIUM complexity, requires status endpoints + uniform button bar. Build after preview updates work.
5. **RRC fetch-missing repair** -- MEDIUM complexity, backend + frontend. Unblocks proration users stuck on missing RRC data.
6. **Tool-specific Gemini prompts** -- LOW complexity, iterate on prompt text. Can be refined anytime.

**Defer:**
- Enrichment result caching (don't re-enrich already-enriched entries) -- add after core flow works
- Enrichment history/audit trail -- nice but not blocking
- SmartList API creation -- not how GHL SmartLists work; tag-based filtering is the answer

## Complexity Estimates

| Feature | Backend | Frontend | Total | Risk |
|---------|---------|----------|-------|------|
| GHL smart list clarification | LOW (remove/rename field) | LOW (label change + help text) | LOW | LOW |
| Conditional enrichment buttons | LOW (1 new status endpoint) | MEDIUM (button bar component, visibility logic, per-page integration) | MEDIUM | LOW |
| Preview update after enrichment | LOW (endpoints already return data) | MEDIUM (state merge, undo snapshots, re-render per tool) | MEDIUM | MEDIUM -- entries state shape varies per tool |
| Tool-specific Gemini prompts | LOW (prompt text only) | NONE | LOW | LOW |
| ECF upload flow fix | NONE | LOW (gate auto-process behind format check) | LOW | LOW |
| RRC fetch-missing repair | LOW (multi-lease parsing regex) | MEDIUM (state merge, summary banner, row highlighting) | MEDIUM | MEDIUM -- RRC scraping is inherently fragile |

## Sources

- Prior GHL API research: `.planning/research/FEATURES-GHL-API.md` (2026-02-26)
- Prior GHL pitfalls research: `.planning/research/PITFALLS-GHL-API.md` (2026-02-26)
- GoHighLevel SmartLists: filter-based, not manual membership (confirmed in PITFALLS-GHL-API.md Pitfall 10)
- Existing codebase analysis: `gemini_service.py`, `address_validation_service.py`, `enrichment.py`, `bulk_send_service.py`, `client.py`
- Frontend component analysis: `AiReviewPanel.tsx`, `EnrichmentPanel.tsx`, `EnrichmentProgress.tsx`, `AutoCorrectionsBanner.tsx`
- RRC fetch-missing endpoint: `backend/app/api/proration.py` lines 333-478
- GHL models: `backend/app/models/ghl.py` -- BulkSendRequest.smart_list_name is Optional, maps to campaign_name in job persistence

---
*Feature research for: v1.5 Enrichment Pipeline & Bug Fixes*
*Researched: 2026-03-13*
*Context: Subsequent milestone fixing broken enrichment flows and adding universal enrichment buttons*
