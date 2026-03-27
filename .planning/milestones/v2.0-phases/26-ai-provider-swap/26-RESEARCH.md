# Phase 26: AI Provider Swap - Research

**Researched:** 2026-03-25
**Domain:** LLM provider abstraction (Gemini -> LM Studio via OpenAI SDK)
**Confidence:** HIGH

## Summary

The codebase has a clean `LLMProvider` protocol in `llm/protocol.py` with a factory in `llm/__init__.py`. Currently only `GeminiProvider` exists. The swap requires: (1) a new `OpenAIProvider` implementing the same protocol, (2) updated factory routing on `AI_PROVIDER` config, (3) removal of `gemini_service.py`, `gemini_provider.py`, and `google-genai` dependency.

The blast radius is wider than just the LLM layer. Direct Gemini imports exist in **6 backend files** (ai_validation.py, revenue.py, data_enrichment_pipeline.py, pipeline.py, features.py, admin.py) plus **2 frontend files** (AdminSettings.tsx, api.ts). The admin settings API has Gemini-specific endpoints (`/settings/gemini`) and models that need renaming. The revenue parser (`gemini_revenue_parser.py`) calls Gemini directly, bypassing the LLM abstraction entirely.

**Primary recommendation:** Build `OpenAIProvider` implementing `LLMProvider` protocol, then systematically replace all Gemini references. The revenue parser needs rewriting to use the provider abstraction. Admin settings need renaming from "gemini" to "ai" terminology. Rate limiting and budget tracking from `gemini_service.py` are Gemini-specific (API cost tracking) and should be removed for local inference.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked -- all implementation choices at Claude's discretion.

Key research findings incorporated as constraints:
- OpenAI SDK (>=1.60.0) for LM Studio -- set base_url, api_key="lm-studio"
- LM Studio default endpoint: http://localhost:1234/v1
- JSON mode unreliable -- prompt for JSON and parse from text (regex {..} extraction)
- No API key needed for LM Studio -- pass dummy value
- Skip rate limiting for local inference (no API costs)
- Keep LLMProvider protocol unchanged -- new provider implements same interface
- Existing provider factory in llm/__init__.py -- add OpenAI branch
- New env vars: AI_PROVIDER (default "none"), LLM_API_BASE (default "http://localhost:1234/v1"), LLM_MODEL (default "local-model")
- Remove google-genai from requirements.txt, delete gemini_service.py and GeminiProvider
- Default model: qwen3.5-35b-a3b (from user spec)

### Claude's Discretion
All implementation choices.

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AI-01 | OpenAI-compatible provider calls LM Studio at configurable base URL implementing LLMProvider protocol | OpenAI SDK 2.30.0 confirmed; `LLMProvider` protocol has 2 methods: `cleanup_entries` and `is_available`; new `OpenAIProvider` class needed |
| AI-02 | Provider factory routes AI calls based on AI_PROVIDER config (lmstudio or none) | Factory in `llm/__init__.py` currently hardcodes GeminiProvider; add switch on `settings.ai_provider` |
| AI-03 | Gemini provider and google-genai dependency removed entirely | `google-genai>=1.0.0` in requirements.txt; GeminiProvider in llm/; gemini_service.py (409 lines); gemini_revenue_parser.py (197 lines); plus references in 6 backend + 2 frontend files |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Use `python3` not `python` on macOS
- Backend patterns: snake_case modules, async route handlers, lazy imports, `logger = logging.getLogger(__name__)` per module
- Pydantic models with `Field(...)` descriptors
- Config via Pydantic Settings with `@property` for computed values
- Frontend: PascalCase components, camelCase utils, Tailwind utility classes
- Testing: pytest with async support, `make test` to run

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | >=2.0.0 | OpenAI-compatible API client for LM Studio | Latest stable is 2.30.0. LM Studio exposes `/v1/chat/completions`. SDK handles base_url routing natively. |

### Removed
| Library | Version | Reason |
|---------|---------|--------|
| google-genai | >=1.0.0 | Gemini dependency -- replaced by openai SDK |

**Installation:**
```bash
# Add to requirements.txt (replacing google-genai line)
pip install "openai>=2.0.0"

# Remove
# google-genai>=1.0.0  (delete this line)
```

**Version verification:** openai 2.30.0 confirmed on PyPI (2026-03-25). Not currently installed in local venv.

## Architecture Patterns

### New Provider Structure
```
backend/app/services/llm/
    __init__.py          # Updated factory (switch on AI_PROVIDER)
    protocol.py          # UNCHANGED - LLMProvider protocol
    prompts.py           # UNCHANGED - cleanup prompts (provider-agnostic)
    openai_provider.py   # NEW - OpenAI-compatible provider for LM Studio
    # gemini_provider.py  DELETED
```

