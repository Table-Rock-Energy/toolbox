# Phase 16: Revenue Multi-PDF Streaming - Research

**Researched:** 2026-03-20
**Domain:** NDJSON streaming for multi-PDF upload progress
**Confidence:** HIGH

## Summary

This phase adds per-file progress streaming to revenue multi-PDF uploads. The backend already processes multiple files sequentially in a loop (line 49 of `revenue.py`), making it straightforward to yield NDJSON progress lines between iterations. The frontend currently restricts to single-file upload (`multiple={false}`) -- this needs changing to `multiple={true}` to enable multi-PDF uploads, alongside adding a ReadableStream consumer for progress updates.

The codebase has established patterns for both SSE streaming (GHL bulk send) and disconnect detection (pipeline.py). This phase uses NDJSON over fetch ReadableStream rather than SSE/EventSource because the upload itself is a POST with FormData -- EventSource only supports GET requests. The NDJSON approach is simpler: stream JSON lines from a FastAPI `StreamingResponse`, read them with `response.body.getReader()` on the frontend.

**Primary recommendation:** Add `POST /api/revenue/upload-stream` returning `StreamingResponse(media_type="application/x-ndjson")`, keep existing upload endpoint unchanged. Frontend switches to streaming endpoint when uploading, shows inline progress counter.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use NDJSON (newline-delimited JSON) streaming response from the upload endpoint
- Backend yields a progress line after each PDF completes: `{"type":"progress","file":"filename.pdf","index":1,"total":5,"status":"done"}`
- Final line contains the full result: `{"type":"result","data":{...full UploadResponse...}}`
- Frontend reads the stream with `response.body.getReader()` and updates progress state per chunk
- Add a new endpoint `POST /api/revenue/upload-stream` that returns `StreamingResponse` with `application/x-ndjson` content type
- Keep existing `POST /api/revenue/upload` unchanged (backward compatibility)
- Process PDFs sequentially (same as now) but yield progress after each file
- If client disconnects mid-stream, stop processing remaining PDFs (check request.is_disconnected between files)
- Revenue page shows a compact progress indicator during upload: "Processing 2 of 5: quarterly_report.pdf"
- Progress updates in-place (not a modal) -- simpler than EnrichmentModal
- On completion, results populate the data table as they do now
- On error for individual PDFs, show error inline and continue with remaining files

### Claude's Discretion
- Whether to use EventSource (SSE) or fetch with ReadableStream (NDJSON) -- recommendation: use fetch + ReadableStream since this is a POST with FormData (EventSource cannot do POST)
- Progress UI placement -- recommendation: below the FileUpload component, above the results table
- Whether to show a file-by-file list or just current/total counter -- recommendation: current/total counter with current filename (compact)
- Error handling granularity in the streaming response -- recommendation: per-file error lines in stream, aggregate in final result

### Deferred Ideas (OUT OF SCOPE)
- Per-PDF cancel/retry in revenue -- explicitly out of scope per REQUIREMENTS.md
- Parallel PDF processing -- not needed, PDFs are typically 2-10 files
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REV-01 | User sees per-PDF progress during multi-PDF revenue upload via SSE | NDJSON streaming endpoint + ReadableStream consumer + inline progress UI. Note: requirement says "SSE" but CONTEXT.md decided NDJSON -- both achieve same UX goal. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI StreamingResponse | 0.x (current) | NDJSON streaming from backend | Built-in, already used in codebase for SSE |
| fetch + ReadableStream | Browser native | Frontend stream consumption | No library needed, native API |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| TextDecoder | Browser native | Decode stream chunks to text | Required for ReadableStream byte processing |

**No new packages required.** Everything needed is already in the project or browser-native.

## Architecture Patterns

### Backend: Streaming Upload Endpoint

**Pattern: Generator + StreamingResponse**

The existing `upload_pdfs` processes files in a `for file in files:` loop. The streaming version wraps the same logic in an `async def generate()` that yields NDJSON lines between iterations.

