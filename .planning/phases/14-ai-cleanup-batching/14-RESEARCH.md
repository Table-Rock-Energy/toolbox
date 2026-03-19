# Phase 14: AI Cleanup Batching - Research

**Researched:** 2026-03-19
**Domain:** Configurable batch processing, concurrency, retry, and backend disconnect detection
**Confidence:** HIGH

## Summary

This phase extends the existing batch pipeline engine (OperationContext + pipeline API + GeminiProvider) with four capabilities: configurable batch size via admin settings, concurrent batch execution, automatic retry of failed batches, and backend disconnect detection. All four touch surfaces are well-understood from the Phase 13 implementation.

The codebase already has every integration point needed. The frontend `OperationContext.tsx` has a hardcoded `BATCH_SIZE = 25` that becomes dynamic. The backend `gemini_service.py` has `BATCH_SIZE = 25` and `BATCH_DELAY_SECONDS = 6` that become configurable. The admin settings flow (`load_app_settings` / `save_app_settings` / `_apply_settings_to_runtime`) provides the persistence pattern. FastAPI's `Request.is_disconnected()` provides the disconnect detection primitive.

**Primary recommendation:** Keep changes surgical. The batch engine logic in OperationContext stays client-side. Concurrency is added via `asyncio.Semaphore` on the backend (GeminiProvider) with a configurable concurrency limit. Retry is a single end-of-step pass in OperationContext. Disconnect detection is a `request: Request` parameter added to pipeline endpoints.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single global batch size (all tools use same value) -- no per-tool override
- Config lives under existing Google Cloud section in admin UI as "AI Cleanup" subsection
- Stored in `batch_config` key in existing app_settings.json
- Frontend fetches batch size from `/api/admin/settings` response; falls back to 25 if not configured
- 2 concurrent batches (configurable alongside batch size)
- Retry failed batches once at end of step (collect failures, re-run after all batches complete)
- `max_retries` stored in same `batch_config` in app_settings (default: 1)
- After retry exhausted, return partial results with count of still-failed entries
- Check `request.is_disconnected()` between internal Gemini batches in `/api/pipeline/cleanup`
- Add `request: Request` parameter to pipeline endpoints
- On disconnect: log warning + return early with partial results
- Granularity: check before each internal Gemini batch call

### Claude's Discretion
- Concurrency implementation details (asyncio.Semaphore vs Promise.allSettled on frontend)
- Whether concurrency is frontend-side (parallel fetch calls) or backend-side (parallel Gemini calls) or both
- Retry batch collection data structure and re-dispatch mechanism
- Admin UI layout for batch config controls (slider vs number input)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BATCH-03 | User can configure batch size per tool via admin settings | Admin settings flow (`load_app_settings`/`save_app_settings`/`_apply_settings_to_runtime`), `batch_config` key in app_settings.json, AdminSettings.tsx Google Cloud card |
| BATCH-04 | System runs multiple batches concurrently when Gemini rate limits allow | `asyncio.Semaphore` in GeminiProvider, rate limit check (`_check_rate_limit`), `MAX_RPM=10` constraint |
| RESIL-02 | Backend stops Gemini processing when client disconnects | FastAPI `Request.is_disconnected()`, pipeline.py cleanup endpoint |
| RESIL-04 | System automatically retries failed batches up to configurable limit | OperationContext catch block already tracks `failedBatches`, retry pass at end-of-step |
</phase_requirements>

## Standard Stack

No new libraries needed. This phase modifies existing code only.

### Core (already in project)
| Library | Version | Purpose | Role in Phase |
|---------|---------|---------|---------------|
| FastAPI | 0.x | Backend API | `Request.is_disconnected()` for disconnect detection |
| React | 19.x | Frontend SPA | OperationContext modifications for retry + dynamic batch size |
| google-genai | 2.x | Gemini API | Already used via GeminiProvider |

### No New Dependencies
This phase requires zero new packages. All capabilities come from existing FastAPI primitives (`Request.is_disconnected()`), Python stdlib (`asyncio.Semaphore`), and React patterns already in the codebase.

## Architecture Patterns

### Pattern 1: Dynamic Batch Config via App Settings
**What:** Add `batch_config` section to `app_settings.json` with `batch_size`, `max_concurrency`, and `max_retries` fields. Backend reads these at request time; frontend fetches them from the admin settings API.

