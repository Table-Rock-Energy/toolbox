---
phase: 09-tool-specific-ai-prompts
plan: 01
subsystem: api
tags: [gemini, llm, prompts, pipeline, ecf, pydantic]

# Dependency graph
requires:
  - phase: 08-enrichment-pipeline-features
    provides: CLEANUP_PROMPTS dict, LLMProvider protocol, GeminiProvider, pipeline API
provides:
  - ECF as new tool key in CLEANUP_PROMPTS and TOOL_PROMPTS
  - PipelineRequest.source_data for cross-file comparison
  - Revenue batch median pre-computation for outlier detection
  - ECF field mappings in pipeline.py
  - ExtractionResult.original_csv_entries for ECF frontend access
  - Suffix standardization in extract/title prompts
affects: [09-02-frontend-wiring, 09-03-confidence-badges]

# Tech tracking
tech-stack:
  added: [statistics.median (stdlib)]
  patterns: [source_data passthrough for cross-file LLM context, Python pre-computation of statistics before LLM call]

key-files:
  created:
    - backend/tests/test_prompts.py
  modified:
    - backend/app/models/pipeline.py
    - backend/app/models/extract.py
    - backend/app/services/llm/protocol.py
    - backend/app/services/llm/gemini_provider.py
    - backend/app/services/llm/prompts.py
    - backend/app/services/gemini_service.py
    - backend/app/api/pipeline.py
    - backend/tests/test_pipeline.py

key-decisions:
  - "ECF cleanup prompt does dual-duty: standard cleanup + cross-file comparison in one pass"
  - "Revenue median pre-computed in Python (not by LLM) for reliability"
  - "source_data is keyword-only with None default for backward compatibility"

patterns-established:
  - "source_data passthrough: optional kwarg flows PipelineRequest -> pipeline_cleanup -> provider.cleanup_entries -> prompt context"
  - "Pre-computed statistics injected into entries as _prefixed metadata keys before LLM call"

requirements-completed: [ENRICH-11]

# Metrics
duration: 6min
completed: 2026-03-16
---

# Phase 9 Plan 1: Backend Pipeline Plumbing and Prompts Summary

**ECF cross-file cleanup prompt with source_data passthrough, suffix standardization for Extract/Title, and revenue outlier detection via pre-computed batch median**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-16T19:34:44Z
- **Completed:** 2026-03-16T19:40:30Z
- **Tasks:** 2 (TDD: 4 RED/GREEN commits)
- **Files modified:** 9

## Accomplishments
- Added ECF as 5th tool key with dedicated cleanup and validation prompts for cross-file PDF/CSV comparison
- Extended PipelineRequest with source_data field, LLMProvider protocol, and GeminiProvider to pass original CSV data for ECF
- Added suffix standardization (Jr, Sr, I-IV) to Extract and Title cleanup prompts
- Added statistical outlier detection to Revenue cleanup prompt using Python-computed batch median
- Added ECF field mappings to both DEFAULT_FIELD_MAPPINGS and DEFAULT_ENRICH_MAPPINGS
- Added original_csv_entries to ExtractionResult for ECF frontend access

## Task Commits

Each task was committed atomically (TDD: test then implementation):

1. **Task 1 RED: Pipeline plumbing tests** - `4f785bb` (test)
2. **Task 1 GREEN: Pipeline plumbing implementation** - `019599f` (feat)
3. **Task 2 RED: Prompt content tests** - `1996c7d` (test)
4. **Task 2 GREEN: ECF prompts + prompt refinements** - `ded4eb4` (feat)

## Files Created/Modified
- `backend/app/models/pipeline.py` - Added source_data field to PipelineRequest, updated tool description
- `backend/app/models/extract.py` - Added original_csv_entries to ExtractionResult
- `backend/app/services/llm/protocol.py` - Extended cleanup_entries with source_data kwarg
- `backend/app/services/llm/gemini_provider.py` - Accepts and passes source_data to prompt context
- `backend/app/services/llm/prompts.py` - Added CLEANUP_PROMPTS['ecf'], suffix standardization, outlier detection
- `backend/app/services/gemini_service.py` - Added TOOL_PROMPTS['ecf']
- `backend/app/api/pipeline.py` - ECF field mappings, revenue median injection, source_data passthrough
- `backend/tests/test_pipeline.py` - 6 new tests for plumbing
- `backend/tests/test_prompts.py` - 8 new tests for prompt content

## Decisions Made
- ECF cleanup prompt does dual-duty: standard cleanup + cross-file comparison in one pass (per user decision in CONTEXT.md)
- Revenue median pre-computed in Python using statistics.median, not by LLM (more reliable)
- source_data is keyword-only parameter with None default so all existing callers continue working without changes
- Cross-file discrepancies always marked as "high" confidence per user requirements

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend pipeline plumbing complete for ECF cross-file comparison
- Frontend needs to pass tool='ecf' and source_data when ECF format detected (Plan 02)
- ProposedChangesPanel needs confidence badges (Plan 02 or 03)

---
*Phase: 09-tool-specific-ai-prompts*
*Completed: 2026-03-16*
