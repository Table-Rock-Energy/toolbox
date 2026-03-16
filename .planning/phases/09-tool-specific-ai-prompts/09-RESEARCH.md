# Phase 9: Tool-Specific AI Prompts - Research

**Researched:** 2026-03-16
**Domain:** LLM prompt engineering, cross-file data comparison, statistical outlier detection
**Confidence:** HIGH

## Summary

Phase 9 is primarily a prompt-authoring and pipeline-plumbing phase with minimal new library dependencies. The existing infrastructure (CLEANUP_PROMPTS dict, TOOL_PROMPTS dict, PipelineRequest model, LLMProvider protocol, ProposedChangesPanel) is well-structured for the required changes. The work breaks into four distinct areas: (1) adding ECF as a new tool key with cross-file comparison prompts, (2) adding suffix standardization to Extract/Title cleanup prompts, (3) adding statistical outlier detection to Revenue cleanup prompts, and (4) adding confidence badges to ProposedChangesPanel.

The main technical decisions are: how to pass original CSV data through the pipeline for ECF cross-file comparison (requires extending PipelineRequest with an optional `source_data` field), whether to compute median in Python vs letting the LLM estimate from batch (Python pre-computation is more reliable), and how the LLMProvider protocol signature needs to change to accept source_data.

**Primary recommendation:** Extend the pipeline plumbing first (PipelineRequest.source_data, LLMProvider protocol, GeminiProvider), then add prompts, then add frontend confidence badges. Keep prompt changes surgical -- ECF is net-new, others are minor refinements.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ECF cross-file comparison: Compare ALL overlapping fields between PDF-extracted and CSV-provided data (names, addresses, entity types, entry numbers, metadata like county/legal description/case number)
- Present discrepancies as ProposedChange: CSV value as current, PDF value as suggested, with reason explaining the mismatch -- follows "PDF is authoritative" principle from v1.4
- Cross-file checking runs as part of Clean Up (no separate button) -- when user clicks Clean Up on ECF data, the prompt does both standard name/address cleanup AND cross-file comparison in one pass
- AI receives both the merged result AND the original CSV data so it can see where merge chose PDF over CSV
- Both CLEANUP_PROMPTS and TOOL_PROMPTS get ECF-specific versions
- Keep existing Extract/Title/Revenue/Proration prompts largely intact -- add targeted refinements only
- Add suffix standardization to Extract and Title cleanup prompts: normalize Jr./Junior -> Jr, Sr./Senior -> Sr, III stays III, The Third -> III
- Add statistical outlier detection to Revenue prompts: flag values >3x median compared against the batch
- ECF prompt is the only net-new prompt
- Add 'ecf' as a new valid tool key alongside extract/title/proration/revenue
- Frontend sends tool='ecf' when the upload was ECF format
- Add optional 'source_data' field to PipelineRequest for passing original CSV data alongside merged entries
- ECF gets both a CLEANUP_PROMPTS['ecf'] entry and a TOOL_PROMPTS['ecf'] entry
- Show all proposed changes, sort by confidence (high first) -- no filtering
- ECF cross-file discrepancies always marked as high confidence
- Add confidence badge to ProposedChangesPanel: small colored badge (green=high, yellow=medium, gray=low) next to each proposed change

### Claude's Discretion
- Exact wording of ECF cross-file prompt instructions
- How to structure the statistical outlier detection in the Revenue prompt (whether to compute median in Python and pass to LLM, or let LLM estimate from the batch)
- ECF validation prompt scope (how much overlap with standard Extract validation)
- Confidence badge styling and placement within ProposedChangesPanel

### Deferred Ideas (OUT OF SCOPE)
- Admin-editable prompt templates -- deferred to v1.6+
- Prompt A/B testing or quality scoring -- future consideration
- Tool-specific confidence thresholds (different filtering per tool) -- not needed now
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRICH-11 | Tool-specific AI QA prompts: name cleanup for Extract/Title, figure verification for Revenue, address cleaning for all, overall accuracy check across both source files for ECF | All four prompt areas mapped to specific code changes below: ECF cross-file prompt (net-new), suffix standardization (Extract/Title refinement), outlier detection (Revenue refinement), ECF validation prompt (net-new) |
</phase_requirements>

