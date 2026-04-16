---
phase: 31-docker-lm-studio-connectivity
plan: 02
subsystem: infra
tags: [docker, ollama, verify-model, e2e, human-verify]

requires:
  - phase: 31
    plan: 01
    provides: Docker Compose host.docker.internal mapping + OpenAIProvider.verify_model
provides:
  - Verified E2E AI enrichment pipeline against host Ollama from inside Docker container
  - Production readiness sign-off for DOCKER-03
affects: [ai-enrichment, docker-deployment]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - .planning/phases/31-docker-lm-studio-connectivity/31-02-PLAN.md

key-decisions:
  - "Accepted Ollama (not LM Studio) as the host LLM runtime; plan doc updated to reflect"
  - "Graceful-degradation path on single-batch timeouts was validated in production: one batch can fail without breaking the run"

patterns-established: []

requirements-completed: [DOCKER-03]

duration: ~20min
completed: 2026-04-16
---

# Phase 31 Plan 02: E2E AI Enrichment Pipeline Verification Summary

**End-to-end enrichment confirmed working on production server: Docker backend reaches host Ollama via host.docker.internal, verify_model passes, inference returns real cleaned results to the UI.**

## Verification Environment

- **Server:** tre-serv-ai (on-prem)
- **Container:** `toolbox-app` (uvicorn + FastAPI)
- **LLM host:** Ollama on host :11434
- **Model in use:** `qwen3.5-9b` (loaded, Q4_K_M, 32k ctx)
- **Config confirmed:** `AI_PROVIDER=ollama`, `LLM_API_BASE=http://host.docker.internal:11434/v1`, `LLM_MODEL=qwen3.5-9b`
- **ExtraHosts confirmed:** `host.docker.internal:host-gateway` present on running container

## Acceptance Criteria — Results

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Container can reach Ollama via `host.docker.internal` | PASS | `GET /v1/models → 200 OK` observed repeatedly in backend logs |
| `verify_model` runs before inference | PASS | `httpx GET /v1/models` calls appear before each batch's `POST /chat/completions` |
| AI enrichment returns proposed changes end-to-end | PASS | `POST /api/pipeline/cleanup → 200 OK`; UI advanced from "Estimating…" to "Batch N of 10" and populated results |
| No `ConnectError` or model verification failures | PASS | No `ConnectError` observed; all model-verification GETs returned 200 |

## Observations (non-blocking)

- **Single-batch timeout under high load:** One `LLM cleanup error for batch 0: Request timed out.` was observed during a 200-row run. The openai SDK retried automatically and a later `POST /chat/completions` for the same batch returned 200. The pipeline's graceful-failure path handled it: the overall `POST /api/pipeline/cleanup` still returned 200 and the UI kept advancing. This is a **tuning concern** (9B model + default SDK timeout + batch size), not a failure of phase 31 objectives.
- **Coverage improvement vs prior runs:** User reported enrichment now processes the full entry list rather than silently skipping entries as in earlier (pre-31) runs. Consistent with the design intent: `verify_model` + explicit Ollama config prevents silent early-exit on model-mismatch or connection-mapping gaps.

## Follow-ups for v2.3 or later

- Raise the openai SDK timeout (or override `httpx.Timeout`) for cleanup calls — candidate default: 180s read timeout
- Consider reducing default `cleanup_batch_size` when `LLM_MODEL` is a 9B-class model
- Add structured log lines (not just SDK logs) summarizing per-batch duration and retry count for capacity planning

## Issues Encountered

None that blocked completion. See Observations above.

## User Setup Required

On the server: Ollama running on host with the configured model pulled (`ollama pull qwen3.5-9b`). Verified present.

## Phase 31 Status

Both plans complete:

- 31-01: Docker Compose config + verify_model — DONE (2026-03-31)
- 31-02: E2E pipeline verification on server — DONE (2026-04-16)

Phase 31 closes out DOCKER-01, DOCKER-02, DOCKER-03 for milestone v2.2.

---
*Phase: 31-docker-lm-studio-connectivity*
*Completed: 2026-04-16*
