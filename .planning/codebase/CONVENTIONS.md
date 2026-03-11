# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- Frontend components and pages: PascalCase (`DataTable.tsx`, `Extract.tsx`, `Modal.tsx`, `AuthContext.tsx`)
- Frontend utilities and hooks: camelCase (`api.ts`, `firebase.ts`, `useToolLayout.ts`, `useSSEProgress.ts`)
- Frontend barrel exports: `index.ts` in `components/` and `pages/`
- Backend Python modules: snake_case (`rrc_data_service.py`, `csv_processor.py`, `export_service.py`)
- Backend naming convention: `{domain}_service.py`, `{type}_parser.py`, `export_service.py`

**Functions:**
- Frontend component functions: PascalCase (`export default function DataTable<T>()`, `function ProtectedRoute()`)
- Frontend regular functions: camelCase with verb prefix (`handleSort()`, `checkAuthorization()`, `connectEventSource()`)
- Frontend event handlers: `handle` prefix (`handleSort`, `handleClick`)
- Backend functions: snake_case (`def process_csv()`, `async def upload_pdf()`)
- Backend private functions: leading underscore (`_save_entries()`, `_init_client()`, `_persist_allowlist_to_firestore()`)

**Variables:**
- Frontend: camelCase (`currentPage`, `sortDirection`, `paginatedData`)
- Frontend booleans: `is/has/should` prefix (`isLoading`, `isAuthorized`, `isAdmin`, `isComplete`)
- Backend: snake_case (`total_count`, `file_bytes`, `job_id`)
- Backend module-level private: leading underscore (`_db`, `_firebase_app`, `_initialized`)

**Types/Interfaces:**
- Frontend interfaces: PascalCase (`interface DataTableProps<T>`, `interface ApiRequestOptions`, `interface ProgressData`)
- Frontend type parameters: single capital letter with extends constraint (`<T extends object>`)
- Backend Pydantic models: PascalCase classes (`class PartyEntry(BaseModel)`, `class Settings(BaseSettings)`)
- Backend enums: `class EntityType(str, Enum)` with PascalCase string values (`EntityType.INDIVIDUAL`, `EntityType.TRUST`)

**Constants:**
- Frontend: SCREAMING_SNAKE_CASE (`const API_BASE_URL`, `const PANEL_COLLAPSED_PREFIX`)
- Backend: SCREAMING_SNAKE_CASE (`USERS_COLLECTION`, `CONTENT_TYPE_MAP`, `DEFAULT_ALLOWED_USERS`, `M1_COLUMNS`)

## Code Style

**Formatting:**
- Frontend: No Prettier configured; rely on ESLint for style enforcement
- Frontend uses single quotes for imports (observed in `AuthContext.tsx`) but inconsistent (some files use single, some double)
- Frontend: No semicolons at end of statements (predominant pattern, see `DataTable.tsx`, `useSSEProgress.ts`)
- Backend: Ruff for linting (no formatter config found beyond `ruff check`)
- Backend: Double quotes for strings (Python convention)

**Linting:**
- Frontend: ESLint 9 with flat config at `frontend/eslint.config.js`
  - Extends: `@eslint/js` recommended, `typescript-eslint` recommended, `react-hooks` recommended, `react-refresh` vite
  - Target: ES2020, browser globals
  - Ignores: `dist/`
- Backend: Ruff (`ruff check app/`)
  - No `.ruff.toml` or `pyproject.toml` ruff config found; uses ruff defaults
- Both linters run via `make lint`
- Linting is best-effort in preflight checks (non-blocking)

