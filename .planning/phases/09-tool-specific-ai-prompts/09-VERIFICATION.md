---
phase: 09-tool-specific-ai-prompts
verified: 2026-03-17T00:00:00Z
status: human_needed
score: 17/17 must-haves verified
human_verification:
  - test: "Upload an ECF PDF+CSV and run Clean Up, check Network tab"
    expected: "Request body to /api/pipeline/cleanup contains \"tool\": \"ecf\" and \"source_data\": [...] with original CSV rows"
    why_human: "Cannot verify network request payload without running the app"
  - test: "Upload any file and run Clean Up on any tool page to trigger ProposedChangesPanel"
    expected: "Group header rows show a small colored pill badge (green=high, yellow=medium, red/pink=low) between 'Row N' and 'N fields'. Groups with high-confidence changes appear before medium/low groups."
    why_human: "Visual appearance and sort order require browser interaction to observe"
---

# Phase 9: Tool-Specific AI Prompts Verification Report

**Phase Goal:** Each tool gets tailored AI QA prompts that leverage tool-specific data patterns for better cleanup and validation
**Verified:** 2026-03-17
**Status:** human_needed (all automated checks passed; 2 items need browser verification)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Extract and Title tools use name-focused cleanup prompts (suffix standardization, entity type inference from name patterns) | VERIFIED | `CLEANUP_PROMPTS["extract"]` contains "Suffix standardization: Normalize suffixes...Jr./Junior/junior -> Jr, Sr./Senior/senior -> Sr, The Third/3rd -> III" (prompts.py:15); same in `CLEANUP_PROMPTS["title"]` (prompts.py:33) |
| 2 | Revenue tool uses figure-verification prompts (cross-check amounts, flag outliers, validate decimal positions) | VERIFIED | `CLEANUP_PROMPTS["revenue"]` contains "Statistical outlier detection: If _batch_median_value is provided, flag any owner_value that exceeds 3x the median" (prompts.py:68); pipeline.py injects `_batch_median_value` and `_outlier_threshold` before LLM call (api/pipeline.py:113-126) |
| 3 | ECF tool uses cross-file accuracy prompts (compare PDF-extracted vs CSV-provided data, flag discrepancies between sources) | VERIFIED | `CLEANUP_PROMPTS["ecf"]` contains "cross-file", "PDF is authoritative", "source_data", "entry_number" (prompts.py:75-101); GeminiProvider appends "Original CSV source data for cross-file comparison" to user_prompt when source_data present (gemini_provider.py:59-63) |

**Score:** 3/3 success criteria verified

### Required Artifacts (Plan 01)

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/services/llm/prompts.py` | VERIFIED | CLEANUP_PROMPTS has 5 keys: extract, title, proration, revenue, ecf. ECF contains "cross-file" and "PDF is authoritative". Extract/title contain "Suffix standardization". Revenue contains "_batch_median_value". |
| `backend/app/services/gemini_service.py` | VERIFIED | TOOL_PROMPTS has "ecf" key containing "ECF", "Convey 640", "merged from two sources", "Suffix format" |
| `backend/app/models/pipeline.py` | VERIFIED | `source_data: list[dict] | None = Field(default=None, ...)` present; tool description includes "or ecf" |
| `backend/app/services/llm/protocol.py` | VERIFIED | `cleanup_entries` signature: `*, source_data: list[dict] | None = None` keyword-only parameter |
| `backend/app/api/pipeline.py` | VERIFIED | ECF in DEFAULT_FIELD_MAPPINGS and DEFAULT_ENRICH_MAPPINGS; `from statistics import median as compute_median`; `_batch_median_value`/`_outlier_threshold` injection; `source_data=request.source_data` passthrough |
| `backend/tests/test_prompts.py` | VERIFIED | Contains: test_ecf_cleanup_prompt_exists, test_ecf_validation_prompt_exists, test_suffix_standardization_in_extract, test_suffix_standardization_in_title, test_revenue_outlier_detection, test_all_tools_have_cleanup_prompts |
| `backend/tests/test_pipeline.py` | VERIFIED | Contains: test_pipeline_request_accepts_source_data, test_ecf_cleanup_passes_source_data, test_revenue_injects_median, test_revenue_skips_median_when_few_values, test_extract_does_not_inject_median |
| `backend/app/models/extract.py` | VERIFIED | `original_csv_entries: Optional[list[dict]] = Field(None, ...)` present |

### Required Artifacts (Plan 02)

| Artifact | Status | Details |
|----------|--------|---------|
| `frontend/src/utils/api.ts` | VERIFIED | PipelineRequest interface has `source_data?: Record<string, unknown>[] | null`; pipelineApi.cleanup/validate/enrich all accept `sourceData` 4th param and pass as `source_data` |
| `frontend/src/hooks/useEnrichmentPipeline.ts` | VERIFIED | UseEnrichmentPipelineOptions includes `sourceData?: Record<string, unknown>[]`; destructured and passed: `apiMethod(tool, entries, undefined, step === 'cleanup' ? sourceData : undefined)` |
| `frontend/src/pages/Extract.tsx` | VERIFIED | `const [originalCsvEntries, setOriginalCsvEntries] = useState<Record<string, unknown>[]>([])` at line 126; sets `originalCsvEntries` from `data.result.original_csv_entries`; `tool: formatHint === 'ECF' ? 'ecf' : 'extract'`; `sourceData: formatHint === 'ECF' ? originalCsvEntries : undefined` |
| `frontend/src/components/ProposedChangesPanel.tsx` | VERIFIED | `CONFIDENCE_ORDER` defined; `sortedGroups` sorts by minimum confidence order; `highestConfidence` computed per group; confidence badge rendered with `CONFIDENCE_STYLES[highestConfidence]` in group header |
| `backend/app/api/extract.py` | VERIFIED | `original_csv_entries` captured from CSV parse before merge; set on ExtractionResult conditionally when format is ECF |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/app/api/pipeline.py` | `backend/app/services/llm/gemini_provider.py` | `provider.cleanup_entries(request.tool, request.entries, source_data=request.source_data)` | WIRED | Line 128-130 in pipeline.py passes source_data kwarg |
| `backend/app/services/llm/gemini_provider.py` | `backend/app/services/llm/prompts.py` | `CLEANUP_PROMPTS.get(tool)` | WIRED | Line 40: `system_prompt = CLEANUP_PROMPTS.get(tool, CLEANUP_PROMPTS["extract"])` |
| `frontend/src/pages/Extract.tsx` | `frontend/src/hooks/useEnrichmentPipeline.ts` | `sourceData` prop | WIRED | Extract.tsx line 616 passes `sourceData: formatHint === 'ECF' ? originalCsvEntries : undefined` |
| `frontend/src/hooks/useEnrichmentPipeline.ts` | `frontend/src/utils/api.ts` | `pipelineApi.cleanup(tool, entries, undefined, step === 'cleanup' ? sourceData : undefined)` | WIRED | Line 82 passes sourceData; pipelineApi serializes as `source_data` in request body |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| ENRICH-11 | 09-01, 09-02 | Tool-specific AI QA prompts: name cleanup for Extract/Title, figure verification for Revenue, address cleaning for all, overall accuracy check across both source files for ECF | SATISFIED | All five CLEANUP_PROMPTS keys exist with tool-specific content; ECF TOOL_PROMPTS entry in gemini_service.py; end-to-end wiring from Extract.tsx -> useEnrichmentPipeline -> pipelineApi -> backend pipeline_cleanup -> GeminiProvider -> CLEANUP_PROMPTS |

