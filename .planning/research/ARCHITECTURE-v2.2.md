# Architecture: AI Enrichment Pipeline + Nginx Proxy

**Domain:** AI enrichment data flow and on-prem proxy configuration
**Researched:** 2026-03-31
**Confidence:** HIGH (based on full codebase analysis)

## Current Architecture

The AI enrichment pipeline has a clean layered architecture with well-defined integration points. Here is the complete request flow from button click to LM Studio inference and back.

### End-to-End Data Flow

```
User clicks "Enrich" button
         |
  ┌──────┴───────────────────────┐
  │  UnifiedEnrichButton.tsx     │
  │  → useEnrichmentPipeline.ts  │
  │  → OR OperationContext.tsx   │
  │    (batch-aware pipeline)    │
  └──────────┬───────────────────┘
             |  POST /api/pipeline/cleanup
             |  { tool, entries[], field_mapping, source_data }
             |  timeout: 300s (frontend)
  ┌──────────┴───────────────────┐
  │  Nginx reverse proxy         │
  │  (port 443 → 127.0.0.1:8080)│
  │  proxy_read_timeout: 120s    │  ← PROBLEM: default location
  └──────────┬───────────────────┘
             |
  ┌──────────┴───────────────────┐
  │  FastAPI pipeline.py router  │
  │  POST /api/pipeline/cleanup  │
  │  Auth: require_auth (JWT)    │
  └──────────┬───────────────────┘
             |
  ┌──────────┴───────────────────┐
  │  get_llm_provider()          │
  │  → checks settings.ai_provider│
  │  → returns OpenAIProvider    │
  │    or None                   │
  └──────────┬───────────────────┘
             |
  ┌──────────┴───────────────────┐
  │  OpenAIProvider              │
  │  .cleanup_entries()          │
  │  → batches entries (25/batch)│
  │  → for each batch:          │
  │    1. check disconnect       │
  │    2. build prompt           │
  │    3. call LM Studio API     │
  │    4. parse JSON response    │
  │    5. collect suggestions    │
  └──────────┬───────────────────┘
             |  HTTP POST (AsyncOpenAI SDK)
             |  http://host.docker.internal:1234/v1/chat/completions
             |  timeout: 300s (SDK)
  ┌──────────┴───────────────────┐
  │  LM Studio                   │
  │  Local inference server      │
  │  Model: qwen3.5-35b-a3b     │
  │  Port: 1234                  │
  └──────────────────────────────┘
```

### Component Inventory

| Component | File | Role | Status |
|-----------|------|------|--------|
| Enrich button | `UnifiedEnrichButton.tsx` | Single entry point for all enrichment | Existing |
| Pipeline hook | `useEnrichmentPipeline.ts` | Individual step execution + review | Existing |
| Operation context | `OperationContext.tsx` | Batch-aware multi-step pipeline with persistence | Existing |
| API client | `utils/api.ts` → `pipelineApi` | HTTP calls with 300s timeout | Existing |
| Feature flags | `api/features.py` → `/api/features/status` | Reports which steps are enabled | Existing |
| Pipeline router | `api/pipeline.py` | 3 endpoints: cleanup, validate, enrich | Existing |
| LLM factory | `services/llm/__init__.py` | `get_llm_provider()` routing | Existing |
| LLM protocol | `services/llm/protocol.py` | `LLMProvider` Protocol class | Existing |
| OpenAI provider | `services/llm/openai_provider.py` | AsyncOpenAI client → LM Studio | Existing |
| Prompts | `services/llm/prompts.py` | Tool-specific cleanup + validation prompts | Existing |
| Config | `core/config.py` | `ai_provider`, `llm_api_base`, `llm_model` settings | Existing |
| Admin models | `api/admin.py` → `/settings/available-models` | Filesystem + API model discovery | Existing |
| Data pipeline | `services/data_enrichment_pipeline.py` | Legacy multi-step enrichment (addresses, places, contacts, AI names) | Existing but secondary |
| Nginx config | `nginx/default.conf` | Reverse proxy with endpoint-specific timeouts | Existing, **needs update** |

