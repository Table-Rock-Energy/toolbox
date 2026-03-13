# Domain Pitfalls: v1.5 Enrichment Pipeline & Bug Fixes

**Domain:** Multi-step enrichment, GHL API integration repair, RRC scraping, Gemini QA, frontend async state management
**Researched:** 2026-03-13
**Overall confidence:** HIGH (based on codebase analysis of existing bugs and known failure modes)

---

## Critical Pitfalls

Mistakes that cause data loss, broken UX, or require significant rework.

### Pitfall 1: Preview State Goes Stale After Async Enrichment Steps

**What goes wrong:** The Gemini validation completes in the background (`asyncio.to_thread` in `gemini_service.py`) and returns suggestions, but the frontend preview table does not re-render with updated data. The `AiReviewPanel` fires `onApplySuggestions` with accepted changes, but the parent component's entries state is a snapshot from upload time. If the user ran enrichment first, then AI validation, the AI suggestions reference stale `entry_index` values that no longer match the current entries array (entries may have been reordered, filtered, or modified by enrichment).

**Why it happens:** Each post-processing step (Validate, Clean Up, Enrich) operates on the entries array independently. There is no shared pipeline state or version tracking. The `AiReviewPanel` receives `entries` as a prop but the `onApplySuggestions` callback applies changes by `entry_index` -- if entries were modified between when the AI request was sent and when suggestions are applied, indices are wrong.

**Consequences:**
- Suggestions applied to wrong rows (silent data corruption)
- Preview shows pre-enrichment data even after enrichment completes
- User exports data thinking enrichment was applied, but export uses stale state

**Prevention:**
- Maintain a single `entriesRef` (useRef) that is the source of truth, updated after each step
- Stamp each AI validation request with a version counter; reject suggestions if version has changed
- After each enrichment step completes, explicitly call `setEntries(updatedEntries)` and ensure the preview table re-renders
- Add a visual indicator (badge, timestamp) showing when data was last modified

**Detection:** User runs Validate, then Enrich, then exports -- compare export output with what the preview showed. If they differ, this bug is present.

**Phase to address:** Must be fixed in the universal 3-button UI phase, before any enrichment steps are wired up.

---

### Pitfall 2: GHL Smart List Creation Is Not an API Feature

**What goes wrong:** The `BulkSendRequest` model has a `smart_list_name` field, and the frontend `GhlSendModal` sends it, but the backend only uses it as a label for the Firestore job document (`campaign_name = data.smart_list_name or data.campaign_tag`). No GHL API call actually creates a smart list. The GHL API v2 does not have a public endpoint for programmatic smart list creation -- smart lists are filter-based saved views in the GHL UI, not API-creatable objects.

**Why it happens:** Confusion between GHL "tags" (which are API-creatable and applied to contacts) and "smart lists" (which are UI-only saved filters). The original design assumed smart lists could be created via API.

**Consequences:**
- User expects contacts to appear in a named smart list in GHL, but they only get tagged
- Manual step required in GHL UI to create a smart list filtering by the campaign tag
- Feature appears broken from user's perspective

**Prevention:**
- Rename `smart_list_name` to `campaign_name` throughout the codebase to avoid confusion
- Document that the workflow is: tag contacts via API, then manually create smart list in GHL UI filtering by that tag
- Alternatively, use GHL's "Add to Campaign" API if the campaign already exists (requires campaign ID, not name)
- Update UI copy: change "Smart List Name" label to "Campaign Tag" with helper text explaining the tag will be applied to all contacts

**Detection:** User sends contacts with a smart list name, then searches for that smart list in GHL -- it does not exist.

**Phase to address:** Fix in GHL bulk send repair phase. Rename the field and update UI copy to set correct expectations.

**Confidence:** MEDIUM -- based on GHL API v2 documentation from training data. The API version in use (`2021-07-28`) is old; newer versions may have added smart list endpoints. Verify against current GHL API docs before implementing.

---

### Pitfall 3: Enrichment Service Processes Persons Sequentially Without Timeout or Progress