**TypeScript:**
- Strict mode enabled in `frontend/tsconfig.app.json`
- `noUnusedLocals: true`, `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- `verbatimModuleSyntax: true` -- use `type` keyword for type-only imports
- `erasableSyntaxOnly: true`
- Target: ES2022, module: ESNext, jsx: react-jsx

## Import Organization

**Frontend Order:**
1. External packages (`react`, `react-router-dom`, `lucide-react`, `firebase/auth`)
2. Internal relative imports -- components (`../components`), contexts (`../contexts/AuthContext`)
3. Utilities (`../utils/api`)
4. Type-only imports using `type` keyword (`import type { AiSuggestion } from '../utils/api'`)

**Frontend Pattern Examples (from `frontend/src/pages/Extract.tsx`):**
```typescript
import { useState, useMemo, useEffect, useRef } from 'react'
import { FileSearch, Download, Upload, ... } from 'lucide-react'
import { FileUpload, Modal, AiReviewPanel, EnrichmentPanel } from '../components'
import { aiApi, enrichmentApi } from '../utils/api'
import type { AiSuggestion } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useToolLayout } from '../hooks/useToolLayout'
```

**Backend Order:**
1. `from __future__ import annotations` (when used for forward references)
2. Standard library (`logging`, `json`, `pathlib`, `datetime`)
3. Third-party (`fastapi`, `pydantic`, `pandas`)
4. Internal imports (`from app.core.config import settings`, `from app.models.extract import ...`)

**Backend Pattern Examples (from `backend/app/api/extract.py`):**
```python
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.extract import ExtractionResult, PartyEntry, UploadResponse
from app.services.extract.export_service import to_csv, to_excel
```

**Path Aliases:**
- No path aliases configured in frontend (uses relative paths like `../components`, `../utils/api`)
- Backend uses absolute imports from `app.` root (`from app.core.config import settings`)

## Error Handling

**Frontend Patterns:**
- `ApiClient` wraps all fetch calls and returns `ApiResponse<T>` with `{ data, error, status }` -- never throws
- Errors are surfaced via the `error` field in the response object
- FastAPI 422 validation errors are parsed into readable strings (`field: message`)
- Timeout errors handled via `AbortController` with configurable timeout (default 30s)
- Auth errors: Firebase error codes mapped to user-friendly messages in `AuthContext.tsx`
- File: `frontend/src/utils/api.ts`

```typescript
// Pattern: All API calls return { data, error, status } -- check error field
const { data, error } = await api.post<ResultType>('/endpoint', body)
if (error) {
  // Handle error (set state, show toast, etc.)
}
```

**Backend Patterns:**
- `HTTPException` with appropriate status codes (400, 401, 403, 404, 500)
- Re-raise `HTTPException` explicitly, catch-all `Exception` for unexpected errors
- `from e` chaining on re-raised exceptions
- Fire-and-forget for non-critical operations (Firestore persistence never blocks user response)
- Graceful fallbacks for optional services (GCS, Firestore, Firebase Admin)
- File: `backend/app/api/extract.py`, `backend/app/core/ingestion.py`

```python
# Pattern: Re-raise known HTTPExceptions, wrap unexpected errors
try:
    result = process(data)
except HTTPException:
    raise
except Exception as e:
    logger.exception("Error processing: %s", e)
    raise HTTPException(status_code=500, detail=f"Error: {e!s}") from e
```

**Backend Fallback Pattern:**
```python
# Pattern: Try optional service, warn and continue on failure
try:
    from app.services.firestore_service import some_function
    await some_function()
except Exception as e:
    logger.warning(f"Service unavailable (non-critical): {e}")
```

## Logging

**Framework:** Python `logging` module (backend), `console` (frontend)

**Backend Patterns:**
- Every module: `logger = logging.getLogger(__name__)`
- Root config in `backend/app/main.py`: `logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")`
- Use `%s` format strings (not f-strings) in `logger.info()`, `logger.warning()`, `logger.exception()`
- Use `logger.exception()` for caught exceptions (includes traceback)
- Use `logger.warning()` for non-critical failures
- Use `logger.debug()` for verbose/diagnostic info

```python
# Correct logging pattern
logger.info("Extracted %d entries from %s", len(entries), file.filename)
logger.exception("Error processing PDF: %s", e)
logger.warning("Could not load allowlist from Firestore: %s", e)
```

**Frontend Patterns:**
- `console.error()` for caught errors in auth flows
- No structured logging framework

## Comments