**Flow:**
1. Admin sets values in AdminSettings UI -> PUT `/api/admin/settings/google-cloud` (extended)
2. `save_app_settings()` persists to `app_settings.json` + Firestore
3. `_apply_settings_to_runtime()` updates runtime `settings` object
4. GeminiProvider reads `batch_size` and `max_concurrency` from runtime settings
5. Frontend fetches settings on mount, passes `batchSize` to OperationContext

**Backend storage shape:**
```json
{
  "google_cloud": { ... },
  "batch_config": {
    "batch_size": 25,
    "max_concurrency": 2,
    "max_retries": 1
  }
}
```

**Runtime injection in `_apply_settings_to_runtime`:**
```python
bc = settings_data.get("batch_config", {})
if "batch_size" in bc:
    runtime_settings.batch_size = bc["batch_size"]
if "max_concurrency" in bc:
    runtime_settings.batch_max_concurrency = bc["max_concurrency"]
if "max_retries" in bc:
    runtime_settings.batch_max_retries = bc["max_retries"]
```

### Pattern 2: Backend Concurrency via asyncio.Semaphore
**What:** GeminiProvider.cleanup_entries currently processes batches sequentially. Add `asyncio.Semaphore(max_concurrency)` and `asyncio.gather()` to run N batches concurrently while respecting rate limits.

**Recommendation: Backend-side concurrency (not frontend-side).** Reasons:
- The frontend already sends one batch of entries per API call. Making the frontend send multiple parallel requests would require changing the OperationContext batch loop significantly.
- The backend GeminiProvider already has an internal batch loop (line 129 of `gemini_provider.py`). Adding concurrency here is simpler -- the semaphore controls how many `asyncio.to_thread` calls run simultaneously.
- Rate limiting is already server-side (`_check_rate_limit`). Keeping concurrency server-side means rate limiting stays coherent.

**Key constraint:** With `MAX_RPM=10` and `BATCH_DELAY_SECONDS=6`, sequential batches process ~10 per minute. With 2 concurrent batches, we can process 2 every 6 seconds = 20/min, but we must respect the 10 RPM limit. So the semaphore + rate limit check work together: the semaphore allows 2 in-flight, but `_check_rate_limit()` gates actual API calls.

**Example:**
```python
async def cleanup_entries(self, tool, entries, *, source_data=None):
    from app.services.gemini_service import _get_client, BATCH_DELAY_SECONDS
    from app.core.config import settings as runtime_settings

    batch_size = getattr(runtime_settings, 'batch_size', 25)
    max_concurrency = getattr(runtime_settings, 'batch_max_concurrency', 2)

    client = _get_client()
    total_batches = (len(entries) + batch_size - 1) // batch_size
    semaphore = asyncio.Semaphore(max_concurrency)

    async def process_batch(batch_idx):
        async with semaphore:
            start = batch_idx * batch_size
            batch = entries[start:start + batch_size]
            return await asyncio.to_thread(
                _cleanup_batch_sync, client, tool, batch, start, source_data
            )

    tasks = [process_batch(i) for i in range(total_batches)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... collect suggestions, handle exceptions ...
```

**Important nuance:** The current `_cleanup_batch_sync` calls `_check_rate_limit()` and `_record_request()` which use module-level lists/counters. These are not thread-safe with concurrent `asyncio.to_thread` calls. Need to add a `threading.Lock` around rate-limit state, or serialize the rate-limit check via an asyncio lock before dispatching to thread.

### Pattern 3: End-of-Step Retry in OperationContext
**What:** After all batches for a step complete, collect failed batch indices. If `failedBatches > 0` and retries remain, re-run just the failed batches.

**Data structure:** Track failed batch ranges as `{startIndex, endIndex}[]` alongside the batch loop. After the step's main loop, if failures exist and retry count allows, loop through failed ranges only.

```typescript
// After main batch loop for a step
if (failedBatchRanges.length > 0 && retriesRemaining > 0) {
  retriesRemaining--
  for (const range of failedBatchRanges) {
    // Re-attempt the failed batch
    const batch = currentEntries.slice(range.start, range.end)
    try {
      const response = await apiMethod(tool, batch, ...)
      // Apply changes...
      retrySuccesses++
    } catch {
      stillFailedBatches++
    }
  }
}
```