**What goes wrong:** `enrich_persons()` in `enrichment_service.py` loops through up to 50 persons sequentially, making 1-2 HTTP calls per person (PDL + SearchBug). With network latency, 50 persons at ~2 seconds each = 100+ seconds. The user sees a spinner for minutes with no progress feedback.

**Why it happens:** The enrichment service was designed for small batches but is now being promoted as a universal feature across all tools. The sequential loop with no progress reporting makes it appear hung.

**Consequences:**
- User thinks the feature is broken and refreshes, losing the request
- Cloud Run cold-start + enrichment = potential timeout on 1Gi instances
- No partial results if one provider fails mid-batch
- Existing `EnrichmentPanel` (`enrichment_panel.tsx`) shows loading state but no per-person progress

**Prevention:**
- Add SSE-based progress streaming for enrichment (similar to GHL bulk send pattern already in codebase)
- Process persons in parallel with `asyncio.gather()` with a concurrency limiter (`asyncio.Semaphore(5)`)
- Return partial results immediately as each person completes
- Cap batch size at 25 for the universal button and process remaining on demand
- Add a request-level timeout (30 seconds) with graceful partial return

**Detection:** Click Enrich on 30+ entries, observe response time exceeds 30 seconds with no progress indication.

**Phase to address:** Address when building the universal Enrich button. Must have progress feedback before deploying.

---

### Pitfall 4: Concurrent Enrichment Button Clicks Cause Race Condition

**What goes wrong:** If the user clicks "Validate" and then immediately clicks "Enrich" before validation completes, both operations run concurrently against the same entries array. Both will try to modify entries state when they complete, and the last one to call `setEntries()` wins, silently discarding the other's results.

**Why it happens:** The universal 3-button UI has no operation mutex. Each button triggers an independent async operation. React state updates from both operations race.

**Consequences:**
- AI validation suggestions silently lost if enrichment completes after
- Enriched data silently lost if validation completes after
- Export may contain partially-processed data with no indication

**Prevention:**
- Disable all three buttons while any operation is in progress (simple and effective)
- Show a progress indicator on the active operation
- Queue operations: if Validate is running and user clicks Enrich, show "Validate must complete first"
- Use a `processingRef` to track which operation is active and prevent concurrent execution
- Each operation should take the current entries as input and return modified entries (functional pipeline, not shared mutable state)

**Detection:** Click two buttons in rapid succession, then check if both operations' results are reflected in the preview.

**Phase to address:** Must be solved in the universal 3-button UI design. This is an architecture decision, not a bug fix.

---

## Moderate Pitfalls

Issues that degrade UX or cause incorrect behavior but do not corrupt data.

### Pitfall 5: Gemini Rate Limits Silently Truncate Validation Results

**What goes wrong:** `validate_entries()` in `gemini_service.py` processes entries in batches of 25 with a 6-second delay between batches. If rate limits are hit (`MAX_RPM=10`, `MAX_RPD=250`), the function returns a partial result with `success=True` and a summary like "Partially reviewed (3/8 batches)". The frontend `AiReviewPanel` shows suggestions only for the reviewed entries and provides no way to resume or retry the remaining entries.

**Why it happens:** The rate limit check happens before each batch, and when it fails, the function returns immediately with whatever suggestions it has. The `success=True` flag makes it look like everything worked.

**Consequences:**
- User applies AI suggestions thinking all entries were reviewed, but only the first N batches were checked
- For a 200-entry upload (8 batches), hitting RPM limits after batch 3 means 125 entries are never validated
- No retry mechanism for the un-reviewed entries

**Prevention:**
- Change the response to include a distinct `partial: true` flag when not all entries were reviewed
- Show a clear warning banner in `AiReviewPanel`: "Only X of Y entries were reviewed due to rate limits"
- Add a "Resume Validation" button that picks up where it left off (pass `start_index` to the API)
- The `AiValidationResult` model already has `entries_reviewed` and the summary text, but the frontend does not differentiate partial from full results