```python
# Source: FastAPI docs + existing codebase pattern (ghl.py SSE)
from fastapi.responses import StreamingResponse
import json

@router.post("/upload-stream")
async def upload_pdfs_stream(request: Request, files: list[UploadFile] = File(...)):
    total = len(files)

    async def generate():
        statements = []
        errors = []
        total_rows = 0

        for idx, file in enumerate(files):
            # Check disconnect between files
            if await request.is_disconnected():
                break

            # Yield progress: starting this file
            yield json.dumps({
                "type": "progress",
                "file": file.filename,
                "index": idx + 1,
                "total": total,
                "status": "processing"
            }) + "\n"

            # ... process file (same logic as existing upload_pdfs) ...

            # Yield progress: file complete
            yield json.dumps({
                "type": "progress",
                "file": file.filename,
                "index": idx + 1,
                "total": total,
                "status": "done"  # or "error" with error message
            }) + "\n"

        # Yield final result (same shape as UploadResponse)
        result = UploadResponse(...)
        yield json.dumps({
            "type": "result",
            "data": result.model_dump(mode="json")
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

### Frontend: ReadableStream Consumer

**Pattern: getReader() + TextDecoder line splitting**

```typescript
// Read NDJSON stream from fetch response
const response = await fetch(`${API_BASE}/revenue/upload-stream`, {
  method: 'POST',
  headers: authHeaders,
  body: formData,
})

const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break

  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop()! // Keep incomplete line in buffer

  for (const line of lines) {
    if (!line.trim()) continue
    const msg = JSON.parse(line)
    if (msg.type === 'progress') {
      setStreamProgress({ file: msg.file, index: msg.index, total: msg.total, status: msg.status })
    } else if (msg.type === 'result') {
      // Handle final result same as current upload handler
    }
  }
}
```

### Progress UI Component

Inline below the FileUpload area, not a modal:

```
[===================>        ] Processing 3 of 5: quarterly_q3.pdf
```

Simple state: `{ file: string, index: number, total: number, status: string } | null`

### Anti-Patterns to Avoid
- **Using EventSource for POST requests:** EventSource only supports GET. Use fetch + ReadableStream for POST with FormData.
- **Accumulating all chunks before processing:** Process each NDJSON line as it arrives for real-time UI updates.
- **Forgetting buffer management:** Stream chunks may split across JSON lines. Always buffer and split on newlines.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stream reading | Custom WebSocket protocol | fetch + ReadableStream | Browser-native, no server changes needed |
| Progress state management | Global state/context | Local useState in Revenue.tsx | Scoped to upload lifecycle only |
| NDJSON parsing | Custom protocol parser | JSON.parse per line | NDJSON is just JSON + newlines |

**Key insight:** This feature is intentionally simple. No new libraries, no new hooks, no new contexts. It is a streaming fetch with local state.

## Common Pitfalls

### Pitfall 1: Incomplete NDJSON Line Buffering
**What goes wrong:** Stream chunks don't align with JSON line boundaries. A chunk may contain a partial line.
**Why it happens:** TCP/HTTP streaming delivers data in arbitrary chunk sizes.
**How to avoid:** Buffer incoming text, split on `\n`, keep the last segment (potentially incomplete) in the buffer for the next chunk.
**Warning signs:** JSON parse errors on seemingly valid data.

### Pitfall 2: Post-Processing Not Included in Streaming
**What goes wrong:** The current `upload_pdfs` runs `auto_enrich` post-processing after all files are parsed. If the streaming endpoint skips this, results differ from the non-streaming endpoint.
**Why it happens:** Post-processing needs all statements collected before running.
**How to avoid:** Run post-processing after the file loop completes, before yielding the final `result` line. Yield an extra progress line like `{"type":"progress","status":"post-processing"}` during this phase.
**Warning signs:** Streaming results missing `post_process` field.

### Pitfall 3: Frontend FileUpload Multiple Flag
**What goes wrong:** Revenue page currently passes `multiple={false}` to FileUpload. Multi-PDF streaming requires `multiple={true}`.
**Why it happens:** Historical single-file design.
**How to avoid:** Change `multiple={false}` to `multiple={true}` and update `handleFilesSelected` to pass all files (not just `files[0]`).
**Warning signs:** Users can only select one file at a time despite streaming being implemented.

### Pitfall 4: Auth Headers in Streaming Request
**What goes wrong:** The streaming endpoint needs auth headers just like the regular upload.
**Why it happens:** Easy to forget when switching from simple fetch to streaming fetch.
**How to avoid:** Use the same `authHeaders()` helper already in Revenue.tsx.

### Pitfall 5: Error Response When No Files
**What goes wrong:** If 0 valid PDFs are submitted, the generator yields nothing or an empty result.
**How to avoid:** Validate file count upfront before entering the streaming response. Return a normal 400 error for empty uploads -- only use streaming when there are files to process.

## Code Examples

### Backend: Streaming Endpoint Structure

The streaming endpoint should extract the PDF processing logic into a shared function to avoid duplicating the parsing code between `upload_pdfs` and `upload_pdfs_stream`. The processing logic for a single file (lines 50-111 of `revenue.py`) can be factored into a helper:

```python
async def _process_single_pdf(file: UploadFile) -> tuple[RevenueStatement | None, list[str]]:
    """Process a single PDF file. Returns (statement_or_None, errors)."""
    # ... extracted from existing upload_pdfs loop body ...