## Standard Stack

No new libraries needed. This phase modifies existing prompt strings and adds minor plumbing.

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | existing | Gemini LLM calls | Already used by gemini_provider.py |
| pydantic | 2.x | PipelineRequest model extension | Already used for all API models |
| React | 19.x | ProposedChangesPanel confidence badge | Already the frontend framework |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| statistics (stdlib) | n/a | Median computation for Revenue outlier detection | Pre-compute batch median in Python before sending to LLM |

**Installation:** None required. All dependencies already present.

## Architecture Patterns

### Recommended Change Structure
```
backend/
├── app/
│   ├── models/
│   │   └── pipeline.py              # Add source_data field to PipelineRequest
│   ├── services/
│   │   ├── llm/
│   │   │   ├── prompts.py           # Add CLEANUP_PROMPTS['ecf'], refine extract/title/revenue
│   │   │   ├── protocol.py          # Extend cleanup_entries signature with source_data
│   │   │   └── gemini_provider.py   # Accept + pass source_data for ECF cleanup
│   │   └── gemini_service.py        # Add TOOL_PROMPTS['ecf']
│   └── api/
│       └── pipeline.py              # Pass source_data through, add ECF field mappings, compute revenue medians
frontend/
├── src/
│   ├── components/
│   │   └── ProposedChangesPanel.tsx  # Add confidence badges, sort by confidence
│   ├── hooks/
│   │   └── useEnrichmentPipeline.ts  # Accept + pass source_data for ECF
│   ├── pages/
│   │   └── Extract.tsx              # Pass tool='ecf' + source_data when ECF format
│   └── utils/
│       └── api.ts                   # Add source_data to PipelineRequest type + pipelineApi calls
```

### Pattern 1: Extending PipelineRequest with source_data
**What:** Add an optional `source_data` field to PipelineRequest that carries the original CSV entries for ECF cross-file comparison. Other tools ignore it.
**When to use:** Only when tool='ecf' and CSV data was uploaded alongside PDF.
**Example:**
```python
# backend/app/models/pipeline.py
class PipelineRequest(BaseModel):
    tool: str = Field(description="Tool name: extract, title, proration, revenue, or ecf")
    entries: list[dict] = Field(description="List of entry dicts to process")
    field_mapping: dict[str, str] = Field(default_factory=dict)
    source_data: list[dict] | None = Field(
        default=None,
        description="Original source data for cross-file comparison (ECF: original CSV rows)",
    )
```

### Pattern 2: LLM Provider Protocol Extension
**What:** Add optional `source_data` parameter to `cleanup_entries` in the protocol and implementation.
**When to use:** Protocol change needed so ECF cross-file data reaches the LLM.
**Example:**
```python
# backend/app/services/llm/protocol.py
class LLMProvider(Protocol):
    async def cleanup_entries(
        self, tool: str, entries: list[dict],
        *, source_data: list[dict] | None = None,
    ) -> list[ProposedChange]: ...
```

### Pattern 3: Revenue Median Pre-Computation
**What:** Compute batch-level statistics (median owner_value, median owner_volume) in Python and inject into the prompt as context.
**Why:** LLMs are unreliable at mental math on large datasets. Pre-computing the median and passing it as prompt context gives the LLM a concrete threshold to compare against (>3x median = outlier).
**Example:**
```python
# In pipeline.py cleanup endpoint, before calling provider
if request.tool == "revenue":
    from statistics import median
    values = [float(e.get("owner_value", 0)) for e in request.entries if e.get("owner_value")]
    if values:
        med = median(values)
        # Inject as metadata the LLM can reference
        for e in request.entries:
            e["_batch_median_value"] = med
            e["_outlier_threshold"] = med * 3
```

