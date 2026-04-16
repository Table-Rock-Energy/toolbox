---
phase: 32-nginx-proxy-configuration
milestone: v2.2
---

# Phase 32 Context

## Problem

Production on-prem deployment uses nginx (`nginx/default.conf`) as the reverse proxy in front of the FastAPI backend. Two endpoint classes currently fall outside the proxy's hardening:

1. **`/api/pipeline/cleanup`, `/api/pipeline/validate`, `/api/pipeline/enrich`** — AI enrichment routes that call local Ollama through the container. With a 9B-class model (`qwen3.5-9b`), a single batch can take 3–6 minutes. These routes currently hit the `location /` default block (`proxy_read_timeout 120s`), which means nginx can close the upstream connection with a 504 before the backend finishes. Observed in phase 31 verification on tre-serv-ai.
2. **`/api/revenue/upload`** — NDJSON streaming endpoint (`StreamingResponse` at `backend/app/api/revenue.py:281`) that delivers per-PDF progress updates during multi-file revenue parsing. Because the route is served by the default `/` block, `proxy_buffering` is on (nginx default), so the frontend only sees progress in batches rather than as they happen.

## Existing proxy-hardened routes (reference)

The config already handles two classes correctly:

- `/api/proration/` — 300s timeouts, `proxy_buffering off` (NDJSON streaming for fetch-missing)
- `/api/ghl/send/` — 600s timeouts, `proxy_buffering off` (SSE progress stream)

These are the pattern to follow.

## Endpoints in scope

| Route prefix | Purpose | Why nginx cares |
|--------------|---------|-----------------|
| `/api/pipeline/` | AI cleanup/validate/enrich via Ollama | Long-running (multi-minute batches); needs extended read timeout |
| `/api/revenue/` | NDJSON streaming progress for multi-PDF upload | Needs `proxy_buffering off` and extended timeout |

## Constraints

- Single file to edit: `nginx/default.conf` (no other ingress)
- Changes are deployed to production on-prem via git pull + `nginx -s reload` (or container restart of `toolbox-nginx`)
- On-prem Cloud Run CI/CD is disabled (per milestone v2.0) — deployment is manual
- Cannot regress existing proration/ghl-send/proration location blocks
- TLS termination and security headers already correct — don't touch
- `client_max_body_size 50M` already matches backend — don't touch
