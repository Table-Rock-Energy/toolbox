# Feature Landscape

**Domain:** AI enrichment pipeline debugging + LM Studio integration for on-prem deployment
**Researched:** 2026-03-31
**Milestone:** v2.2 Post-Migration Fixes & AI Enrichment

## Table Stakes

Features required for AI enrichment to be considered "working." Without these, the pipeline is non-functional on the server.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| LM Studio network connectivity from Docker | Pipeline calls `host.docker.internal:1234/v1` -- must resolve and connect | Low | LM Studio server running, `--add-host` on Linux | Linux Docker does NOT auto-resolve `host.docker.internal`; needs `--add-host host.docker.internal:host-gateway` in docker-compose or use `172.17.0.1` directly |
| LM Studio "Serve on Network" enabled | Default binds to `127.0.0.1` only; Docker container is a different network namespace | Low | LM Studio UI toggle | Must bind to `0.0.0.0` in LM Studio Developer tab settings, not just localhost |
| Model loaded in LM Studio before API call | `/v1/chat/completions` returns 500 or empty if no model loaded | Low | Sufficient VRAM/RAM for model | LM Studio does NOT auto-load; model must be explicitly loaded in the UI or via API |
| Correct model ID in `llm_model` config | Model ID must match what `/v1/models` returns (includes quantization suffix) | Low | Model discovery endpoint working | Current default `qwen3.5-35b-a3b` may not match the actual loaded model ID format |
| Valid JSON responses from LLM | Pipeline expects `{"suggestions": [...]}` format | Med | Model capability, prompt quality | Local models are less reliable at structured JSON than cloud APIs; `parse_json_response` handles markdown fences and preamble but cannot fix malformed JSON |
| Timeout handling for slow inference | Local inference on 35B model can take 60-300s per batch | Low | Already set to 300s | 5-minute timeout is reasonable but batches of 25 entries with complex prompts may still hit it on underpowered hardware |
| `AI_PROVIDER=lmstudio` in production env | Config defaults to `"none"` -- must be explicitly set | Low | Environment variable in Docker/systemd | Without this, `get_llm_provider()` returns `None` and all AI steps are silently skipped |
| Nginx proxy handles pipeline endpoints | Pipeline responses can be large (all entries returned) and slow (AI inference) | Low | Nginx config for `/api/pipeline/*` | Need `proxy_read_timeout`, `proxy_buffering off` for streaming NDJSON responses |
| All ad-hoc fixes tracked in milestone | 5 commits landed between v2.1 and v2.2 start | Low | Already shipped | Revenue Decimal coercion, RRC PostgreSQL migration, GHL-prep filter, AI enrichment fixes, admin password hashing |

## Already Shipped (Track in v2.2)

These fixes landed between v2.1 and v2.2 milestone start. They need retroactive tracking.

| Fix | Commit | What It Solved |
|-----|--------|---------------|
| Revenue Decimal-to-float coercion | `596b7d3` | `check_amount` column failed DB persistence as Python Decimal |
| RRC data PostgreSQL migration + model discovery | `c76a6db` | RRC data now persists to PostgreSQL, LM Studio models discovered from filesystem |
| GHL-prep filter fix + revenue column widening | `0c8b06a` | Filter dropdown worked incorrectly, revenue table columns too narrow |
| AI enrichment fixes + LM Studio model discovery | `986ea31` | Provider factory improvements, model listing from `llm_models_dir` |
| Admin password hashing import fix | `9ed6270` | Wrong import path for bcrypt hashing in user creation |

## Differentiators

Features that improve AI enrichment quality and reliability beyond basic connectivity.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| Structured output via `response_format` | LM Studio supports OpenAI-compatible `response_format: { type: "json_schema", json_schema: {...} }` which guarantees valid JSON | Med | LM Studio 0.3+, model support for structured output | Currently relying on prompt-only JSON enforcement + regex fallback parsing; structured output would eliminate JSON parse failures entirely. `CLEANUP_RESPONSE_SCHEMA` already defined in `prompts.py` but unused |
| Health check before pipeline run | Ping `/v1/models` before starting batch to fail fast with clear error | Low | None | Currently pipeline starts, sends first batch, then fails on connection error -- user sees "LLM cleanup error for batch 0" in logs with no UI feedback |
| Model warm-up / keep-alive | First inference after model load is 3-5x slower (loading into GPU memory) | Low | LM Studio config | LM Studio has a "keep model loaded" setting; without it, model unloads after timeout and first request is slow |
| Smaller default batch size for local inference | 25 entries per batch may overwhelm context window on smaller models | Low | Configurable via admin settings (already exists) | Consider defaulting to 10 for local inference; 25 entries as JSON can be 5-10K tokens input + large system prompt |
| Revenue-specific AI verification | `verify_revenue_entries()` exists but pipeline only calls `cleanup_entries()` for the "names" step | Med | Pipeline wiring in `data_enrichment_pipeline.py` | The revenue verify prompt does math checking and gap-filling -- valuable but not wired into the unified enrichment flow |
| Retry with smaller batch on failure | If a batch fails (timeout, malformed JSON), retry with half the batch size | Med | None | Current behavior: log error, skip batch, continue. Lost suggestions are never recovered |
| Admin UI showing LM Studio connection status | Model discovery endpoint exists but connection status not surfaced in enrichment UI | Low | Frontend work | User has no way to know if LM Studio is reachable before clicking "Enrich" |
| LM Studio model switching via admin UI | Change models without restarting server | Low | Model list endpoint already exists at `GET /api/admin/settings/available-models` | Frontend dropdown to select from discovered models |