No orphaned requirements found. REQUIREMENTS.md maps ENRICH-11 to Phase 9 and marks it Complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/hooks/useEnrichmentPipeline.ts` | 91 | `console.error(...)` in error branch (no user-facing error state set) | Info | Pipeline step failures are silently logged; user sees no error message. Pre-existing pattern, not introduced in this phase. |

No blockers or stubs detected. All implementations are substantive.

### Test Results

All 24 backend tests pass (0 failures, 9 deprecation warnings only):

```
backend/tests/test_pipeline.py  -- 5 new tests for source_data and revenue median
backend/tests/test_prompts.py   -- 8 tests for ECF/extract/title/revenue prompt content
======================== 24 passed, 9 warnings in 0.05s
```

TypeScript: Compiles cleanly with no errors (`tsc --noEmit` exits 0).

### Human Verification Required

#### 1. ECF Network Payload Verification

**Test:** Upload an ECF PDF and accompanying Convey 640 CSV on the Extract page. Run Clean Up. Open the browser Network tab and inspect the POST /api/pipeline/cleanup request body.
**Expected:** The request body contains `"tool": "ecf"` (not `"extract"`) and `"source_data": [...]` with a non-empty array of the original CSV row dicts.
**Why human:** Cannot execute browser network requests programmatically during code verification.

#### 2. Confidence Badge Visual Appearance

**Test:** On any tool page, upload a file and run Clean Up to generate proposed changes. Observe the ProposedChangesPanel group header rows (collapsed view).
**Expected:** Each group header shows a small colored pill badge between "Row N" and "N fields". Green badge = high confidence, yellow = medium, red/pink = low. Groups with the highest-confidence changes appear at the top of the list.
**Why human:** Visual layout, badge colors, and sort order require browser rendering to verify.

### Summary

All 17 must-have items verified automatically:

- Backend: ECF cleanup prompt (cross-file comparison, PDF-authoritative) and validation prompt (Convey 640) both present in their respective dicts. Extract/Title prompts updated with suffix standardization. Revenue prompt updated with statistical outlier detection. Pipeline API wired for revenue median pre-computation and source_data passthrough. ExtractionResult carries original_csv_entries for ECF.
- Frontend: PipelineRequest TypeScript type includes source_data. pipelineApi methods pass sourceData through. useEnrichmentPipeline accepts and forwards sourceData for cleanup step only. Extract.tsx routes ECF uploads to tool='ecf' and captures original CSV entries. ProposedChangesPanel has confidence badges in group headers with confidence-based sort.
- Tests: 24 backend tests pass. TypeScript compiles cleanly.
- ENRICH-11: Fully satisfied across both plans.

Two human verification items remain — both are observability checks (network payload content, visual badge rendering) that cannot be verified from code alone.

---

_Verified: 2026-03-17_
_Verifier: Claude (gsd-verifier)_