### Pattern 4: Backend Disconnect Detection
**What:** Add `request: Request` parameter to `pipeline_cleanup` (and optionally validate/enrich). Pass it through to GeminiProvider so it can check `await request.is_disconnected()` between batches.

**Key detail:** `request.is_disconnected()` is a sync method in FastAPI/Starlette (returns `bool`), not async. It checks if the underlying ASGI connection has been closed. Must be checked on the main asyncio thread, not inside `asyncio.to_thread`.

```python
@router.post("/cleanup", response_model=PipelineResponse)
async def pipeline_cleanup(request: Request, body: PipelineRequest) -> PipelineResponse:
    # ... setup ...
    changes = await provider.cleanup_entries(
        body.tool, body.entries,
        source_data=body.source_data,
        disconnect_check=lambda: request.is_disconnected(),
    )
```

In GeminiProvider, check between batches:
```python
for batch_idx in range(total_batches):
    if disconnect_check and await asyncio.to_thread(disconnect_check):
        logger.warning("Client disconnected, stopping cleanup")
        break
    # ... process batch ...
```

**Correction:** `request.is_disconnected()` is actually sync in Starlette but needs the event loop. The cleanest approach: check it in the async context before dispatching each batch to a thread.

### Anti-Patterns to Avoid
- **Frontend-side concurrency for Gemini calls:** Don't use `Promise.allSettled` to fire multiple `/pipeline/cleanup` requests. Each request goes through the full Gemini batch loop already. Parallel API requests would double-count rate limits and create race conditions in the module-level RPM tracking.
- **Retry inside the batch loop:** Don't retry immediately on failure. The CONTEXT.md specifies end-of-step retry to avoid mid-stream complexity.
- **Shared mutable state without locks:** The `_rpm_timestamps` list and `_daily_count` in `gemini_service.py` are not thread-safe. With concurrency, add protection.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrency limiting | Custom counter/queue | `asyncio.Semaphore` | Battle-tested, handles edge cases |
| Rate limit coordination | Custom token bucket | Extend existing `_check_rate_limit` with threading.Lock | Already works, just needs thread safety |
| Disconnect detection | Polling/heartbeat | `Request.is_disconnected()` | Built into FastAPI/Starlette |
| Settings persistence | New config system | Existing `app_settings.json` + Firestore flow | Already handles encryption, sync, runtime injection |

## Common Pitfalls

### Pitfall 1: Thread Safety of Rate Limit State
**What goes wrong:** `_rpm_timestamps` and `_daily_count` in `gemini_service.py` are module-level variables accessed from `asyncio.to_thread`. With concurrent batches, two threads may read/write simultaneously.
**Why it happens:** `asyncio.to_thread` runs in a real thread pool. Module globals are shared.
**How to avoid:** Add `threading.Lock` around `_check_rate_limit()` and `_record_request()`.
**Warning signs:** Intermittent rate limit errors, RPM count exceeding MAX_RPM.

### Pitfall 2: Request Parameter Conflicts with Pydantic Model
**What goes wrong:** Adding `request: Request` to a FastAPI endpoint that already takes a Pydantic body model requires careful parameter naming.
**Why it happens:** FastAPI resolves parameters by type annotation. If the body parameter is named `request`, it conflicts with `starlette.requests.Request`.
**How to avoid:** Name the body parameter differently: `async def pipeline_cleanup(request: Request, body: PipelineRequest)`.

### Pitfall 3: Stale Batch Size on Frontend
**What goes wrong:** If admin changes batch size while an operation is running, the running operation uses the old value.
**How to avoid:** Read batch size once at operation start (already natural since `startOperation` captures config). Don't re-read mid-operation.

### Pitfall 4: Disconnect Check Blocking
**What goes wrong:** `request.is_disconnected()` must be called from the async context, not from within `asyncio.to_thread`.
**How to avoid:** Check disconnect before dispatching each batch to a thread, not inside the sync batch function.

### Pitfall 5: Over-Aggressive Concurrency Exceeding RPM
**What goes wrong:** With 2 concurrent batches and no delay, requests fire faster than 10 RPM.
**How to avoid:** Keep `BATCH_DELAY_SECONDS` between concurrent groups, or rely on `_check_rate_limit()` to gate. The semaphore limits in-flight requests, but the rate limiter must also enforce timing.

## Code Examples