### Pattern 4: ECF Cross-File Prompt Structure
**What:** The ECF cleanup prompt does double duty: standard name/address cleanup AND cross-file comparison in one pass. The prompt receives both merged entries (current state) and original CSV rows (source_data), and compares fields.
**Why:** User explicitly decided no separate button -- cross-file checking is part of Clean Up.
**Design:**
```
System prompt (CLEANUP_PROMPTS['ecf']):
  - Standard cleanup rules (casing, abbreviations, entity types)
  - Cross-file comparison rules (compare each entry against its CSV counterpart)
  - "PDF is authoritative" principle: suggest PDF value when CSV differs
  - Mark cross-file discrepancies as high confidence

User prompt:
  - Merged entries (the processed/merged result)
  - Original CSV data (source_data, keyed by entry_number for alignment)
```

### Pattern 5: Sorting ProposedChanges by Confidence
**What:** Sort proposed changes array so high-confidence items appear first.
**Where:** In ProposedChangesPanel.tsx, sort the groups or the flat list before rendering.
**Example:**
```typescript
const CONFIDENCE_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }
const sortedChanges = [...proposedChanges].sort(
  (a, b) => (CONFIDENCE_ORDER[a.confidence] ?? 3) - (CONFIDENCE_ORDER[b.confidence] ?? 3)
)
```

### Anti-Patterns to Avoid
- **Sending raw CSV file to LLM:** Do NOT send the CSV file content as text. Send structured JSON entries from the parsed CSV data that the frontend already has.
- **Letting LLM compute statistics:** Do NOT ask the LLM to "find the median of all owner_value fields." Pre-compute in Python and pass the result.
- **Separate cross-file endpoint:** The user explicitly decided against this. Cross-file comparison is part of the cleanup step.
- **Breaking existing prompt behavior:** The user wants to keep existing prompts "largely intact." Only add suffix normalization to Extract/Title and outlier detection to Revenue. Do not restructure the prompt logic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Median computation | Custom median function | `statistics.median` (stdlib) | Edge cases with even-length lists, zero values |
| Confidence sort | Custom sort comparator | Simple dict-based priority map | Cleaner, maintainable |

**Key insight:** This phase is almost entirely prompt text and data plumbing. There are no complex algorithms to hand-roll.

## Common Pitfalls

### Pitfall 1: Protocol Signature Breaking Change
**What goes wrong:** Adding `source_data` as a required parameter to `cleanup_entries` breaks all existing callers.
**Why it happens:** Protocol defines the interface used by both the provider and the pipeline endpoint.
**How to avoid:** Make `source_data` keyword-only with a default of `None`. The existing call site `provider.cleanup_entries(request.tool, request.entries)` continues to work unchanged.
**Warning signs:** TypeError at runtime when calling cleanup_entries without source_data.

### Pitfall 2: ECF Entry Alignment Between Merged and CSV
**What goes wrong:** The LLM can't match merged entries to their CSV counterparts because index numbers don't align after merge.
**Why it happens:** The merge process may reorder, add, or skip entries relative to the CSV.
**How to avoid:** Use `entry_number` as the alignment key in the prompt. Instruct the LLM to match by entry_number, not by array index. Include entry_number in both merged entries and source_data.
**Warning signs:** Cross-file comparison suggestions reference wrong rows.

### Pitfall 3: Revenue Outlier Detection on Empty/Zero Values
**What goes wrong:** Computing median fails or gives meaningless results when most values are 0 or empty.
**Why it happens:** Many revenue rows may have null/zero owner_value (especially for gas with volume-only reporting).
**How to avoid:** Filter out zero and empty values before computing median. If fewer than 3 non-zero values exist, skip outlier detection for that batch.
**Warning signs:** Every row flagged as outlier, or median of 0 making everything an outlier.