### Pattern 1: OpenAI Provider Implementation
**What:** New `OpenAIProvider` class satisfying `LLMProvider` protocol
**When to use:** All AI calls (cleanup, validation, revenue parsing)
**Example:**
```python
# backend/app/services/llm/openai_provider.py
from openai import OpenAI
from app.core.config import settings

class OpenAIProvider:
    """LLM provider backed by OpenAI-compatible API (LM Studio, Ollama, etc.)."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=settings.llm_api_base,
                api_key=settings.llm_api_key or "not-needed",
            )
        return self._client

    def is_available(self) -> bool:
        return settings.ai_provider == "lmstudio"

    async def cleanup_entries(self, tool, entries, *, source_data=None, disconnect_check=None):
        # Implementation using chat.completions.create
        ...
```

### Pattern 2: JSON Response Parsing (Critical)
**What:** LM Studio models often wrap JSON in markdown fences or add preamble text
**When to use:** Every LLM response that expects JSON
**Example:**
```python
import json
import re

def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and preamble."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
```

### Pattern 3: Provider Factory with Config Routing
**What:** Factory returns provider based on AI_PROVIDER setting
**Example:**
```python
def get_llm_provider() -> LLMProvider | None:
    if settings.ai_provider == "lmstudio":
        from app.services.llm.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        return provider if provider.is_available() else None
    return None  # AI_PROVIDER=none
```

### Pattern 4: Config Changes
**What:** New settings fields replacing Gemini-specific ones
```python
# New fields in Settings
ai_provider: str = "none"           # "lmstudio" or "none"
llm_api_base: str = "http://localhost:1234/v1"
llm_model: str = "qwen3.5-35b-a3b"
llm_api_key: Optional[str] = None

# Remove these fields:
# gemini_api_key, gemini_enabled, gemini_model, gemini_monthly_budget
# google_api_key (if only used for Gemini)

# Replace property:
@property
def use_ai(self) -> bool:
    return self.ai_provider != "none"
```

### Anti-Patterns to Avoid
- **Keeping rate limiting for local inference:** LM Studio is local, no API costs or rate limits. The entire rate-limiting infrastructure from gemini_service.py should be removed, not ported.
- **Using `response_format={"type": "json_object"}`:** CONTEXT.md explicitly states JSON mode is unreliable with LM Studio. Prompt for JSON in the system message and parse from text.
- **Leaving gemini_service.py functions scattered:** The `validate_entries`, `verify_revenue_entries`, `get_ai_status` functions from gemini_service.py are used directly by 3 API routes. These must be replaced, not left dangling.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAI API client | Raw httpx calls | `openai` SDK | Handles retries, types, streaming, auth |
| JSON extraction from text | Complex parser | Regex cascade (fence -> brace) | 3 fallback steps covers all LM Studio output patterns |

## Comprehensive File Audit

### Files to CREATE
| File | Purpose |
|------|---------|
| `backend/app/services/llm/openai_provider.py` | New OpenAI-compatible provider |