**Detection:** Upload 200+ entries, click Validate -- check if `entries_reviewed < total entries` in the response.

**Phase to address:** Fix in the Gemini QA prompts phase. The partial result UX must be clear before making validation universal.

---

### Pitfall 6: RRC HTML Parsing Breaks on Website Layout Changes

**What goes wrong:** `_parse_rrc_html()` in `rrc_county_download_service.py` uses regex to parse HTML table rows. It relies on specific `<td>` ordering (lease_name at index 1, operator_name at index 7, acres at index 11, well_type at index 13). If the RRC website adds, removes, or reorders columns, all parsed data will be wrong -- fields will be shifted and the parser will silently return incorrect data.

**Why it happens:** HTML scraping is inherently fragile. The parser uses positional indexing instead of header-based column detection. There are no header validation checks.

**Prevention:**
- Add header row validation: parse the `<th>` elements first and build a column-name-to-index map
- Fall back to CSV download (the existing path) when HTML parsing fails or columns do not match expected headers
- Add a smoke test that validates parsing against a known HTML fixture saved in test-data
- Log a warning when the number of `<td>` elements per row does not match expectations (currently requires 12+)

**Detection:** RRC data shows wrong operator names, wrong acreage, or zero results where data should exist. Check `/tmp/rrc_individual_*.html` debug files for layout changes.

**Phase to address:** RRC fetch-missing repair phase. Add header validation before deploying multi-lease lookups.

---

### Pitfall 7: RRC Session State Leaks Between Individual Lease Queries

**What goes wrong:** `fetch_individual_leases()` reuses a single `requests.Session` across multiple lease lookups. The RRC website uses server-side session state. If a search returns results, the server may cache that result set -- the next search might return the previous search's data, or the server-side session may expire.

**Why it happens:** The RRC website is a stateful Java web application (JSP/Struts pattern based on the URL structure `oilProQueryAction.do`). Each search creates server-side state. Reusing a session means the server-side state from query N can interfere with query N+1.

**Prevention:**
- Create a fresh session for each individual lease lookup, not just on failure (the code already does this on exception, but should be proactive)
- Or: perform search + data extraction as a single atomic sequence per lease before starting the next
- Add validation: verify that returned lease_number matches the requested lease_number
- The `_human_delay()` between queries helps but does not prevent session state issues

**Detection:** Two consecutive lease lookups return identical data despite different district/lease numbers.

**Phase to address:** RRC fetch-missing repair phase.

---

### Pitfall 8: ECF Upload Auto-Processing Skips User Confirmation

**What goes wrong:** The v1.4 ECF upload flow auto-detects the format on file selection and may start processing without explicit user confirmation. This breaks the mental model of "upload, then process" that exists for standard OCC files. Users may accidentally upload the wrong file.

**Why it happens:** The ECF format detection runs in the upload handler, and the existing Extract page conflates file selection with processing for the new ECF path.

**Prevention:**
- Separate file selection from processing for all formats: select file(s), show format detection result, require explicit "Process" button click
- After format detection, show a confirmation card: "Detected: ECF Multiunit Filing. County: [X]. Click Process to extract respondents."
- If auto-detection fails or returns "unknown", show a format selector dropdown
- Ensure the Process button is disabled until format detection completes

**Detection:** User selects an ECF PDF and processing starts immediately with no confirmation step.

**Phase to address:** ECF upload flow fix phase. Must be explicit about the upload-detect-confirm-process flow.

---

### Pitfall 9: Address Validation Results Not Surfacing in Preview

**What goes wrong:** This is a known existing bug. The address validation service runs but the results (standardized addresses) are not propagated back to the entries state in the frontend. The backend returns address corrections, but there is no handler in the frontend to apply them to the entries array.

**Why it happens:** The AI validation flow was designed for suggestions (show to user, let them accept/reject), but address validation returns authoritative corrections that should be auto-applied or at minimum shown as high-confidence suggestions. The two flows were built independently and never integrated.

