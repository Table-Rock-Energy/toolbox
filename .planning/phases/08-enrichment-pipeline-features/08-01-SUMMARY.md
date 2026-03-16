---
phase: 08-enrichment-pipeline-features
plan: 01
subsystem: api
tags: [fastapi, pydantic, gemini, google-maps, enrichment, protocol, pipeline]

# Dependency graph
requires:
  - phase: 07-enrichment-ui-preview-state
    provides: EnrichmentToolbar UI with stub callbacks for pipeline steps
provides:
  - LLMProvider Protocol class for swappable AI providers
  - GeminiProvider implementation for AI cleanup
  - ProposedChange/PipelineRequest/PipelineResponse Pydantic models
  - Three pipeline API endpoints at /api/pipeline/{cleanup,validate,enrich}
  - CLEANUP_PROMPTS for all 4 tools (extract, title, proration, revenue)
  - Default field mappings per tool for address validation and enrichment
affects: [08-enrichment-pipeline-features]

# Tech tracking
tech-stack:
  added: []
  patterns: [Protocol-based provider abstraction for LLM swapping, unified ProposedChange response format across pipeline steps]

key-files:
  created:
    - backend/app/models/pipeline.py
    - backend/app/services/llm/__init__.py
    - backend/app/services/llm/protocol.py
    - backend/app/services/llm/gemini_provider.py
    - backend/app/services/llm/prompts.py
    - backend/app/api/pipeline.py
    - backend/tests/test_llm_protocol.py
    - backend/tests/test_pipeline.py
  modified:
    - backend/app/main.py

key-decisions:
  - "CLEANUP_PROMPTS are correction-focused (active cleanup) vs existing TOOL_PROMPTS which are validation-focused (passive review)"
  - "validate endpoint calls validate_address() per entry instead of validate_addresses_batch() to build ProposedChange diffs without auto-applying"
  - "Field mapping system with per-tool defaults and request-level overrides for consistent API across tools"
  - "Revenue tool returns empty proposed changes for validate since it has no address fields"

patterns-established:
  - "Protocol pattern: LLMProvider Protocol with runtime_checkable for isinstance checks and provider swapping"
  - "Pipeline response pattern: All three endpoints return identical PipelineResponse with ProposedChange list"
  - "Field mapping pattern: DEFAULT_FIELD_MAPPINGS dict with request.field_mapping override"

requirements-completed: [ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-10]

# Metrics
duration: 18min
completed: 2026-03-16
---

# Phase 8 Plan 1: Pipeline API Summary

**LLM provider protocol with Gemini implementation, pipeline Pydantic models, and three unified API endpoints for AI cleanup, address validation, and contact enrichment**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-16T15:43:18Z
- **Completed:** 2026-03-16T16:02:00Z
- **Tasks:** 2 (TDD: 4 commits)
- **Files modified:** 9

## Accomplishments
- LLMProvider Protocol class with GeminiProvider that reuses existing gemini_service rate-limiting infrastructure
- Three pipeline endpoints (cleanup, validate, enrich) all returning unified PipelineResponse with ProposedChange list
- CLEANUP_PROMPTS distinct from existing TOOL_PROMPTS -- correction-focused for name casing, abbreviations, entity types, format normalization
- 22 tests covering protocol conformance, model validation, endpoint behavior, field mapping, and auth requirements

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: LLM protocol, models, prompts** (TDD)
   - RED: `ff6b5a5` (test) - Failing tests for protocol, models, prompts
   - GREEN: `ea4518f` (feat) - Implementation passing all 12 tests

2. **Task 2: Pipeline API endpoints** (TDD)
   - RED: `2b63058` (test) - Failing tests for cleanup, validate, enrich endpoints
   - GREEN: `6ba8089` (feat) - Implementation passing all 22 tests

## Files Created/Modified
- `backend/app/models/pipeline.py` - ProposedChange, PipelineRequest, PipelineResponse Pydantic models
- `backend/app/services/llm/__init__.py` - get_llm_provider() factory function
- `backend/app/services/llm/protocol.py` - LLMProvider Protocol class (runtime_checkable)
- `backend/app/services/llm/gemini_provider.py` - GeminiProvider with cleanup_entries using gemini_service infrastructure
- `backend/app/services/llm/prompts.py` - CLEANUP_PROMPTS for extract, title, proration, revenue + response schema
- `backend/app/api/pipeline.py` - Three pipeline endpoints with field mapping and error handling
- `backend/app/main.py` - Router mounting for /api/pipeline with auth dependency
- `backend/tests/test_llm_protocol.py` - 12 tests for protocol, provider, models, prompts
- `backend/tests/test_pipeline.py` - 10 tests for endpoints, field mapping, auth

## Decisions Made
- CLEANUP_PROMPTS are correction-focused (name casing, abbreviation expansion, entity type inference) vs existing TOOL_PROMPTS which flag/validate (passive review). This avoids conflating the two concerns.
- Validate endpoint uses validate_address() per entry (not validate_addresses_batch) to build ProposedChange diffs per-field without auto-applying changes. This lets the frontend control which changes to accept.
- Revenue tool returns empty proposed changes for validate since revenue data has no address fields.
- Field mapping system: per-tool defaults (extract uses mailing_address, title uses address, etc.) with request-level override support.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock for Gemini client initialization**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test for cleanup_entries was calling real _get_client() which requires GEMINI_API_KEY
- **Fix:** Added patch for app.services.gemini_service._get_client to return MagicMock
- **Files modified:** backend/tests/test_llm_protocol.py
- **Verification:** All 12 tests pass
- **Committed in:** ea4518f (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test fix. No scope creep.

## Issues Encountered
- Full test suite (251 tests) times out during execution -- pre-existing issue with some test fixtures, not related to this plan's changes. Targeted test runs (22 new tests + auth/features tests) all pass.

## User Setup Required
None - no external service configuration required. Pipeline endpoints gracefully handle missing API keys by returning error responses.

## Next Phase Readiness
- Pipeline API ready for frontend wiring in subsequent plans
- EnrichmentToolbar callbacks can now call /api/pipeline/{cleanup,validate,enrich}
- LLM provider can be swapped to Ollama/Qwen in future by implementing LLMProvider protocol

---
*Phase: 08-enrichment-pipeline-features*
*Completed: 2026-03-16*