### Pitfall 4: Prompt Token Limits
**What goes wrong:** ECF cross-file prompt with both merged entries AND CSV source_data doubles the token count.
**Why it happens:** The existing batch size of 25 was calibrated for single-source data.
**How to avoid:** Consider reducing batch size for ECF tool (e.g., 15 instead of 25) since each entry carries ~2x the data. Or keep batch size at 25 but monitor token usage.
**Warning signs:** Gemini truncating input, incomplete suggestions, rate limit exhaustion.

### Pitfall 5: Frontend Type Mismatch for source_data
**What goes wrong:** TypeScript type for PipelineRequest doesn't include source_data, causing compile errors.
**Why it happens:** The frontend PipelineRequest interface in api.ts needs updating alongside the backend model.
**How to avoid:** Update the frontend PipelineRequest interface and pipelineApi methods to accept optional source_data parameter simultaneously with backend changes.
**Warning signs:** TypeScript compilation errors in useEnrichmentPipeline.ts or Extract.tsx.

### Pitfall 6: Confidence Badge Already Partially Exists
**What goes wrong:** Developer adds duplicate confidence display.
**Why it happens:** ProposedChangesPanel already shows confidence as a colored pill in the expanded detail view (CONFIDENCE_STYLES mapping at line 28-32). The request is to add a "badge" -- need to understand this means the compact badge visible in the group header row, not just in expanded detail.
**How to avoid:** Read the existing component carefully. The confidence pill already exists in expanded details. The new badge should appear in the group header row (the collapsed view) so users can see confidence at a glance without expanding.
**Warning signs:** Redundant confidence display in expanded view.

## Code Examples

### ECF Cleanup Prompt (recommended wording)
```python
CLEANUP_PROMPTS["ecf"] = """You are a data cleanup assistant for ECF (Exhibit C Filing / Convey 640) data from Oklahoma OCC filings.
You have TWO data sources for each entry:
1. MERGED ENTRIES: The processed result combining PDF extraction and CSV data (entries in the main list)
2. ORIGINAL CSV DATA: The raw data from the Convey 640 CSV upload (provided separately as source_data)

Your job has TWO parts:

PART 1 - Standard Cleanup (same as extract):
- Name casing: Convert ALL CAPS names to proper Title Case. Keep entity abbreviations uppercase (LLC, LP, INC, CO, LTD).
- Suffix standardization: Normalize suffixes (Jr./Junior -> Jr, Sr./Senior -> Sr, The Third/3rd -> III). Standard suffixes: Jr, Sr, I, II, III, IV.
- Name abbreviations: Expand common abbreviations (Jno -> John, Wm -> William, Chas -> Charles, Jas -> James, Robt -> Robert).
- Entity type inference: If name contains "Trust", "Estate", "LLC", etc. but entity_type doesn't match, suggest the correct entity_type.
- Address cleanup: Strip "c/o" prefixes from mailing_address, suggest moving them to notes.
- State abbreviation: Correct to valid 2-letter US state code.
- ZIP format: Normalize to XXXXX or XXXXX-XXXX.

PART 2 - Cross-File Comparison:
Compare each merged entry against its CSV counterpart (matched by entry_number).
For EVERY field that differs between merged and CSV data:
- If PDF-extracted value differs from CSV value, suggest the PDF value (PDF is authoritative).
- Report the CSV value as current_value and the PDF/merged value as suggested_value.
- Include reason explaining: "PDF extraction differs from CSV: [field] was '[csv_val]' in CSV but '[pdf_val]' in PDF"
- Mark ALL cross-file discrepancies as "high" confidence (these are objective factual mismatches).
- Compare: names, addresses, entity types, entry numbers, and any metadata fields present in both sources.

Return corrections as JSON with: entry_index, field, current_value, suggested_value, reason, confidence (high/medium/low).
If all entries look correct and CSV matches merged data, return {"suggestions": []}."""
```

