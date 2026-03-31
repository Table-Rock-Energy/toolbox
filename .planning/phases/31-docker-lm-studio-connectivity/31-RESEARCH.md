# Phase 31: Docker + LM Studio Connectivity - Research

**Researched:** 2026-03-31
**Domain:** Docker networking, OpenAI-compatible local LLM integration
**Confidence:** HIGH

## Summary

The backend already has a fully functional LLM provider (`openai_provider.py`) that connects to LM Studio via the OpenAI-compatible API, and the admin settings page already discovers models from both the filesystem and `GET /v1/models`. The `docker-compose.yml` is missing `extra_hosts` configuration, which is the primary blocker -- the container cannot resolve `host.docker.internal` on Linux without it. The config default `llm_api_base` already points to `http://host.docker.internal:1234/v1`.

The two concrete gaps are: (1) add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `backend` service in docker-compose, and (2) add model ID verification against `/v1/models` before making inference calls so the user gets a clear error instead of a cryptic 404 from LM Studio when the model isn't loaded. The admin settings endpoint (`GET /api/admin/settings/available-models`) already queries `/v1/models` -- the verification just needs to happen at inference time too.

**Primary recommendation:** Add `extra_hosts` to docker-compose backend service, add a model verification check to `OpenAIProvider`, and pass `AI_PROVIDER=lmstudio` + `LLM_MODELS_DIR` through docker-compose environment variables.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation choices at Claude's discretion (infrastructure phase).

### Claude's Discretion
All implementation choices. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOCKER-01 | AI enrichment pipeline reaches LM Studio from Docker container via `--add-host=host.docker.internal:host-gateway` | docker-compose `extra_hosts` config + environment variables for AI provider settings |
| DOCKER-02 | Backend verifies model ID against LM Studio's `/v1/models` endpoint before inference calls | New `verify_model()` method on `OpenAIProvider` using existing httpx pattern from admin endpoint |
| DOCKER-03 | User can run full enrichment pipeline (upload -> enrich -> results) end-to-end on server | Requires DOCKER-01 + DOCKER-02 working together; pipeline API (`/api/pipeline/cleanup`) already wired end-to-end |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Use `python3` not `python` on macOS
- Backend patterns: async route handlers, `logger = logging.getLogger(__name__)` per module
- Lazy imports for optional dependencies
- Pydantic Settings with env vars for configuration
- Tests: pytest with async support, httpx for API testing
- Git commits and pushes to main are allowed

## Standard Stack

No new libraries needed. All required dependencies are already installed.

### Core (already in project)
| Library | Purpose | Used By |
|---------|---------|---------|
| openai (AsyncOpenAI) | OpenAI-compatible client for LM Studio | `openai_provider.py` |
| httpx | Async HTTP client for `/v1/models` queries | `admin.py` (already uses for model discovery) |
| pydantic-settings | Config management with env var binding | `config.py` |

## Architecture Patterns

### Current Architecture (already working)

```
Frontend (AdminSettings.tsx)
    |
    v
GET /api/admin/settings/available-models  <-- queries LM Studio /v1/models + filesystem
    |
POST /api/pipeline/cleanup               <-- calls OpenAIProvider.cleanup_entries()
    |
    v
OpenAIProvider._get_client() --> AsyncOpenAI(base_url=settings.llm_api_base)
    |
    v
LM Studio at http://host.docker.internal:1234/v1
```

### What Needs Changing

1. **docker-compose.yml**: Add `extra_hosts` and AI environment variables to `backend` service
2. **openai_provider.py**: Add `verify_model()` method that checks `/v1/models` before first inference
3. **Health check enhancement** (optional): Include LM Studio connectivity in `/api/health` response when AI is enabled

### Pattern: Model Verification Before Inference

The `get_available_models` admin endpoint already has the exact pattern needed:

```python
# From admin.py lines 519-530 -- reuse this pattern
async with httpx.AsyncClient(timeout=10.0) as client:
    response = await client.get(f"{base_url}/models")
    response.raise_for_status()
    data = response.json()
    loaded_ids = {m.get("id", "") for m in data.get("data", [])}
```