### Files to DELETE
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/services/gemini_service.py` | 535 | Gemini client, rate limiting, validation, revenue verify |
| `backend/app/services/llm/gemini_provider.py` | 186 | GeminiProvider class |
| `backend/app/services/revenue/gemini_revenue_parser.py` | 197 | Direct Gemini revenue parsing |

### Files to MODIFY (Backend)
| File | What Changes |
|------|-------------|
| `backend/app/services/llm/__init__.py` | Factory routes on `settings.ai_provider` instead of hardcoding GeminiProvider |
| `backend/app/core/config.py` | Add `ai_provider`, `llm_api_base`, `llm_model`, `llm_api_key`. Remove `gemini_*` fields and `google_api_key`. Replace `use_gemini` with `use_ai`. |
| `backend/app/api/ai_validation.py` | Replace `gemini_service` imports with new provider-based calls. `validate_entries` and `get_ai_status` need new implementations. |
| `backend/app/api/revenue.py` | Replace `gemini_revenue_parser` import with provider-based revenue parsing (or remove AI revenue parsing if out of scope) |
| `backend/app/api/pipeline.py` | Update error message strings from "Gemini" to "AI" |
| `backend/app/api/features.py` | Change `settings.use_gemini` to `settings.use_ai` |
| `backend/app/api/extract.py` | Change `settings.use_gemini` to `settings.use_ai` |
| `backend/app/api/admin.py` | Rename Gemini settings endpoints/models to AI terminology. Update `GeminiSettingsRequest/Response` to `AiSettingsRequest/Response`. Rename `/settings/gemini` to `/settings/ai`. |
| `backend/app/services/data_enrichment_pipeline.py` | Replace `gemini_service.validate_entries` with provider-based call. Change `settings.use_gemini` to `settings.use_ai`. |
| `backend/requirements.txt` | Remove `google-genai>=1.0.0`, add `openai>=2.0.0` |

### Files to MODIFY (Frontend)
| File | What Changes |
|------|-------------|
| `frontend/src/pages/AdminSettings.tsx` | Rename `gemini_enabled/model/budget` to `ai_enabled/model/budget`. Update API endpoint from `/settings/gemini` to `/settings/ai`. Remove Gemini model dropdown (replace with text input for LLM_MODEL). Remove monthly budget UI (no cost tracking for local). |
| `frontend/src/utils/api.ts` | Rename `gemini_enabled` to `ai_enabled` in types |

### Test Files to UPDATE
| File | What Changes |
|------|-------------|
| `backend/tests/test_llm_protocol.py` | Replace GeminiProvider with OpenAIProvider |
| `backend/tests/test_pipeline.py` | Update mock paths from gemini to openai provider |
| `backend/tests/test_features_status.py` | Update `use_gemini` to `use_ai` mocks |
| `backend/tests/test_post_process.py` | Update Gemini references |
| `backend/tests/test_auth_enforcement.py` | May have Gemini references |
| `backend/tests/test_prompts.py` | Should be unchanged (prompts are provider-agnostic) |

## Key Design Decisions

### Revenue Parser Strategy
`gemini_revenue_parser.py` calls Gemini directly (not through LLMProvider protocol). Two options:
1. **Rewrite as provider-based:** Create a revenue parsing method on OpenAIProvider or a standalone function that uses the provider
2. **Remove AI revenue parsing:** Revenue has traditional parsers (EnergyLink, Enverus, Energy Transfer) that work without AI. Gemini was a fallback.

**Recommendation:** Remove `gemini_revenue_parser.py` entirely. The traditional parsers handle known formats. If AI revenue parsing is needed later, it can be added as a proper provider method. This simplifies the swap and avoids porting complex revenue-specific prompts to a different model that may behave differently.

### Validation Service Strategy
`gemini_service.py` exposes `validate_entries()` and `verify_revenue_entries()` used by `ai_validation.py` and `data_enrichment_pipeline.py`. These need replacements:
- Move `validate_entries` logic into the new provider (or a thin wrapper that uses the provider)
- The `get_ai_status()` function should return simplified status (no rate limits, no budget for local)
- The `AiStatusResponse` model has budget/rate-limit fields -- these become optional/zero for local

### Admin Settings Renaming
The admin API has Gemini-specific endpoints and models. Rename:
- `/settings/gemini` -> `/settings/ai`
- `GeminiSettingsRequest` -> `AiSettingsRequest` (fields: `enabled`, `model`)
- `GeminiSettingsResponse` -> `AiSettingsResponse` (drop `monthly_budget`, `has_key`)
- Remove API key management UI (LM Studio needs no key)
- Remove budget tracking UI (local inference has no cost)

### Config Field Mapping
| Old (Gemini) | New (Generic) | Notes |
|-------------|---------------|-------|
| `gemini_api_key` | `llm_api_key` | Optional, LM Studio ignores |
| `gemini_enabled` | (removed) | Replaced by `ai_provider != "none"` |
| `gemini_model` | `llm_model` | Default: "qwen3.5-35b-a3b" |
| `gemini_monthly_budget` | (removed) | No cost tracking for local |
| `google_api_key` | (removed) | Was unified Gemini/Maps key. Maps key stays separate if Google Maps is still used. |
| (new) | `ai_provider` | "lmstudio" or "none" |
| (new) | `llm_api_base` | Default: "http://localhost:1234/v1" |

**Note on `google_api_key`:** This field serves as a unified key for Gemini, Google Maps, and Google Places. Removing it would break Maps/Places if they're still used. Check: `use_google_maps` and `use_places` both fall back to `google_api_key`. Since this phase only removes Gemini, keep `google_api_key` if Maps/Places still need it, or remove it if those are also being removed in Phase 27. **Safest:** Keep `google_api_key` in this phase (it does no harm), let Phase 27 clean it up with GCS removal.

## Common Pitfalls

### Pitfall 1: JSON Parsing Failures from Local Models
**What goes wrong:** Local models (Qwen, Llama) often return JSON wrapped in markdown fences, with preamble text, or with trailing commas.
**Why it happens:** Unlike Gemini's `response_mime_type="application/json"`, local models don't enforce JSON output structure.
**How to avoid:** Always use the `parse_json_response()` cascade function. Never call `json.loads(response.text)` directly.
**Warning signs:** `json.JSONDecodeError` in logs.

### Pitfall 2: Synchronous OpenAI Client in Async Context
**What goes wrong:** The `openai.OpenAI` client is synchronous. Calling it in an async handler blocks the event loop.
**Why it happens:** The existing code already handles this with `asyncio.to_thread()` for Gemini sync calls.
**How to avoid:** Use `asyncio.to_thread()` for all OpenAI client calls, same pattern as existing code. Alternatively, use `openai.AsyncOpenAI` for native async support.
**Recommendation:** Use `AsyncOpenAI` since all route handlers are already async. This is cleaner than `to_thread()`.

### Pitfall 3: Stale Gemini References in Admin Settings
**What goes wrong:** The admin settings API has ~40 lines of Gemini-specific code with hardcoded field names like `gemini_enabled`, `gemini_model`, `gemini_monthly_budget`. Missing any reference causes runtime errors or dead UI.
**How to avoid:** Full grep for "gemini" across the entire codebase after changes. Every occurrence must be addressed.

### Pitfall 4: Test Mocks Reference Old Paths
**What goes wrong:** Tests mock `app.services.gemini_service` and `app.services.llm.gemini_provider`. After deletion, tests fail on import.
**How to avoid:** Update all test mock paths to use new provider paths.

### Pitfall 5: LM Studio Not Running
**What goes wrong:** `OpenAIProvider.is_available()` returns True (config says "lmstudio") but LM Studio isn't running, causing connection errors.
**How to avoid:** `is_available()` should only check config, not connectivity. Let actual calls fail gracefully with proper error messages. The pipeline already handles provider errors.

## Code Examples

### OpenAI SDK Chat Completion (for LM Studio)
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed",
)

response = await client.chat.completions.create(
    model="qwen3.5-35b-a3b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.1,
)

text = response.choices[0].message.content
data = parse_json_response(text)  # Custom parser with fallbacks
```

