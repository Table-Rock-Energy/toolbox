# Phase 16: Revenue Multi-PDF Streaming - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Revenue multi-PDF uploads stream per-file progress to the frontend so users see which PDF is being processed and how many remain, instead of a blocking spinner with no feedback.

Requirements: REV-01

</domain>

<decisions>
## Implementation Decisions

### Streaming Strategy
- Use NDJSON (newline-delimited JSON) streaming response from the upload endpoint — already proven in the codebase (GHL bulk send uses SSE)
- Backend yields a progress line after each PDF completes: `{"type":"progress","file":"filename.pdf","index":1,"total":5,"status":"done"}`
- Final line contains the full result: `{"type":"result","data":{...full UploadResponse...}}`
- Frontend reads the stream with `response.body.getReader()` and updates progress state per chunk

### Backend Changes
- Add a new endpoint `POST /api/revenue/upload-stream` that returns `StreamingResponse` with `application/x-ndjson` content type
- Keep existing `POST /api/revenue/upload` unchanged (backward compatibility)
- Process PDFs sequentially (same as now) but yield progress after each file
- If client disconnects mid-stream, stop processing remaining PDFs (check request.is_disconnected between files)

### Frontend Progress UI
- Revenue page shows a compact progress indicator during upload: "Processing 2 of 5: quarterly_report.pdf"
- Progress updates in-place (not a modal) — simpler than EnrichmentModal since this is upload, not enrichment
- On completion, results populate the data table as they do now
- On error for individual PDFs, show error inline and continue with remaining files (same as current behavior)

### Claude's Discretion
- Whether to use `EventSource` (SSE) or `fetch` with `ReadableStream` (NDJSON) — both work, pick whichever fits cleanly
- Progress UI placement (above table, in upload card, etc.)
- Whether to show a file-by-file list or just current/total counter
- Error handling granularity in the streaming response

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `revenue.py` api endpoint — `upload_pdfs()` already processes files in a loop, easy to yield progress between iterations
- `StreamingResponse` from FastAPI — used in GHL bulk send for SSE, same pattern applies
- `useSSEProgress.ts` hook — existing SSE consumer, may be adaptable for NDJSON streaming
- Revenue page already has upload handling with loading state

### Established Patterns
- GHL send uses SSE with `EventSource` for progress tracking (different pattern but similar concept)
- Revenue upload currently returns `UploadResponse` with all statements + errors in one response
- `request.is_disconnected()` pattern from Phase 14 — reuse for disconnect detection

### Integration Points
- `backend/app/api/revenue.py` — Add streaming endpoint alongside existing upload
- `frontend/src/pages/Revenue.tsx` — Switch upload handler to use streaming endpoint with progress state
- `frontend/src/utils/api.ts` — May need streaming fetch helper

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard streaming progress pattern applied to the existing sequential PDF processing loop.

</specifics>

<deferred>
## Deferred Ideas

- Per-PDF cancel/retry in revenue — explicitly out of scope per REQUIREMENTS.md
- Parallel PDF processing — not needed, PDFs are typically 2-10 files

</deferred>

---

*Phase: 16-revenue-multi-pdf-streaming*
*Context gathered: 2026-03-20*