## Anti-Features

Features to explicitly NOT build for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Address validation via LLM | LLMs cannot authoritatively validate addresses -- they hallucinate ZIP codes and street numbers. Research confirms: "You should not use generative AI tools to validate your addresses." | Keep Google Maps API for address validation (already separate pipeline step). LLM only standardizes format. |
| Auto-loading models via LM Studio API | LM Studio API model loading is fragile and version-dependent | Require model to be manually loaded in LM Studio UI; surface clear error if no model loaded |
| Multiple concurrent LLM providers | Only one server (LM Studio) exists on-prem; Gemini already removed in v2.0 | Keep single-provider factory pattern. Adding Ollama/vLLM support is future scope |
| Automatic prompt tuning per model | Different models respond differently to same prompt; tempting to add model-specific prompt variants | Use one prompt set. If model struggles with JSON output, use `response_format` structured output instead |
| Streaming LLM token responses to UI | LM Studio supports SSE streaming but parsing partial JSON mid-stream adds complexity | Keep batch request/response pattern. Progress already tracked at batch level via OperationContext |
| Caching LLM responses | Deterministic data cleanup on same input is appealing but entries change between runs | Skip caching -- data changes each upload. Not worth cache invalidation complexity |
| Retry/fallback to cloud AI | Defeats purpose of on-prem migration | Fix local connectivity instead |
| Automated AI model downloading | Over-engineering for single-server setup | Use LM Studio's built-in model browser |

## Feature Dependencies

```
LM Studio running + network accessible (0.0.0.0 binding)
  -> Docker container can reach host (--add-host or direct IP)
    -> Model loaded in LM Studio
      -> AI_PROVIDER=lmstudio in env
        -> get_llm_provider() returns OpenAIProvider
          -> cleanup_entries() / validate_entries() called in pipeline
            -> JSON parsed from response via parse_json_response()
              -> ProposedChange / AiSuggestion objects applied to entries

Nginx config for pipeline endpoints
  -> proxy_read_timeout >= 300s for AI inference
  -> proxy_buffering off for NDJSON streaming (enrich_entries)
  -> Both /api/pipeline/* and streaming enrichment endpoints covered

Model discovery endpoint (admin GET /settings/available-models)
  -> Filesystem scan (llm_models_dir = /mnt/array/lm-studio/models)
  -> LM Studio /v1/models API query
  -> Merged model list with loaded status
```

## MVP Recommendation

Priority order for getting AI enrichment working end-to-end:

1. **Network connectivity** -- Verify `host.docker.internal` resolves from Docker container on the Linux server. If not, switch `llm_api_base` to use the host's LAN IP or `172.17.0.1`. Ensure LM Studio binds to `0.0.0.0` (not default `127.0.0.1`).
2. **Environment config** -- Set `AI_PROVIDER=lmstudio`, `LLM_API_BASE`, and `LLM_MODEL` in production environment. Model ID must match `/v1/models` response exactly (use model discovery endpoint to find the right ID).
3. **Nginx pipeline timeout** -- Add `proxy_read_timeout 300s` and `proxy_buffering off` for `/api/pipeline/` location block.
4. **Health check before pipeline** -- Add a fast `/v1/models` ping at the start of `cleanup_entries()` to fail fast with a user-visible error instead of timing out after 300s.
5. **Structured output** -- Add `response_format` parameter to `chat.completions.create()` calls using `CLEANUP_RESPONSE_SCHEMA` already defined in `prompts.py`. Single highest-impact reliability improvement.

Defer: Revenue AI verification wiring, retry with smaller batches, admin connection status UI, model switching UI.

## Common LM Studio Failure Modes (Reference)

Specific failure scenarios to investigate when debugging on the server.