**When to Comment:**
- Module-level docstrings on all Python files describing purpose (triple-quoted)
- Docstrings on all public Python functions and classes
- Inline comments for non-obvious logic or workarounds
- `# NOTE:` for important context about why something is done a certain way
- Section dividers using `# ====...====` or `# ----...----` comment blocks in service files

**JSDoc/TSDoc:**
- Minimal use in frontend; `useToolLayout.ts` uses `/** ... */` JSDoc comments
- No systematic JSDoc on React components or hooks

**Pydantic Field Descriptions:**
- All Pydantic model fields include `description=` parameter in `Field(...)`
- This serves as documentation and powers Swagger/OpenAPI docs

## Function Design

**Size:**
- Route handlers in API files: 20-80 lines typical
- Service functions: focused, single-responsibility
- Frontend page components: can be very large (Extract.tsx is 1400+ lines) -- these contain significant inline logic

**Parameters:**
- Backend: Use keyword-only args (`*`) for multi-param functions (see `persist_job_result()`)
- Backend: Use `Annotated[type, metadata]` for FastAPI params (`Annotated[UploadFile, File(...)]`)
- Frontend: Destructure props objects in component signatures

**Return Values:**
- Backend routes: Return Pydantic models (response_model annotation) or dict
- Backend services: Return tuples for multi-value results (`success, message, row_count`)
- Frontend API: Always return `ApiResponse<T>` with `{ data, error, status }`

## Module Design

**Exports:**
- Frontend: Default exports for components, named exports for utilities and types
- Frontend: Barrel re-exports in `frontend/src/components/index.ts` and `frontend/src/pages/index.ts`
- Backend: No barrel files; direct imports from specific modules

**Barrel Files:**
- `frontend/src/components/index.ts`: Re-exports all default component exports as named exports
- Pattern: `export { default as ComponentName } from './ComponentName'`

**Frontend API Organization:**
- Singleton `ApiClient` instance exported as `api` from `frontend/src/utils/api.ts`
- Per-domain API objects (`aiApi`, `enrichmentApi`, `ghlApi`) defined in the same file
- Types colocated with their API functions in `api.ts`

**Backend Service Organization:**
- Tool-per-directory in `backend/app/services/` (e.g., `services/extract/`, `services/proration/`)
- Shared services at `backend/app/services/` root level (`firestore_service.py`, `storage_service.py`)
- Lazy imports for heavy/optional dependencies (Firebase, Firestore, Gemini)

## Pydantic Model Conventions

- Use `Field(...)` for required fields with description
- Use `Field(default, description=...)` for optional fields with defaults
- Use `default_factory=list` for mutable defaults
- Enums: `class MyEnum(str, Enum)` pattern with PascalCase string values
- Model naming: `{Noun}Entry`, `{Noun}Result`, `{Noun}Response`, `{Noun}Request`
- File: `backend/app/models/extract.py`

```python
class PartyEntry(BaseModel):
    entry_number: str = Field(..., description="Entry number")
    entity_type: EntityType = Field(default=EntityType.INDIVIDUAL, description="Type of entity")
    mailing_address: Optional[str] = Field(None, description="Street address")
    entries: list[PartyEntry] = Field(default_factory=list, description="List of entries")
```

## Configuration Pattern

- Pydantic `BaseSettings` with `SettingsConfigDict(env_file=".env")`
- `@property` methods for computed boolean checks (`use_gcs`, `use_database`, `use_gemini`)
- Singleton pattern: `settings = Settings()` at module level
- File: `backend/app/core/config.py`

## Styling Conventions

- Tailwind CSS utility classes inline (no separate CSS files per component)
- Custom brand colors with `tre-` prefix: `bg-tre-navy`, `text-tre-teal`, `border-tre-tan`
- Oswald font via `font-oswald` utility class
- Responsive classes used sparingly (mostly desktop-oriented internal tool)
- Common patterns: `rounded-xl`, `border border-gray-200`, `shadow-sm`
- Disabled states: `disabled:opacity-50 disabled:cursor-not-allowed`
- Transition utilities: `transition-colors`, `hover:bg-gray-100`
- Colors defined in `frontend/tailwind.config.js`

---

*Convention analysis: 2026-03-10*
