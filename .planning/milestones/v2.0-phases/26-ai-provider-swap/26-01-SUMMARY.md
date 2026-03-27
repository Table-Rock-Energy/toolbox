---
phase: 26-ai-provider-swap
plan: 01
subsystem: ai
tags: [openai, lmstudio, llm, provider-abstraction, json-parsing]

# Dependency graph
requires:
  - phase: 25-firestore-removal
    provides: PostgreSQL-only backend with no Firestore dependencies
provides:
  - OpenAIProvider class implementing LLMProvider protocol via AsyncOpenAI
  - parse_json_response utility for LM Studio output parsing
  - Provider factory routing on ai_provider config
  - TOOL_PROMPTS and REVENUE_VERIFY_PROMPT centralized in prompts.py
  - Config fields: ai_provider, llm_api_base, llm_model, llm_api_key, use_ai
affects: [26-ai-provider-swap]

# Tech tracking
tech-stack:
  added: [openai>=2.0.0]
  patterns: [openai-compatible-local-inference, json-response-extraction, provider-factory-routing]

key-files:
  created:
    - backend/app/services/llm/openai_provider.py
  modified:
    - backend/app/services/llm/__init__.py
    - backend/app/core/config.py
    - backend/app/services/llm/prompts.py
    - backend/requirements.txt
    - backend/tests/test_llm_protocol.py

key-decisions:
  - "openai SDK for LM Studio (OpenAI-compatible API, same SDK pattern as cloud providers)"
  - "Gemini legacy fallback in factory (preserves existing provider until Plan 02 removes it)"
  - "No rate limiting for local inference (LM Studio has no rate limits)"
  - "parse_json_response handles 3 output patterns (clean, markdown-fenced, preamble)"

patterns-established:
  - "OpenAI-compatible provider pattern: AsyncOpenAI with configurable base_url"
  - "JSON response extraction: try direct -> try fenced -> try brace match -> raise ValueError"

requirements-completed: [AI-01, AI-02]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 26 Plan 01: OpenAI Provider Summary

**AsyncOpenAI-based LLM provider for LM Studio with JSON response parsing, provider factory routing, and centralized prompt constants**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T22:19:43Z
- **Completed:** 2026-03-25T22:23:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 6

## Accomplishments
- OpenAIProvider class implementing LLMProvider protocol with cleanup_entries, validate_entries, verify_revenue_entries
- parse_json_response handles clean JSON, markdown-fenced, and preamble-wrapped LLM outputs
- Provider factory routes on ai_provider config with Gemini legacy fallback
- Config fields: ai_provider, llm_api_base, llm_model, llm_api_key with use_ai property
- TOOL_PROMPTS and REVENUE_VERIFY_PROMPT moved from gemini_service.py to prompts.py
- 21 tests pass including protocol satisfaction, JSON parsing, factory routing, and cleanup_entries mocking

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `7d47d6f` (test)
2. **Task 1 (GREEN): Implementation** - `1ac8c76` (feat)

## Files Created/Modified
- `backend/app/services/llm/openai_provider.py` - OpenAIProvider class + parse_json_response utility
- `backend/app/services/llm/__init__.py` - Factory routing on ai_provider config
- `backend/app/core/config.py` - ai_provider, llm_api_base, llm_model, llm_api_key, use_ai
- `backend/app/services/llm/prompts.py` - Added TOOL_PROMPTS, REVENUE_VERIFY_PROMPT, VALIDATION_RESPONSE_SCHEMA
- `backend/requirements.txt` - Added openai>=2.0.0
- `backend/tests/test_llm_protocol.py` - Rewritten for OpenAIProvider (21 tests)

## Decisions Made
- openai SDK for LM Studio: OpenAI-compatible API means same SDK works for local and cloud
- Gemini legacy fallback preserved in factory: factory falls back to GeminiProvider when ai_provider is unset, ensuring existing deployments work until Plan 02 completes the swap
- No rate limiting for local inference: LM Studio has no rate limits, eliminating the Gemini rate-limit complexity
- parse_json_response handles 3 patterns: LM Studio models may emit clean JSON, markdown-fenced JSON, or preamble+JSON

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. New env vars (AI_PROVIDER, LLM_API_BASE, LLM_MODEL, LLM_API_KEY) default to safe values.

## Next Phase Readiness
- OpenAI provider infrastructure ready for Plan 02 to swap Gemini references
- Factory, config, prompts all in place
- All tests pass

---
*Phase: 26-ai-provider-swap*
*Completed: 2026-03-25*