### ECF Validation Prompt (recommended wording)
```python
TOOL_PROMPTS["ecf"] = """You are a data quality reviewer for ECF (Exhibit C Filing / Convey 640) data from Oklahoma OCC filings.
This data was merged from two sources: a PDF filing and a Convey 640 CSV spreadsheet.

Review each entry and suggest corrections for:
- Name casing: Convert ALL CAPS names to proper Title Case. Keep entity abbreviations uppercase (LLC, LP, INC, CO).
- Entity type vs name mismatch: If name contains "Trust", "Estate", "LLC", etc. but entity_type doesn't match, suggest correction.
- Address completeness: Flag entries missing city, state, or zip_code when mailing_address is present.
- State abbreviation: Ensure state is a valid 2-letter US state code.
- ZIP code format: Should be 5 digits or 5+4 format.
- Suffix format: Verify suffixes are standardized (Jr, Sr, I, II, III, IV -- not spelled out).
- Duplicate detection: Flag entries with very similar names that may be duplicates.

Only suggest changes where you are confident there is an actual error."""
```

### Suffix Standardization Addition (Extract/Title)
```python
# Add this line to CLEANUP_PROMPTS["extract"] and CLEANUP_PROMPTS["title"]:
"- Suffix standardization: Normalize suffixes to standard forms: Jr./Junior/junior -> Jr, Sr./Senior/senior -> Sr, The Third/3rd -> III, The Second/2nd -> II. Standard suffixes are: Jr, Sr, I, II, III, IV."
```

### Revenue Outlier Detection Addition
```python
# Add to CLEANUP_PROMPTS["revenue"]:
"- Statistical outlier detection: If _batch_median_value is provided, flag any owner_value that exceeds 3x the median (_outlier_threshold). These may indicate data extraction errors (misplaced decimal, concatenated values). Use \"medium\" confidence for outlier flags."
```

### Python Median Pre-Computation
```python
# In pipeline.py, inside pipeline_cleanup before calling provider:
if request.tool == "revenue":
    from statistics import median as compute_median
    values = [
        float(e["owner_value"])
        for e in request.entries
        if e.get("owner_value") and float(e.get("owner_value", 0)) > 0
    ]
    if len(values) >= 3:
        med = compute_median(values)
        threshold = med * 3
        for e in request.entries:
            e["_batch_median_value"] = round(med, 2)
            e["_outlier_threshold"] = round(threshold, 2)
```

### Frontend: Pass tool='ecf' and source_data
```typescript
// In Extract.tsx, when calling useEnrichmentPipeline:
const pipeline = useEnrichmentPipeline({
  tool: formatHint === 'ECF' ? 'ecf' : 'extract',
  previewEntries: preview.previewEntries,
  updateEntries: preview.updateEntries,
  editedFields: preview.editedFields,
  keyField: 'entry_number' as keyof PartyEntry,
  featureFlags,
  // Pass original CSV entries for ECF cross-file comparison
  sourceData: formatHint === 'ECF' ? originalCsvEntries : undefined,
})
```

### Confidence Badge in Group Header
```typescript
// In ProposedChangesPanel.tsx, add to the group header row:
const highestConfidence = changes.reduce((best, c) => {
  const order = { high: 0, medium: 1, low: 2 }
  return (order[c.confidence as keyof typeof order] ?? 3) < (order[best as keyof typeof order] ?? 3)
    ? c.confidence : best
}, changes[0].confidence)

// Render in group header:
<span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium ${CONFIDENCE_STYLES[highestConfidence] || ''}`}>
  {highestConfidence}
</span>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single prompt for all tools | Per-tool CLEANUP_PROMPTS dict | Phase 8 (2026-03-16) | Already implemented, just needs 'ecf' key |
| No cross-file comparison | Cross-file via source_data in prompt | This phase | ECF-specific, other tools unaffected |

**No deprecated patterns.** The existing prompt infrastructure is recent (Phase 8) and well-designed for this extension.

## Open Questions