### AsyncOpenAI vs OpenAI
```python
# Synchronous (requires asyncio.to_thread in async context)
from openai import OpenAI
client = OpenAI(base_url=..., api_key=...)
response = client.chat.completions.create(...)  # blocks

# Async (native, preferred for FastAPI)
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=..., api_key=...)
response = await client.chat.completions.create(...)  # non-blocking
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/test_llm_protocol.py tests/test_pipeline.py -x -q` |
| Full suite command | `cd backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-01 | OpenAIProvider satisfies LLMProvider protocol | unit | `cd backend && python3 -m pytest tests/test_llm_protocol.py -x` | Exists (needs update from GeminiProvider to OpenAIProvider) |
| AI-01 | JSON response parsing handles fenced/preamble output | unit | `cd backend && python3 -m pytest tests/test_llm_protocol.py::TestJsonParsing -x` | Wave 0 |
| AI-02 | Factory returns OpenAIProvider when AI_PROVIDER=lmstudio | unit | `cd backend && python3 -m pytest tests/test_llm_protocol.py::TestProviderFactory -x` | Wave 0 |
| AI-02 | Factory returns None when AI_PROVIDER=none | unit | `cd backend && python3 -m pytest tests/test_llm_protocol.py::TestProviderFactory -x` | Wave 0 |
| AI-03 | No google-genai imports in codebase | smoke | `cd backend && python3 -c "import ast, sys; [sys.exit(1) for f in __import__('glob').glob('app/**/*.py', recursive=True) if 'google.genai' in open(f).read() or 'google_genai' in open(f).read()]"` | Wave 0 |
| AI-03 | Pipeline cleanup works with mocked OpenAI provider | integration | `cd backend && python3 -m pytest tests/test_pipeline.py -x` | Exists (needs mock path updates) |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_llm_protocol.py tests/test_pipeline.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_llm_protocol.py::TestJsonParsing` -- covers JSON extraction from fenced/preamble text
- [ ] `tests/test_llm_protocol.py::TestProviderFactory` -- covers factory routing on AI_PROVIDER config
- [ ] Update existing `test_llm_protocol.py` to reference `OpenAIProvider` instead of `GeminiProvider`
- [ ] Update `test_pipeline.py` mock paths from `gemini_provider` to `openai_provider`
- [ ] Smoke test: no `google.genai` or `google_genai` imports remain

## Sources

### Primary (HIGH confidence)
- Codebase audit: all files listed in Comprehensive File Audit read directly
- PyPI: openai 2.30.0 (verified 2026-03-25)
- STACK.md research: LM Studio OpenAI compatibility confirmed

### Secondary (MEDIUM confidence)
- CONTEXT.md: JSON mode unreliability claim (user experience, not independently verified)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- openai SDK is the universal standard for OpenAI-compatible endpoints
- Architecture: HIGH -- existing LLMProvider protocol is clean, pattern is straightforward
- Pitfalls: HIGH -- based on direct codebase audit, all Gemini references catalogued

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable domain, no rapid API changes expected)
