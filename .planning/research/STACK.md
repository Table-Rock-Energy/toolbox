# Technology Stack

**Project:** Table Rock Tools v2.2 - Post-Migration Fixes & AI Enrichment
**Researched:** 2026-03-31
**Scope:** LM Studio debugging, nginx reverse proxy, on-prem Docker stabilization

## What's Already In Place (DO NOT CHANGE)

These are validated and working. Listed for reference only.

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.x | SPA frontend |
| FastAPI | 0.109+ | Async Python API |
| PostgreSQL | 16 | Primary database (migrated from Firestore in v2.0) |
| SQLAlchemy | 2.0+ | Async ORM |
| Alembic | 1.13+ | Schema migrations |
| PyJWT | 2.8+ | Local JWT auth (replaced Firebase in v2.0) |
| pwdlib[bcrypt] | 0.2+ | Password hashing |
| openai SDK | 2.0+ | LM Studio client via OpenAI-compatible API |
| Docker | latest | Production container runtime |
| nginx | system | Reverse proxy + SSL termination |

## Stack Additions Needed

### None.

No new libraries or dependencies are required for v2.2. The existing stack covers everything. The work is debugging and configuration, not adding technology.

## Configuration Changes Required

### 1. LM Studio OpenAI-Compatible API

**Current config** (in `config.py`):
```python
ai_provider: str = "none"
llm_api_base: str = "http://host.docker.internal:1234/v1"
llm_model: str = "qwen3.5-35b-a3b"
llm_api_key: Optional[str] = None
llm_models_dir: str = "/mnt/array/lm-studio/models"
```

**Key facts** (HIGH confidence, verified via LM Studio docs):
- LM Studio 0.4.x serves OpenAI-compatible endpoints at `/v1/chat/completions`, `/v1/models`, `/v1/completions`, `/v1/embeddings`
- The `model` field in API requests must match the exact model ID returned by `GET /v1/models` -- this includes quantization suffixes (e.g., `qwen3.5-35b-a3b` might need to be `lmstudio-community/qwen3.5-35b-a3b-GGUF`)
- API key is ignored on localhost but the openai SDK requires a non-empty string -- current `"not-needed"` fallback is correct
- Streaming is fully supported with SSE
- No rate limiting on local inference -- the existing `asyncio.Semaphore` concurrency control in the pipeline is sufficient

**Debugging checklist for AI enrichment on server:**
1. Verify `AI_PROVIDER=lmstudio` is set in production `.env`
2. Verify `LLM_API_BASE` resolves from inside Docker container (`host.docker.internal` works on Docker Desktop but requires `--add-host=host.docker.internal:host-gateway` on Linux Docker)
3. Verify model ID matches `GET /v1/models` output exactly
4. Verify LM Studio server is running and listening on port 1234
5. Test connectivity: `curl http://host.docker.internal:1234/v1/models` from inside container

**Critical Linux Docker gotcha:** `host.docker.internal` does NOT resolve by default on Linux. Docker Desktop (Mac/Windows) adds it automatically, but on Ubuntu server you must add `--add-host=host.docker.internal:host-gateway` to the `docker run` command or add `extra_hosts` in docker-compose. This is the most likely reason AI enrichment fails on the server.

### 2. Nginx Reverse Proxy for FastAPI

**Current config** (`nginx/default.conf`) has three location blocks:
- `/api/proration/` -- 300s timeout, buffering off (for RRC streaming)
- `/api/ghl/send/` -- 600s timeout, buffering off (for SSE progress)
- `/` -- 120s timeout, default buffering (catch-all)

**Missing: Pipeline/enrichment endpoints.** The AI enrichment pipeline (`/api/pipeline/*`) makes LM Studio calls that can take 30-60+ seconds per batch (local inference on 35B parameter models is slow). The default 120s timeout may be tight for multi-batch operations, and buffering will delay NDJSON streaming responses.

**Required nginx additions:**

```nginx
# AI pipeline endpoints (long-running LM Studio inference)
location /api/pipeline/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # LM Studio inference is slow on large models -- 10 min timeout
    proxy_read_timeout 600s;
    proxy_connect_timeout 60s;
    proxy_send_timeout 600s;

    # Disable buffering for streaming responses
    proxy_buffering off;
    proxy_cache off;
}

# Revenue upload (multi-PDF NDJSON streaming)
location /api/revenue/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_buffering off;
    proxy_cache off;
}
```