1. **Original CSV entries access in frontend**
   - What we know: The CSV file is uploaded via FormData alongside the PDF in Extract.tsx. The backend parses it and returns merged entries.
   - What's unclear: The original parsed CSV entries may not be stored separately in frontend state after the upload response. The backend returns only the merged result.
   - Recommendation: Either (a) have the backend return the original CSV entries alongside the merged result in the upload response, or (b) parse the CSV client-side before upload to retain it. Option (a) is simpler -- add an `original_csv_entries` field to ExtractionResult when format is ECF.

2. **Batch size for ECF with double data**
   - What we know: Current batch size is 25 entries. ECF entries with source_data could be ~2x token count.
   - What's unclear: Whether Gemini 2.5 Flash handles the doubled context within rate limits.
   - Recommendation: Start with batch size 25, monitor token usage. Reduce to 15 if rate limits are hit more frequently.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | backend/pytest.ini |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox && make test` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRICH-11a | ECF cleanup prompt exists in CLEANUP_PROMPTS with 'ecf' key | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_prompts.py::test_ecf_cleanup_prompt_exists -x` | No -- Wave 0 |
| ENRICH-11b | ECF validation prompt exists in TOOL_PROMPTS with 'ecf' key | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_prompts.py::test_ecf_validation_prompt_exists -x` | No -- Wave 0 |
| ENRICH-11c | PipelineRequest accepts source_data field | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::test_pipeline_request_accepts_source_data -x` | No -- Wave 0 |
| ENRICH-11d | Cleanup endpoint passes source_data to provider for ECF | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::TestPipelineCleanup::test_ecf_cleanup_passes_source_data -x` | No -- Wave 0 |
| ENRICH-11e | Revenue cleanup injects batch median metadata | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::TestPipelineCleanup::test_revenue_injects_median -x` | No -- Wave 0 |
| ENRICH-11f | Extract/Title prompts include suffix standardization text | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_prompts.py::test_suffix_standardization_in_prompts -x` | No -- Wave 0 |
| ENRICH-11g | ProposedChangesPanel sorts by confidence | manual-only | Visual verification | N/A |
| ENRICH-11h | Frontend sends tool='ecf' for ECF format | manual-only | Visual verification (check network tab) | N/A |

### Sampling Rate
- **Per task commit:** `cd /Users/yojimbo/Documents/dev/toolbox && make test`
- **Per wave merge:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- [ ] `backend/tests/test_prompts.py` -- covers ENRICH-11a, ENRICH-11b, ENRICH-11f (prompt content assertions)
- [ ] Add to `backend/tests/test_pipeline.py` -- covers ENRICH-11c, ENRICH-11d, ENRICH-11e (pipeline plumbing tests)

## Sources

### Primary (HIGH confidence)
- Direct code reading of `backend/app/services/llm/prompts.py` -- current CLEANUP_PROMPTS structure
- Direct code reading of `backend/app/services/gemini_service.py` -- current TOOL_PROMPTS structure
- Direct code reading of `backend/app/services/llm/protocol.py` -- LLMProvider interface
- Direct code reading of `backend/app/services/llm/gemini_provider.py` -- GeminiProvider implementation
- Direct code reading of `backend/app/api/pipeline.py` -- pipeline endpoints and field mappings
- Direct code reading of `backend/app/models/pipeline.py` -- PipelineRequest/ProposedChange models
- Direct code reading of `frontend/src/components/ProposedChangesPanel.tsx` -- existing confidence display
- Direct code reading of `frontend/src/hooks/useEnrichmentPipeline.ts` -- pipeline hook
- Direct code reading of `frontend/src/pages/Extract.tsx` -- ECF format handling
- Direct code reading of `frontend/src/utils/api.ts` -- pipelineApi client

### Secondary (MEDIUM confidence)
- Python `statistics.median` stdlib -- well-known, stable API

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all code inspected directly
- Architecture: HIGH - straightforward extension of existing patterns, all integration points identified
- Pitfalls: HIGH - identified from direct code reading (protocol signature, entry alignment, token limits, existing confidence display)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable -- no external dependencies to go stale)