### Two Pipeline Paths

There are two distinct enrichment paths in the codebase:

**Path 1: Pipeline API (current, primary)**
- Frontend calls `pipelineApi.cleanup/validate/enrich` directly
- Backend `api/pipeline.py` routes to appropriate service
- `cleanup` → `OpenAIProvider.cleanup_entries()` → LM Studio
- `validate` → `validate_address()` → Google Maps
- `enrich` → `enrich_persons()` → PDL/SearchBug
- Returns `PipelineResponse` with `ProposedChange[]`

**Path 2: Streaming enrichment (legacy, still wired)**
- `data_enrichment_pipeline.py` → `enrich_entries()` async generator
- Runs all 5 steps sequentially with NDJSON progress events
- Used by `_validate_names_step()` which calls `provider.cleanup_entries()`
- Not currently called from any active frontend code (replaced by Path 1 in v1.6)

**Recommendation:** Path 1 is the active architecture. Path 2 can be ignored for this milestone.

## Integration Points

### 1. Frontend → FastAPI (HTTP/JSON)

**Endpoint:** `POST /api/pipeline/cleanup`

**Request (PipelineRequest):**
```json
{
  "tool": "extract",
  "entries": [{ "primary_name": "JOHN SMITH", "entity_type": "Individual" }],
  "field_mapping": {},
  "source_data": null
}
```

**Response (PipelineResponse):**
```json
{
  "success": true,
  "proposed_changes": [
    {
      "entry_index": 0,
      "field": "primary_name",
      "current_value": "JOHN SMITH",
      "proposed_value": "John Smith",
      "reason": "Name casing corrected to Title Case",
      "confidence": "high",
      "source": "ai_cleanup",
      "authoritative": false
    }
  ],
  "entries_processed": 25,
  "error": null
}
```

**Frontend timeouts:**
- Cleanup: 300,000ms (5 min)
- Validate: 120,000ms (2 min)
- Enrich: 120,000ms (2 min)

### 2. FastAPI → LM Studio (OpenAI-compatible API)

**Connection:** `AsyncOpenAI(base_url=settings.llm_api_base)` → `http://host.docker.internal:1234/v1`

**Call:** `client.chat.completions.create(model=settings.llm_model, messages=[...], temperature=0.1)`

**SDK timeout:** 300 seconds

**Batching:** Entries split into batches of `settings.batch_size` (default 25). Each batch = one LLM call. Sequential execution with disconnect check between batches.

**Response parsing:** `parse_json_response()` handles three formats:
1. Clean JSON
2. Markdown-fenced JSON (` ```json ... ``` `)
3. Preamble text + embedded `{...}` block

### 3. Docker Container → LM Studio Host

**Network path:** Container uses `host.docker.internal` to reach the host machine's LM Studio on port 1234.

**Linux caveat:** `host.docker.internal` is not natively supported on Linux Docker. Requires `--add-host=host.docker.internal:host-gateway` in the `docker run` command or `extra_hosts` in docker-compose.

**Current docker run command** (from SERVER_SETUP.md):
```bash
sudo docker run -d \
    --name tablerock-tools \
    --env-file /opt/tablerock/.env \
    -p 127.0.0.1:8080:8080 \
    -v /opt/tablerock/data:/app/data \
    tablerock-tools:latest
```

**Missing:** `--add-host=host.docker.internal:host-gateway` flag. This will cause LM Studio connection failures on Linux.

### 4. Admin → LM Studio Model Discovery

**Endpoint:** `GET /api/admin/settings/available-models`

Two-source discovery:
1. **Filesystem scan:** Reads `settings.llm_models_dir` (`/mnt/array/lm-studio/models`), finds `.gguf` files
2. **API query:** `GET http://{llm_api_base}/models` to find loaded models