**SSE-specific note** (MEDIUM confidence): FastAPI's SSE implementation (via `sse-starlette`) already sends `X-Accel-Buffering: no` header which tells nginx to disable response buffering for that request. However, the `proxy_buffering off` directive in the location block is belt-and-suspenders -- it ensures buffering is disabled even if the header is missed. Keep both.

**Connection header for SSE:** Add `proxy_set_header Connection '';` to SSE location blocks. HTTP/1.1 keepalive requires clearing the Connection header to prevent nginx from closing the connection prematurely.

### 3. Docker Production Configuration for On-Prem

**Current Dockerfile** is fine. The key issues are runtime configuration:

| Setting | Current | Required for On-Prem |
|---------|---------|---------------------|
| `--add-host` | Not set | `host.docker.internal:host-gateway` (Linux) |
| `DATABASE_URL` | localhost | `postgresql+asyncpg://user:pass@host.docker.internal:5432/toolbox` or host network |
| `AI_PROVIDER` | `none` | `lmstudio` |
| `LLM_API_BASE` | `host.docker.internal:1234/v1` | Correct if `--add-host` is set |

**PostgreSQL access from Docker:** Two approaches:
1. **`--add-host` + `host.docker.internal`** -- container talks to host's PostgreSQL via special hostname
2. **`--network=host`** -- container shares host network stack, `localhost` works directly. Simpler but gives container full network access.

Recommendation: Use `--add-host=host.docker.internal:host-gateway` for both PostgreSQL and LM Studio access. It's explicit and doesn't open the entire host network.

**Updated `docker run` for production:**
```bash
sudo docker run -d \
    --name tablerock-tools \
    --restart unless-stopped \
    --env-file /opt/tablerock/.env \
    --add-host=host.docker.internal:host-gateway \
    -p 127.0.0.1:8080:8080 \
    -v /opt/tablerock/data:/app/data \
    tablerock-tools:latest
```

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| Ollama | LM Studio is already integrated and working. No reason to switch inference servers. |
| vLLM | Production-grade but overkill for a single-user internal tool. LM Studio's GUI model management is a feature here. |
| Redis | No caching layer needed. In-memory pandas cache + PostgreSQL is sufficient for this user count. |
| Celery / task queue | The pipeline already handles batch processing with asyncio. Background thread pattern works for RRC downloads. |
| Prometheus / Grafana | Over-engineered for a small internal team. The healthcheck.sh + docker logs pattern is adequate. |
| Traefik / Caddy | nginx is already configured and working. No reason to switch reverse proxies. |
| pgBouncer | Single-digit concurrent users. Connection pooling is unnecessary. |

## Version Pinning Notes

| Package | Current Pin | Recommendation |
|---------|-------------|----------------|
| `openai` | `>=2.0.0` | Keep loose. The SDK is stable for basic chat completions. LM Studio compatibility doesn't depend on specific minor versions. |
| `nginx` | system package | Use Ubuntu's default `apt` package. No need for nginx-plus or custom builds. |
| `PostgreSQL` | 16-alpine (Docker) | Keep. No features from PG 17 are needed. |

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| LM Studio API compat | HIGH | Verified via official LM Studio docs -- standard OpenAI SDK works with base_url swap |
| `host.docker.internal` Linux issue | HIGH | Well-documented Docker limitation on Linux vs Desktop, confirmed in Docker docs |
| nginx SSE buffering | HIGH | Multiple sources confirm `proxy_buffering off` + `X-Accel-Buffering: no` pattern |
| Pipeline timeout needs | MEDIUM | 600s is estimated from 35B model inference times -- may need tuning based on actual server GPU |
| No new dependencies needed | HIGH | Codebase review confirms all required libraries are present |

## Sources

- [LM Studio OpenAI Compatibility Docs](https://lmstudio.ai/docs/developer/openai-compat) -- endpoint list, model ID format, streaming support
- [LM Studio Developer Docs](https://lmstudio.ai/docs/developer) -- native API vs compat layer
- [FastAPI SSE Tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) -- X-Accel-Buffering header behavior
- [Nginx SSE Configuration Guide](https://oneuptime.com/blog/post/2025-12-16-server-sent-events-nginx/view) -- proxy_buffering, timeout settings
- [Nginx Reverse Proxy Guide (2026)](https://eastondev.com/blog/en/posts/dev/20260330-nginx-reverse-proxy-guide/) -- upstream buffering patterns
