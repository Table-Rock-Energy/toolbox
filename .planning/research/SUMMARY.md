# Research Summary: v2.2 Post-Migration Fixes & AI Enrichment

**Project:** Table Rock Tools
**Synthesized:** 2026-03-31
**Milestone:** v2.2 Post-Migration Fixes & AI Enrichment
**Overall confidence:** HIGH

## Executive Summary

v2.2 is a stabilization milestone, not a feature milestone. The v2.0 on-prem migration shipped the infrastructure (JWT auth, PostgreSQL, LM Studio provider, local storage), and several ad-hoc fixes have already landed (revenue Decimal coercion, admin password hashing, GHL-prep filters, RRC PostgreSQL migration). The remaining work is getting AI enrichment working end-to-end on the Ubuntu server and hardening the nginx configuration for long-running AI inference requests.

The primary blocker for AI enrichment is almost certainly `host.docker.internal` DNS resolution on Linux Docker. This hostname resolves automatically on Docker Desktop (Mac/Windows) but requires explicit `--add-host=host.docker.internal:host-gateway` on Linux. The LM Studio provider is configured to reach `http://host.docker.internal:1234/v1`, so without this flag, all AI calls fail silently with connection errors.

The nginx config needs two additional location blocks: one for `/api/pipeline/` (AI enrichment with 600s timeout and disabled buffering) and one for `/api/revenue/` (NDJSON streaming). The current catch-all block has a 120s timeout which is too short for local inference on a 35B parameter model.

No new dependencies are needed. This is entirely a configuration and debugging milestone.

## Key Findings

**Stack:** No changes. All required libraries (openai SDK, sse-starlette, SQLAlchemy) are already installed.
**Architecture:** No structural changes. The LLM provider abstraction (`openai_provider.py` + protocol) is correctly designed.
**Critical pitfall:** `host.docker.internal` doesn't resolve on Linux Docker without `--add-host` flag -- this is the #1 suspected cause of AI enrichment failure on the server.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Docker + LM Studio Connectivity** - Fix `--add-host` flag, verify model ID, test from inside container
   - Addresses: AI enrichment end-to-end on server
   - Avoids: Silent connection failures from unresolvable hostname

2. **Nginx Configuration** - Add pipeline and revenue location blocks with proper timeouts
   - Addresses: Request timeouts during AI inference, buffered streaming responses
   - Avoids: 504 Gateway Timeout on long inference, delayed NDJSON delivery

3. **Bug Fix Consolidation** - Retroactively track already-shipped fixes (Decimal coercion, password hashing, etc.)
   - Addresses: Changelog accuracy, milestone completeness
   - Avoids: Losing track of production fixes

**Phase ordering rationale:**
- Docker connectivity must come first because nginx config doesn't matter if the backend can't reach LM Studio
- Nginx config second because it affects all streaming/long-running endpoints
- Bug consolidation is bookkeeping and can happen anytime

**Research flags for phases:**
- Phase 1: May need model-specific debugging if model ID format doesn't match LM Studio's expectation
- Phase 2: Standard nginx patterns, unlikely to need further research
- Phase 3: No research needed, these are already-shipped fixes

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No changes needed, all libraries present |
| Features | HIGH | Scope is debugging + config, not new features |
| Architecture | HIGH | No structural changes |
| Pitfalls | HIGH | `host.docker.internal` issue is well-documented, nginx SSE patterns are established |

## Gaps to Address

- Actual GPU/hardware specs on the Ubuntu server will determine if 600s timeout is sufficient for the qwen3.5-35b model
- Model ID format needs verification against `GET /v1/models` on the actual LM Studio instance
- PostgreSQL connection from Docker container needs verification (same `host.docker.internal` issue)
