# Domain Pitfalls

**Domain:** On-prem Docker deployment with local LLM inference and nginx reverse proxy
**Researched:** 2026-03-31
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: `host.docker.internal` Does Not Resolve on Linux Docker

**What goes wrong:** The `openai_provider.py` connects to `http://host.docker.internal:1234/v1`. On Docker Desktop (Mac/Windows), this hostname resolves automatically to the host machine. On Linux Docker Engine (which the Ubuntu server uses), it does NOT resolve -- connection attempts fail with DNS resolution errors.

**Why it happens:** Docker Desktop includes a built-in DNS resolver that maps `host.docker.internal` to the host IP. Linux Docker Engine lacks this. It was added as an opt-in feature requiring `--add-host=host.docker.internal:host-gateway`.

**Consequences:** All AI enrichment calls fail silently. The `openai_provider.py` catches exceptions and logs them, but the pipeline returns empty suggestions -- making it look like the AI "found nothing" rather than "couldn't connect."

**Prevention:** Add `--add-host=host.docker.internal:host-gateway` to the production `docker run` command. Also applies to PostgreSQL if `DATABASE_URL` uses `host.docker.internal`.

**Detection:** `docker exec tablerock-tools curl http://host.docker.internal:1234/v1/models` -- if this fails, the flag is missing.

### Pitfall 2: LM Studio Model ID Mismatch

**What goes wrong:** The `llm_model` config is set to `qwen3.5-35b-a3b` but LM Studio's `/v1/models` endpoint may return the model ID with a different format (e.g., `lmstudio-community/qwen3.5-35b-a3b-GGUF` or including quantization info like `Q4_K_M`).

**Why it happens:** LM Studio model IDs are derived from the Hugging Face repo path + filename. The config value was likely set manually without checking the actual model ID.

**Consequences:** OpenAI SDK sends the wrong model name. LM Studio may: (a) return a 404/error, (b) silently use whatever model is loaded, or (c) return an empty response. Behavior depends on LM Studio version.

**Prevention:** Query `GET /v1/models` on the running LM Studio instance and use the exact `id` field value in the config.

**Detection:** Check `docker logs tablerock-tools` for "LLM cleanup error" or "LLM validation error" messages from `openai_provider.py`.

### Pitfall 3: Nginx Timeout on AI Pipeline Requests

**What goes wrong:** The default nginx location block has a 120s `proxy_read_timeout`. Local inference on a 35B parameter model can take 60-120+ seconds per batch. With multiple batches in a single pipeline request, total time easily exceeds 120s.

**Why it happens:** The nginx config was written for Cloud Run (Gemini API responses were fast). Local inference is orders of magnitude slower.

**Consequences:** User sees 504 Gateway Timeout. Backend continues processing (wasting GPU cycles) but the response is lost. Frontend shows a generic error.

**Prevention:** Add a dedicated `/api/pipeline/` location block with 600s timeout and disabled buffering.

**Detection:** `502` or `504` errors in nginx error log during enrichment operations.

## Moderate Pitfalls

### Pitfall 4: Nginx Buffers NDJSON Streaming Responses

**What goes wrong:** Revenue multi-PDF upload uses NDJSON streaming (one JSON line per file processed). Nginx's default response buffering collects the entire response before forwarding, defeating the purpose of streaming.

**Prevention:** Add `proxy_buffering off; proxy_cache off;` to the `/api/revenue/` location block. FastAPI also sends `X-Accel-Buffering: no` header but explicit nginx config is more reliable.

### Pitfall 5: PostgreSQL Connection from Docker Uses Same Hostname

**What goes wrong:** If `DATABASE_URL` contains `host.docker.internal`, it has the same resolution problem as LM Studio. If it contains `localhost`, the container can't reach the host's PostgreSQL.

**Prevention:** Same fix as Pitfall 1 (`--add-host` flag). Verify `DATABASE_URL` in `/opt/tablerock/.env` uses `host.docker.internal` consistently.

### Pitfall 6: LM Studio Not Running After Server Reboot

**What goes wrong:** LM Studio is a desktop application. If the server reboots, LM Studio doesn't auto-start. AI enrichment silently fails.

**Prevention:** Either (a) configure LM Studio to auto-start via systemd user service or desktop autostart, or (b) document manual restart procedure and add LM Studio status to the health check endpoint.

**Detection:** `curl http://localhost:1234/v1/models` returns connection refused.

## Minor Pitfalls

### Pitfall 7: JSON Parsing Fragility with Local Models

**What goes wrong:** Local models (especially smaller quantizations) sometimes return malformed JSON -- extra text before/after the JSON block, incomplete closing braces, or markdown formatting around JSON.

**Prevention:** The existing `parse_json_response()` in `openai_provider.py` already handles three common patterns (clean JSON, markdown-fenced, brace extraction). This is well-designed. Monitor logs for "Could not extract JSON from LLM response" errors to detect new failure patterns.

### Pitfall 8: Batch Size Too Large for Model Context Window

**What goes wrong:** The default batch size is 25 entries. If entries have long text fields, the prompt can exceed the model's context window, causing truncated or nonsensical responses.

**Prevention:** The batch size is configurable via admin settings. If quality degrades, reduce `BATCH_SIZE` to 10-15. The qwen3.5-35b model should handle 25 entries comfortably with its 32K+ context window.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Docker + LM Studio connectivity | Pitfall 1 + 2 | `--add-host` flag + model ID verification |
| Nginx configuration | Pitfall 3 + 4 | Pipeline location block + buffering off |
| Bug fix consolidation | None | Bookkeeping only |

## Sources

- [Docker host.docker.internal documentation](https://docs.docker.com/reference/cli/docker/container/run/#add-host) -- `--add-host` flag behavior on Linux
- [LM Studio OpenAI Compatibility](https://lmstudio.ai/docs/developer/openai-compat) -- model ID format requirements
- [Nginx proxy_buffering directive](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering) -- buffering behavior