Apply this in `OpenAIProvider` as a one-time check before the first inference call. Cache the result so it doesn't add latency to every batch.

### docker-compose.yml Change

```yaml
backend:
  # ... existing config ...
  extra_hosts:
    - "host.docker.internal:host-gateway"
  environment:
    # ... existing vars ...
    - AI_PROVIDER=lmstudio
    - LLM_API_BASE=http://host.docker.internal:1234/v1
    - LLM_MODEL=qwen3.5-35b-a3b
    - LLM_MODELS_DIR=/mnt/array/lm-studio/models
```

### Anti-Patterns to Avoid
- **Do not hardcode the model ID**: It's already configurable via `settings.llm_model` and the admin UI
- **Do not block startup on LM Studio**: LM Studio may not be running when the backend starts. Use lazy verification on first inference call, not on app startup
- **Do not add a new health check dependency**: The Docker HEALTHCHECK should not fail just because LM Studio is offline -- the backend serves many tools that don't need AI

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAI-compatible client | Raw httpx calls for inference | `openai.AsyncOpenAI` | Already in use, handles streaming, retries, auth headers |
| Model discovery | Custom filesystem walker | Existing `get_available_models` admin endpoint | Already handles both filesystem + API merge |
| Docker host networking | Custom DNS resolution | `extra_hosts: host.docker.internal:host-gateway` | Standard Docker Compose mechanism |

## Common Pitfalls

### Pitfall 1: host.docker.internal Not Available on Linux
**What goes wrong:** Container gets `ConnectionRefusedError` or DNS resolution failure when trying to reach LM Studio
**Why it happens:** `host.docker.internal` is only automatically available on Docker Desktop (macOS/Windows). On Linux, it requires explicit `--add-host` or `extra_hosts`
**How to avoid:** Add `extra_hosts: ["host.docker.internal:host-gateway"]` to the backend service in docker-compose.yml
**Warning signs:** `httpx.ConnectError` or `openai.APIConnectionError` in backend logs

### Pitfall 2: Model Not Loaded in LM Studio
**What goes wrong:** LM Studio returns 404 or error when the configured model ID doesn't match any loaded model
**Why it happens:** LM Studio model IDs are based on loaded models, and the user may have configured a model ID that isn't currently loaded
**How to avoid:** Query `GET /v1/models` and verify the configured model exists in the response before making inference calls
**Warning signs:** `404 Not Found` or `model_not_found` errors from the OpenAI client

### Pitfall 3: Environment Variables Not Passed Through docker-compose
**What goes wrong:** Backend container starts with `AI_PROVIDER=none` (the default) even though the host machine has LM Studio running
**Why it happens:** docker-compose environment variables override the Pydantic Settings defaults, but only if explicitly set
**How to avoid:** Add `AI_PROVIDER`, `LLM_API_BASE`, `LLM_MODEL`, and `LLM_MODELS_DIR` to the backend service environment in docker-compose.yml
**Warning signs:** Admin settings shows AI disabled, `/api/pipeline/cleanup` returns "not configured"

### Pitfall 4: Timeout on Large Model Inference
**What goes wrong:** First inference call times out because LM Studio needs to load the model into memory
**Why it happens:** LM Studio lazy-loads models on first request. Large models (35B parameters) can take 30-60 seconds to load
**How to avoid:** The `AsyncOpenAI` client already has `timeout=300.0` (5 minutes). The model verification check should use a shorter timeout (10s) since `/v1/models` is fast
**Warning signs:** `TimeoutError` on the first cleanup request after LM Studio restart

### Pitfall 5: LLM_MODELS_DIR Volume Mount Missing
**What goes wrong:** The `get_available_models` endpoint returns no filesystem models because the container can't see the host's model directory
**Why it happens:** The host's `/mnt/array/lm-studio/models` isn't mounted into the container
**How to avoid:** Add a read-only volume mount for the models directory: `- /mnt/array/lm-studio/models:/mnt/array/lm-studio/models:ro`
**Warning signs:** `models_dir_found: false` in the available-models API response

## Code Examples