**Docker volume requirement:** The models directory must be mounted into the container for filesystem discovery:
```bash
-v /mnt/array/lm-studio/models:/mnt/array/lm-studio/models:ro
```

### 5. Nginx → Application

**Current nginx config** (`nginx/default.conf`):
- Has specific locations for `/api/proration/` (300s timeout) and `/api/ghl/send/` (600s, SSE)
- Default `/` location has 120s timeout
- **No pipeline-specific location** for `/api/pipeline/`

## Nginx Configuration Gaps

### Problem: Pipeline requests will timeout

The `/api/pipeline/cleanup` endpoint can take 5+ minutes for large datasets (e.g., 100 entries = 4 batches x 60-90s per batch on a 35B model). The default nginx location has `proxy_read_timeout 120s`, which will kill the connection before the backend finishes.

### Required nginx addition

```nginx
# ── Pipeline AI cleanup (long-running LLM inference) ──
location /api/pipeline/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # LM Studio inference is slow on large models (35B+)
    # 25 entries/batch x ~90s/batch x 4 batches = ~6 minutes worst case
    proxy_read_timeout 600s;
    proxy_connect_timeout 30s;
    proxy_send_timeout 600s;

    # No buffering -- enables disconnect detection
    proxy_buffering off;
    proxy_cache off;
}
```

### Why `proxy_buffering off` matters

The pipeline endpoint uses `request.is_disconnected()` to check if the client has navigated away, then skips remaining batches. With nginx buffering enabled, the backend cannot detect client disconnects because nginx holds the connection open. Disabling buffering allows the TCP RST to propagate.

## Docker Network Configuration

### Current state (broken on Linux)

The `llm_api_base` default is `http://host.docker.internal:1234/v1`. On Linux, `host.docker.internal` is not automatically resolved.

### Fix

Add to the `docker run` command:
```bash
--add-host=host.docker.internal:host-gateway
```

Or in docker-compose.yml:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### Alternative: Use host network mode

For on-prem where the container only talks to localhost services:
```bash
--network host
```
Then `llm_api_base` can be `http://127.0.0.1:1234/v1` directly. Simplifies networking but loses container isolation.

**Recommendation:** Use `--add-host` flag. It is the least invasive change and matches the existing config default.

### LM Studio models directory mount

For the admin model discovery endpoint to scan the filesystem, mount the models directory read-only:
```bash
-v /mnt/array/lm-studio/models:/mnt/array/lm-studio/models:ro
```

## Disconnect Detection Flow

The pipeline implements client disconnect detection to avoid wasting LM Studio compute:

```
Frontend navigates away or aborts
    → Browser closes TCP connection
    → Nginx (with buffering OFF) propagates RST to uvicorn
    → FastAPI sets request._is_disconnected = True
    → pipeline_cleanup() polls via _check_disconnect()
    → OpenAIProvider.cleanup_entries() checks disconnect_check() between batches
    → Skips remaining batches, returns partial results
```

**Requirement:** `proxy_buffering off` in nginx for the pipeline location. Without this, nginx absorbs the disconnect and the backend keeps processing.

## Batch Processing Architecture

The `OperationContext.tsx` provider adds a layer above `useEnrichmentPipeline.ts`:

```
OperationContext.startOperation()
    |
    +-- Snapshot entries for global undo
    +-- Determine enabled steps from feature flags
    +-- For each step (cleanup -> validate -> enrich):
    |   +-- Split entries into batches of batch_size
    |   +-- For each batch:
    |   |   +-- Call pipelineApi.{step}(tool, batchEntries)
    |   |   +-- Auto-apply all returned changes
    |   |   +-- Track enrichment changes for highlights
    |   |   +-- Update progress UI (batch N of M, ETA)
    |   +-- On batch failure: retry once, then skip-and-continue
    |   +-- Mark step completed
    +-- Set pipeline status to 'completed'
```

