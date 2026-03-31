# Architecture Patterns

**Domain:** On-prem Docker + nginx + LM Studio integration
**Researched:** 2026-03-31
**Confidence:** HIGH -- no structural changes needed, existing architecture is sound

## Current Architecture (No Changes Needed)

```
Internet
   |
nginx (443, SSL termination)
   |
Docker container (8080)
   ├── FastAPI (uvicorn)
   │   ├── /api/pipeline/* --> OpenAIProvider --> LM Studio (1234)
   │   ├── /api/revenue/*  --> PDF parsers --> PostgreSQL
   │   ├── /api/proration/* --> RRC service --> PostgreSQL
   │   └── /api/*           --> various services --> PostgreSQL
   │
   └── Static files (React SPA build)

LM Studio (1234, host machine)
   └── qwen3.5-35b-a3b model (GPU inference)

PostgreSQL (5432, host machine)
   └── toolbox database
```

## Network Topology on Linux Docker

The critical architecture detail for v2.2 is how the Docker container reaches host services:

```
┌─────────────────────────────────┐
│  Ubuntu Server (host)           │
│                                 │
│  ┌──────────┐  ┌──────────┐    │
│  │ LM Studio│  │PostgreSQL│    │
│  │ :1234    │  │ :5432    │    │
│  └────▲─────┘  └────▲─────┘    │
│       │              │          │
│  host.docker.internal           │
│  (172.17.0.1 via --add-host)   │
│       │              │          │
│  ┌────┴──────────────┴─────┐   │
│  │  Docker container       │   │
│  │  tablerock-tools:8080   │   │
│  └─────────▲───────────────┘   │
│            │                    │
│  ┌─────────┴───────────┐       │
│  │  nginx :443         │       │
│  │  proxy_pass :8080   │       │
│  └─────────▲───────────┘       │
└────────────┼───────────────────┘
             │
          Internet
```

## Component Boundaries (Unchanged)

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| nginx | SSL termination, request routing, timeout management | Docker container via localhost:8080 |
| FastAPI container | API logic, PDF processing, data persistence | PostgreSQL via host.docker.internal:5432, LM Studio via host.docker.internal:1234 |
| LM Studio | Local LLM inference | Receives OpenAI-compatible API calls from FastAPI |
| PostgreSQL | Data persistence | Receives async queries from FastAPI via asyncpg |

## Data Flow: AI Enrichment Pipeline

```
1. Frontend POST /api/pipeline/cleanup {tool, entries[]}
2. nginx routes to container (600s timeout, no buffering)
3. FastAPI pipeline handler calls get_llm_provider()
4. OpenAIProvider batches entries (25 per batch)
5. For each batch:
   a. Build system prompt + user prompt with JSON entries
   b. POST to LM Studio /v1/chat/completions
   c. Parse JSON from response (handles markdown fences, preamble)
   d. Convert AiSuggestion -> ProposedChange
6. Return all ProposedChanges to frontend
7. Frontend applies changes to preview state
```

## Patterns to Follow

### Pattern 1: Explicit Host Resolution for Docker on Linux
**What:** Always use `--add-host=host.docker.internal:host-gateway` in production docker run commands on Linux.
**When:** Any time the container needs to reach a service on the host machine.
**Why:** Prevents silent DNS resolution failures that look like service unavailability.

### Pattern 2: Endpoint-Specific Nginx Location Blocks
**What:** Every endpoint pattern with non-default timeout or buffering needs its own location block.
**When:** SSE, NDJSON streaming, long-running AI inference, large file uploads.
**Why:** The catch-all location block can't serve both quick API responses (120s) and slow AI inference (600s).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using --network=host for Docker
**What:** Running the container with `--network=host` to avoid DNS resolution issues.
**Why bad:** Exposes all container ports directly on the host. Container port 8080 becomes accessible without nginx. Defeats the security benefit of binding only to 127.0.0.1.
**Instead:** Use `--add-host=host.docker.internal:host-gateway` with explicit port binding.

### Anti-Pattern 2: Hardcoding IP Addresses in Config
**What:** Setting `LLM_API_BASE=http://172.17.0.1:1234/v1` instead of using `host.docker.internal`.
**Why bad:** Docker's bridge network IP can change. Works today, breaks after Docker daemon restart or network reconfiguration.
**Instead:** Use `host.docker.internal` with the `--add-host` flag.
