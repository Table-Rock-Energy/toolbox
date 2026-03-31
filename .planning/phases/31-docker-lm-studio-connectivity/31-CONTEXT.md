# Phase 31: Docker + LM Studio Connectivity - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

AI enrichment pipeline works end-to-end from inside the Docker container using LM Studio running on the host. This requires fixing Docker DNS resolution for `host.docker.internal` on Linux, verifying the model ID format against LM Studio's API, and confirming the full upload → enrich → results pipeline works on the server.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from research:
- `host.docker.internal` needs `--add-host=host.docker.internal:host-gateway` in docker-compose on Linux
- LM Studio exposes OpenAI-compatible API at `http://host.docker.internal:1234/v1`
- Model ID format needs verification against `GET /v1/models` on actual LM Studio instance
- The OpenAI-compatible provider (`openai_provider.py`) already exists from v2.0

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/openai_provider.py` — OpenAI-compatible LLM provider for LM Studio
- `backend/app/core/config.py` — Pydantic Settings with AI_PROVIDER config
- `docker-compose.yml` — Docker Compose service definitions

### Established Patterns
- Provider factory routing AI calls based on AI_PROVIDER config
- LM Studio configured via LM_STUDIO_BASE_URL and LM_STUDIO_MODEL settings

### Integration Points
- docker-compose.yml `extra_hosts` for DNS resolution
- Backend startup/health check for LM Studio connectivity
- Admin settings page for model selection

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