| Failure | Symptom | Root Cause | Fix |
|---------|---------|------------|-----|
| Connection refused | `openai.APIConnectionError` in logs | LM Studio not running, bound to localhost only, or Docker can't reach host | Bind LM Studio to `0.0.0.0`, add `--add-host host.docker.internal:host-gateway` to docker-compose, or use host LAN IP |
| 500 from `/v1/chat/completions` | HTTP 500 in OpenAI SDK | No model loaded, or model ID mismatch in request | Load model in LM Studio UI, match `llm_model` config to actual model ID from `/v1/models` |
| Timeout (300s) | `openai.APITimeoutError` | Model too large for hardware, or batch too big (25 entries = 5-10K tokens) | Reduce batch size to 10, use smaller/quantized model, increase timeout |
| Malformed JSON response | `ValueError: Could not extract JSON from LLM response` | Model not following JSON instructions reliably | Use `response_format` structured output (guarantees valid JSON), or switch to model with better instruction following |
| Empty suggestions array | Pipeline completes with 0 changes applied | Model returns `{"suggestions": []}` for everything | Check with known-bad data (ALL CAPS names); if still empty, model may not understand domain. Try different model or smaller batch |
| `stream: false` rejection | Socket closed with no response, no error | Some older LM Studio versions reject explicit `stream: false` | Update LM Studio to 0.3+; OpenAI SDK sends `stream: false` by default |
| Model unloaded between requests | First batch succeeds, later batches get 500 | LM Studio auto-unloaded model due to inactivity timeout | Enable "Keep model loaded" in LM Studio settings |
| Nginx timeout on pipeline | 504 Gateway Timeout in browser | Nginx default `proxy_read_timeout` is 60s, AI inference takes 60-300s | Set `proxy_read_timeout 300s` in pipeline location block |

## End-to-End AI Enrichment Flow (Expected Behavior)

When working correctly:

1. User uploads document, gets parsed entries displayed in table
2. User clicks "Enrich" button -> opens enrichment modal (unified, single-button from v1.6)
3. OperationContext manages batch-aware pipeline (25-entry batches from v1.7)
4. Pipeline runs steps sequentially via `enrich_entries()` or `/api/pipeline/cleanup`:
   - Address validation (Google Maps) -- skips if not configured
   - Places lookup (Google Places) -- skips if not configured
   - Contact enrichment (PDL/SearchBug) -- skips if not configured
   - **AI Cleanup** (LM Studio) -- `get_llm_provider()` -> `OpenAIProvider` -> `cleanup_entries()`
   - Name splitting (programmatic)
5. AI Cleanup step detail:
   - System prompt from `CLEANUP_PROMPTS[tool]` (tool-specific: extract, title, proration, revenue, ecf)
   - Entries serialized as JSON with index fields
   - Sent to LM Studio `/v1/chat/completions` with `temperature=0.1`
   - Response parsed via `parse_json_response()` (tries: direct JSON, markdown fence, first `{...}` block)
   - Suggestions filtered to high/medium confidence
   - Entity type re-detection runs after AI name corrections
   - Progress events streamed per batch
6. Frontend highlights changed cells in green with click-to-reveal original values (v1.8 key-based tracking)
7. User can undo all enrichment changes with global undo button
8. Export includes enrichment changes applied to preview state (v1.5 preview-as-source-of-truth)

## Sources

- [LM Studio OpenAI Compatibility Docs](https://lmstudio.ai/docs/developer/openai-compat)
- [LM Studio Structured Output](https://lmstudio.ai/docs/developer/openai-compat/structured-output)
- [LM Studio Server Settings](https://lmstudio.ai/docs/developer/core/server/settings)
- [LM Studio Serve on Network](https://lmstudio.ai/docs/developer/core/server/serve-on-network)
- [LM Studio CORS issue with host.docker.internal](https://github.com/lmstudio-ai/lms/issues/189)
- [Docker host.docker.internal on Linux](https://forums.docker.com/t/connection-refused-on-host-docker-internal/136925)
- [LM Studio model ID mismatch issue](https://github.com/cline/cline/issues/8030)
- [LM Studio stream:false bug](https://github.com/langchain4j/langchain4j/issues/2882)
- [AI address validation limitations](https://www.smarty.com/articles/llm-ai-address-validation)
- [Pydantic for validating LLM outputs](https://machinelearningmastery.com/the-complete-guide-to-using-pydantic-for-validating-llm-outputs/)
- Codebase: `backend/app/services/llm/openai_provider.py` -- OpenAI provider with `parse_json_response()` fallback chain
- Codebase: `backend/app/services/llm/prompts.py` -- all prompt constants + unused `CLEANUP_RESPONSE_SCHEMA`
- Codebase: `backend/app/services/data_enrichment_pipeline.py` -- 5-step enrichment pipeline (AI is step 4)
- Codebase: `backend/app/api/pipeline.py` -- pipeline API endpoints (cleanup/validate/enrich)
- Codebase: `backend/app/api/admin.py` lines 472-556 -- model discovery endpoint
- Codebase: `backend/app/core/config.py` lines 44-49 -- LM Studio config defaults