### Adding batch_config to admin settings backend
```python
# In admin.py _apply_settings_to_runtime()
bc = settings_data.get("batch_config", {})
if "batch_size" in bc:
    runtime_settings.batch_size = max(5, min(100, bc["batch_size"]))
if "max_concurrency" in bc:
    runtime_settings.batch_max_concurrency = max(1, min(5, bc["max_concurrency"]))
if "max_retries" in bc:
    runtime_settings.batch_max_retries = max(0, min(3, bc["max_retries"]))
```

### Adding settings fields to config.py
```python
# In core/config.py Settings class
batch_size: int = 25
batch_max_concurrency: int = 2
batch_max_retries: int = 1
```

### Frontend fetching batch config
```typescript
// In OperationContext or a hook
const [batchConfig, setBatchConfig] = useState({ batchSize: 25, maxRetries: 1 })

useEffect(() => {
  fetch(`${API_BASE}/admin/settings/google-cloud`, { headers })
    .then(r => r.json())
    .then(data => {
      if (data.batch_config) {
        setBatchConfig({
          batchSize: data.batch_config.batch_size ?? 25,
          maxRetries: data.batch_config.max_retries ?? 1,
        })
      }
    })
    .catch(() => {}) // Falls back to defaults
}, [])
```

### Thread-safe rate limiting
```python
import threading

_rate_lock = threading.Lock()

def _check_rate_limit() -> tuple[bool, int, int]:
    with _rate_lock:
        # ... existing logic ...

def _record_request() -> None:
    with _rate_lock:
        # ... existing logic ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded BATCH_SIZE=25 | Dynamic from admin settings | Phase 14 | Admin can tune for their Gemini tier |
| Sequential batch execution | Concurrent with semaphore | Phase 14 | ~2x throughput for large datasets |
| Silent batch failure | Retry once + report partial | Phase 14 | Better success rate, transparent failures |
| No disconnect awareness | Backend checks between batches | Phase 14 | Saves Gemini API calls on cancel |

## Open Questions

1. **Should the settings endpoint be extended or a new endpoint added?**
   - What we know: CONTEXT.md says "under existing Google Cloud section" and "fetches from `/api/admin/settings`"
   - Recommendation: Extend `GET /api/admin/settings/google-cloud` response to include `batch_config`. This keeps the admin UI fetch simple (one call).

2. **Should validate and enrich endpoints also get disconnect detection?**
   - What we know: CONTEXT.md specifically mentions `/api/pipeline/cleanup`. Validate uses Google Maps (fast, cheap). Enrich uses PDL/SearchBug.
   - Recommendation: Add `request: Request` to all three for consistency, but only actively check disconnect in cleanup (the expensive Gemini path).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py -x -v` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BATCH-03 | Batch config loaded from settings, falls back to defaults | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::TestBatchConfig -x` | Wave 0 |
| BATCH-04 | Concurrent batches execute via semaphore | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::TestBatchConcurrency -x` | Wave 0 |
| RESIL-02 | Disconnect stops processing | unit | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py::TestDisconnectDetection -x` | Wave 0 |
| RESIL-04 | Failed batches retried once | unit (frontend logic, manual verify) | manual-only | N/A -- frontend OperationContext logic |

### Sampling Rate
- **Per task commit:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_pipeline.py -x -v`
- **Per wave merge:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline.py::TestBatchConfig` -- test batch_config loading + defaults
- [ ] `tests/test_pipeline.py::TestBatchConcurrency` -- test semaphore concurrency in GeminiProvider
- [ ] `tests/test_pipeline.py::TestDisconnectDetection` -- test request.is_disconnected() stops processing

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `OperationContext.tsx`, `gemini_provider.py`, `gemini_service.py`, `pipeline.py`, `admin.py`, `AdminSettings.tsx`
- FastAPI documentation: `Request.is_disconnected()` is a Starlette primitive, synchronous method
- Python stdlib: `asyncio.Semaphore`, `threading.Lock`

### Secondary (MEDIUM confidence)
- Gemini free tier rate limits: 10 RPM, 250 RPD (from existing constants in `gemini_service.py`)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing code
- Architecture: HIGH -- patterns directly extend existing code with minimal structural change
- Pitfalls: HIGH -- identified from direct code inspection of thread safety and FastAPI parameter resolution

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain, no external dependency changes)