```

### Frontend: Conditional Streaming

```typescript
// Use streaming endpoint when multiple files, regular endpoint for single file
const useStreaming = files.length > 1
const url = useStreaming
  ? `${API_BASE}/revenue/upload-stream`
  : `${API_BASE}/revenue/upload`
```

This is a reasonable optimization but optional -- the streaming endpoint works fine with 1 file too.

### NDJSON Message Types

```typescript
interface StreamProgress {
  type: 'progress'
  file: string
  index: number
  total: number
  status: 'processing' | 'done' | 'error'
  error?: string  // present when status === 'error'
}

interface StreamResult {
  type: 'result'
  data: UploadResponse
}

type StreamMessage = StreamProgress | StreamResult
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single upload, wait for all | Stream per-file progress | This phase | Users see which file is processing |
| `multiple={false}` single file | `multiple={true}` multi-file | This phase | Users can select multiple PDFs at once |

## Open Questions

1. **Should streaming be used for single-file uploads too?**
   - What we know: Single-file uploads complete fast (2-10 seconds). Streaming adds minimal overhead.
   - Recommendation: Use streaming for all uploads (simplifies code path), but only show progress UI when `total > 1`.

2. **Should `handleFilesSelected` append all files to one FormData or call separately?**
   - What we know: The existing backend endpoint accepts `list[UploadFile]` via a single FormData with multiple `files` entries.
   - Recommendation: Single FormData with all files, matching current backend contract.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + httpx |
| Config file | backend/pytest.ini |
| Quick run command | `cd backend && python3 -m pytest tests/test_revenue_parser.py -x -q` |
| Full suite command | `cd backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REV-01 | Streaming endpoint yields progress + result NDJSON lines | integration | `cd backend && python3 -m pytest tests/test_revenue_streaming.py -x` | No -- Wave 0 |
| REV-01 | Frontend reads stream and updates progress state | manual-only | Manual browser test with multi-PDF upload | N/A |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_revenue_streaming.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_revenue_streaming.py` -- covers REV-01 backend streaming
- [ ] Test should verify: NDJSON line format, progress count accuracy, final result shape, error handling per file

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/app/api/revenue.py` -- existing upload endpoint with sequential file processing
- Codebase: `backend/app/api/ghl.py` -- existing SSE streaming pattern with disconnect detection
- Codebase: `backend/app/api/pipeline.py` -- existing `request.is_disconnected()` pattern
- Codebase: `frontend/src/pages/Revenue.tsx` -- current upload handler and UI structure
- Codebase: `frontend/src/hooks/useSSEProgress.ts` -- existing SSE hook (different pattern, reference only)
- FastAPI StreamingResponse documentation -- async generator yielding bytes/strings

### Secondary (MEDIUM confidence)
- NDJSON streaming pattern is well-established (used by Docker, ndjson.org spec)
- ReadableStream API is supported in all modern browsers

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all browser-native + FastAPI built-in
- Architecture: HIGH -- straightforward adaptation of existing patterns already in codebase
- Pitfalls: HIGH -- identified from direct code inspection of current upload flow

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable -- no external dependencies changing)