**Prevention:**
- Define clear result types: "suggestions" (require user approval) vs "corrections" (auto-apply with undo)
- Address validation results should update entries directly, with a banner showing "X addresses standardized (Undo)"
- Or: wire address corrections through the existing `onApplySuggestions` callback with auto-accept for high-confidence results
- Add address validation as a distinct step in the enrichment pipeline ("Clean Up" button), not overloaded onto AI validation

**Detection:** Run address validation, observe that preview entries still show original addresses.

**Phase to address:** Universal Validate/Clean Up/Enrich button phase. Must define the result-type taxonomy before building the UI.

---

### Pitfall 10: Module-Level State in Gemini Service Breaks Under Cloud Run Scaling

**What goes wrong:** `gemini_service.py` uses module-level globals for rate limiting (`_rpm_timestamps`, `_daily_count`, `_monthly_spend`). Cloud Run can run 0-10 instances. Each instance has its own copy of these globals. This means:
- Rate limits are per-instance, not global (actual API usage could be 10x the per-instance limit)
- Monthly spend tracking resets when instances scale to zero and back up
- Daily count resets on each new instance

**Why it happens:** Module-level state was the simplest implementation. For a small team with low concurrent usage, this mostly works.

**Prevention:**
- For the current small team (max-instances=10), this is acceptable risk. Document it.
- If rate limit errors increase: move rate limit state to Firestore with atomic increment operations
- Monthly spend tracking should persist to Firestore on each API call (write-through cache)
- Alternatively, rely on Gemini's built-in rate limiting (let the API return 429) and handle retries -- the service already has retry logic

**Detection:** Check Cloud Run metrics for concurrent instances > 1 when Gemini 429 errors spike.

**Phase to address:** Acceptable for v1.5 launch. Flag for monitoring. If 429 errors appear in production logs, migrate to Firestore-based tracking.

---

### Pitfall 11: GHL Firestore Write Per Contact Creates Document Hot Spot

**What goes wrong:** `process_batch_async()` in `bulk_send_service.py` writes to the same Firestore document after every single contact (`doc_ref.update({...})`). For a 500-contact batch at ~5 writes/second, this exceeds Firestore's recommended sustained write rate of 1 write/second per document.

**Why it happens:** The per-contact Firestore update was designed for real-time SSE progress polling (300ms interval).

**Prevention:**
- Batch Firestore updates: write progress every 10 contacts instead of every 1
- Use in-memory state for SSE progress (module-level dict or asyncio queue) and only write to Firestore at milestones (every 10th contact, on error, at completion)
- For the current batch sizes (typically <200 contacts), this may not hit the limit in practice. Monitor for Firestore 429/contention errors.
- Alternatively, switch from Firestore polling to in-process event streaming for SSE

**Detection:** Firestore error logs showing "Too much contention on document" during bulk sends of 200+ contacts.

**Phase to address:** Low priority for v1.5. Monitor and address if Firestore contention errors appear.

---

## Minor Pitfalls

### Pitfall 12: Enrichment Service Name Splitting Is Naive

**What goes wrong:** `_split_name()` in `enrichment_service.py` splits on whitespace: `parts[0]` = first name, `" ".join(parts[1:])` = last name. This fails for compound surnames ("Van Der Berg"), comma-separated names ("SMITH, JOHN"), and middle names ("Mary Jane Smith").

**Prevention:** When building the universal Enrich button, pass parsed first/last names from the tool entries (which already have name parsing done by the Extract/Title services) instead of relying on `_split_name()`. Accept optional `first_name` and `last_name` fields in the enrichment API.

**Phase to address:** Enrichment pipeline phase.

---

### Pitfall 13: GHL SSE Query-Param Auth Token in URLs

**What goes wrong:** The SSE progress endpoint uses `?token=<firebase_id_token>` in the URL because EventSource API does not support custom headers. This token appears in server access logs and browser history.

**Prevention:** Accepted risk for internal tool. Firebase ID tokens expire after 1 hour. Ensure SSE endpoint URLs are not logged at INFO level with the full token. If this becomes a concern, switch to WebSocket-based progress.