**Key config values** (from `config.py` / admin settings):
- `batch_size`: 25 entries per API call (default)
- `batch_max_concurrency`: 2 (not used for pipeline -- sequential)
- `batch_max_retries`: 1

## Patterns to Follow

### Pattern 1: Provider Protocol
The `LLMProvider` Protocol in `protocol.py` allows swapping AI backends without changing pipeline code. Any new provider just needs `cleanup_entries()` and `is_available()`.

### Pattern 2: ProposedChange as Universal Currency
All three pipeline steps (cleanup, validate, enrich) return the same `ProposedChange` model. The frontend treats them identically for display, apply/reject, and undo. Do not break this contract.

### Pattern 3: Tool-Specific Prompts
Each tool (extract, title, proration, revenue, ecf) has its own cleanup prompt in `prompts.py`. New tools must add entries to both `CLEANUP_PROMPTS` and `TOOL_PROMPTS` dicts.

### Pattern 4: Disconnect-Aware Batching
The `disconnect_check` callback pattern in `cleanup_entries()` allows graceful cancellation between batches without interrupting an in-flight LLM call. Follow this pattern for any new long-running provider methods.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Streaming LLM responses through nginx
SSE/streaming from the LLM call itself is unnecessary complexity. The current architecture does batch-and-return: one complete HTTP response per pipeline call. Do not try to stream individual LLM tokens through the proxy chain.

### Anti-Pattern 2: Concurrent LLM batches for local inference
The `batch_max_concurrency: 2` setting exists but should stay at 1 for LM Studio cleanup calls. Local inference on a single GPU cannot parallelize -- concurrent requests just queue in LM Studio and increase memory pressure. Sequential batching with disconnect checks is correct.

### Anti-Pattern 3: Long-polling for pipeline progress
The OperationContext batches on the frontend side, making one API call per batch. Each call is a standard request/response. Do not add a polling/SSE mechanism for pipeline progress -- the frontend already manages batch state locally.

## Configuration Reference

| Setting | Env Var | Default | Purpose |
|---------|---------|---------|---------|
| `ai_provider` | `AI_PROVIDER` | `none` | Set to `lmstudio` to enable AI cleanup |
| `llm_api_base` | `LLM_API_BASE` | `http://host.docker.internal:1234/v1` | LM Studio API URL |
| `llm_model` | `LLM_MODEL` | `qwen3.5-35b-a3b` | Model identifier for chat completions |
| `llm_api_key` | `LLM_API_KEY` | `None` | API key (not needed for LM Studio) |
| `llm_models_dir` | `LLM_MODELS_DIR` | `/mnt/array/lm-studio/models` | Filesystem path for model discovery |
| `batch_size` | `BATCH_SIZE` | `25` | Entries per LLM API call |

## Build Order (Dependencies)

1. **Fix Docker networking** -- `--add-host=host.docker.internal:host-gateway` in docker run/systemd unit. Without this, nothing else works.
2. **Add nginx pipeline location** -- `/api/pipeline/` with 600s timeout and `proxy_buffering off`. Without this, large enrichments timeout at 120s.
3. **Mount LM Studio models directory** -- `-v /mnt/array/lm-studio/models:/mnt/array/lm-studio/models:ro` for admin model discovery.
4. **Verify LM Studio connectivity** -- `curl http://host.docker.internal:1234/v1/models` from inside the container.
5. **Test end-to-end** -- Upload a small extract PDF, run cleanup, verify suggestions come back.

Steps 1-3 are all infra/config changes (no code changes). Step 4 is validation. Step 5 is integration testing.

## Sources

- Full codebase analysis: `backend/app/services/llm/`, `backend/app/api/pipeline.py`, `frontend/src/hooks/useEnrichmentPipeline.ts`, `frontend/src/contexts/OperationContext.tsx`
- Nginx config: `nginx/default.conf`
- Server setup docs: `docs/SERVER_SETUP.md`
- Docker config: `docker-compose.yml`, `Dockerfile`
- App config: `backend/app/core/config.py`