### docker-compose.yml backend service additions

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  extra_hosts:
    - "host.docker.internal:host-gateway"
  volumes:
    - ./backend/app:/app/app
    - ./backend/data:/app/data
    - /mnt/array/lm-studio/models:/mnt/array/lm-studio/models:ro
  environment:
    - ENVIRONMENT=development
    - DEBUG=true
    - PORT=8000
    - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/toolbox
    - DATABASE_ENABLED=true
    - AI_PROVIDER=lmstudio
    - LLM_API_BASE=http://host.docker.internal:1234/v1
    - LLM_MODEL=qwen3.5-35b-a3b
    - LLM_MODELS_DIR=/mnt/array/lm-studio/models
```

### Model verification in OpenAIProvider

```python
async def verify_model(self) -> tuple[bool, str]:
    """Check if the configured model is available in LM Studio.

    Returns (is_valid, error_message).
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.llm_api_base}/models")
            response.raise_for_status()
            data = response.json()
            loaded_ids = {m.get("id", "") for m in data.get("data", [])}

            if settings.llm_model in loaded_ids:
                return True, ""

            if loaded_ids:
                return False, (
                    f"Model '{settings.llm_model}' not found in LM Studio. "
                    f"Available: {', '.join(sorted(loaded_ids))}"
                )
            return False, "LM Studio connected but no models loaded."
    except httpx.ConnectError:
        return False, f"Cannot connect to LM Studio at {settings.llm_api_base}"
    except Exception as e:
        return False, f"LM Studio check failed: {e}"
```

### Integration in cleanup_entries (before first batch)

```python
# At the start of cleanup_entries, before the batch loop:
if not hasattr(self, '_model_verified') or not self._model_verified:
    valid, error = await self.verify_model()
    if not valid:
        logger.error("Model verification failed: %s", error)
        return []  # or raise, depending on desired behavior
    self._model_verified = True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gemini cloud API | LM Studio local inference | v2.0 migration | No API costs, no rate limits, privacy |
| `host.docker.internal` auto-available | Requires `extra_hosts` on Linux | Always (Linux-specific) | Must be explicit in docker-compose |

## Open Questions

1. **Should model verification happen on every request or once per session?**
   - What we know: The admin endpoint queries `/v1/models` on every page load. The inference timeout is already 300s.
   - Recommendation: Verify once, cache the result. Re-verify only if an inference call fails with a model-not-found error. This avoids adding 10s latency to every pipeline request.

2. **Should the health check include LM Studio status?**
   - What we know: The Docker HEALTHCHECK uses `/api/health`. Adding LM Studio as a dependency would make the container unhealthy when LM Studio is offline.
   - Recommendation: Add LM Studio status as an informational field in the health response (not as a pass/fail condition). The Docker HEALTHCHECK should remain independent.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (if exists) or `pyproject.toml` |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCKER-01 | extra_hosts config in docker-compose | manual | Verify docker-compose.yml has `extra_hosts` entry | N/A (config file) |
| DOCKER-02 | Model verification before inference | unit | `python3 -m pytest tests/test_llm_protocol.py -x -q` | Exists -- extend |
| DOCKER-03 | Full pipeline works end-to-end | integration/manual | `python3 -m pytest tests/test_pipeline.py -x -q` (unit); manual for true E2E | Exists -- extend |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_llm_protocol.py tests/test_pipeline.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before verify-work

### Wave 0 Gaps
- [ ] `tests/test_llm_protocol.py` -- add test for `verify_model()` method (connected + disconnected + wrong model)
- [ ] `tests/test_pipeline.py` -- add test for cleanup returning error when model verification fails

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `docker-compose.yml`, `backend/app/core/config.py`, `backend/app/services/llm/openai_provider.py`, `backend/app/api/pipeline.py`, `backend/app/api/admin.py`
- Docker Compose `extra_hosts` is a well-documented standard feature

### Secondary (MEDIUM confidence)
- `host.docker.internal:host-gateway` is the standard Linux workaround -- documented in Docker official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all code already exists
- Architecture: HIGH -- changes are minimal (docker-compose config + one new method)
- Pitfalls: HIGH -- well-understood Docker networking issue + LM Studio API behavior confirmed from existing admin endpoint code

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable infrastructure, unlikely to change)