**Phase to address:** Not a v1.5 concern. Document as accepted risk.

---

### Pitfall 14: Enrichment Provider API Key Rotation Has No Validation

**What goes wrong:** The enrichment service accepts runtime API key overrides via `set_runtime_config()` from admin UI. If an invalid key is set, every enrichment request fails silently (caught exception in `enrich_person()`) with no results.

**Prevention:** Add a validation step when API keys are updated: make a test API call to each provider. Show validation status in admin UI.

**Phase to address:** When building the universal Enrich button, add key validation on save.

---

### Pitfall 15: RRC `verify=False` SSL Warning Log Noise

**What goes wrong:** Every RRC request generates Python `urllib3` InsecureRequestWarning, filling logs during bulk operations.

**Prevention:** Ensure `urllib3.disable_warnings()` is called in the RRC service module. Quick cosmetic fix.

**Phase to address:** Quick fix during RRC repair phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Universal 3-button UI | Race condition between concurrent operations (#4) | CRITICAL | Disable buttons during active operation, enforce serial pipeline |
| Universal 3-button UI | Preview state goes stale after enrichment (#1) | CRITICAL | Single source of truth with version counter, explicit state updates |
| Universal 3-button UI | Address validation not surfacing (#9) | MODERATE | Define suggestion vs correction result types before building UI |
| GHL smart list fix | Smart lists not API-creatable (#2) | MODERATE | Rename to campaign_name, update UI copy, tag-based workflow |
| GHL bulk send | Firestore write hot spot (#11) | LOW | Batch writes every 10 contacts, monitor contention |
| Gemini QA prompts | Partial validation looks like success (#5) | MODERATE | Add `partial` flag, show warning banner, enable resume |
| Gemini QA prompts | Module-level rate limit state (#10) | LOW | Acceptable for now, monitor 429 errors |
| RRC fetch-missing | HTML parsing fragility (#6) | MODERATE | Add header validation, fallback to CSV path |
| RRC fetch-missing | Session state leakage (#7) | MODERATE | Fresh session per lease or atomic search+download |
| ECF upload UX | Auto-processing without confirmation (#8) | MODERATE | Upload-detect-confirm-process flow |
| Enrichment pipeline | Sequential processing without progress (#3) | CRITICAL | Parallel execution with SSE progress or at minimum per-person updates |
| Enrichment pipeline | Naive name splitting (#12) | LOW | Pass parsed names from tool entries |

## Architecture Recommendation

The most dangerous pattern in v1.5 is **independent async operations modifying shared mutable state without coordination**. The universal 3-button UI must enforce a serial pipeline model:

```
Upload -> entries_v0
  |-> Validate -> suggestions -> user accepts -> entries_v1
  |-> Clean Up -> corrections -> auto-apply -> entries_v2
  |-> Enrich -> enriched data -> merge -> entries_v3
  |-> Export uses entries_v(latest)
```

Each step takes the current version as input and produces the next version. No concurrent steps. A version counter prevents stale suggestions from being applied. The `onApplySuggestions` callback should check: "is the current entries version the same as when I started? If not, reject these suggestions."

## Sources

- Codebase analysis: `gemini_service.py`, `enrichment_service.py`, `bulk_send_service.py`, `rrc_county_download_service.py`, `ghl/client.py`, `ghl.py`, `AiReviewPanel.tsx`, `EnrichmentPanel.tsx`, `useSSEProgress.ts`, `Extract.tsx`
- Known bugs documented in `.planning/PROJECT.md` v1.5 milestone context
- GHL API behavior from existing client implementation (API version `2021-07-28`)
- RRC website behavior from existing scraper implementation and debug trace patterns
- Firestore write rate limits from Google Cloud documentation (1 write/sec/document sustained)
- Confidence: HIGH for pitfalls derived from direct code analysis; MEDIUM for GHL smart list limitation (training data, web search unavailable for verification)

---
*Pitfalls research for: v1.5 Enrichment Pipeline & Bug Fixes*
*Researched: 2026-03-13*
