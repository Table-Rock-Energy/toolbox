# Phase 26: AI Provider Swap - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Create OpenAI-compatible provider for LM Studio implementing LLMProvider protocol. Provider factory routes based on AI_PROVIDER config (lmstudio or none). Remove Gemini provider and google-genai dependency. JSON response parsing handles markdown-fenced and preamble-wrapped model output. Enrichment pipeline works end-to-end with LM Studio or gracefully skips when AI_PROVIDER=none.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

Key research findings to incorporate:
- OpenAI SDK (>=1.60.0) for LM Studio — set base_url, api_key="lm-studio"
- LM Studio default endpoint: http://localhost:1234/v1
- JSON mode unreliable — prompt for JSON and parse from text (regex {…} extraction)
- No API key needed for LM Studio — pass dummy value
- Skip rate limiting for local inference (no API costs)
- Keep LLMProvider protocol unchanged — new provider implements same interface
- Existing provider factory in llm/__init__.py — add OpenAI branch
- New env vars: AI_PROVIDER (default "none"), LLM_API_BASE (default "http://localhost:1234/v1"), LLM_MODEL (default "local-model")
- Remove google-genai from requirements.txt, delete gemini_service.py and GeminiProvider

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/llm/protocol.py` — LLMProvider protocol (cleanup_entries, is_available)
- `backend/app/services/llm/__init__.py` — provider factory (get_llm_provider)
- `backend/app/services/llm/gemini_provider.py` — GeminiProvider (to be replaced)
- `backend/app/services/gemini_service.py` — Gemini client (to be deleted)
- `backend/app/core/config.py` — Settings model

### Integration Points
- llm/__init__.py factory → add OpenAI provider selection
- ai_validation.py → uses get_llm_provider()
- gemini_revenue_parser.py → direct Gemini client calls
- enrichment pipeline → calls cleanup_entries via LLMProvider

</code_context>

<specifics>
## Specific Ideas

User specified: "We are going to use local qwen models on the server via LM Studio"
Default model: qwen3.5-35b-a3b (from user spec)

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
