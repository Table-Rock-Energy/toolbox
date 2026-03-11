# Architecture Patterns: GHL Prep Tool

**Domain:** CSV Transformation Tool (Mineral to GoHighLevel format)
**Researched:** 2026-02-25
**Confidence:** HIGH (based on existing codebase patterns)

## Recommended Architecture

The GHL Prep tool follows the established **tool-per-module** pattern used by Extract, Title, Proration, and Revenue tools. It is a standalone tool with no dependencies on other tool business logic, but shares the common infrastructure components.

### Integration Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Existing Infrastructure                      │
├─────────────────────────────────────────────────────────────────┤
│  IngestionEngine   StorageService   FirestoreService  DataTable  │
│  FileUpload        Modal            shared/export_utils          │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   GHL Prep Tool    │
                    └───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼─────┐         ┌────▼─────┐         ┌────▼─────┐
   │ Backend  │         │ Frontend │         │  Shared  │
   │ NEW      │         │ NEW      │         │ EXISTING │
   └──────────┘         └──────────┘         └──────────┘
   - api/ghl.py         - pages/Ghl.tsx      - FileUpload
   - models/ghl.py      - Sidebar update     - DataTable
   - services/ghl/      - App.tsx route      - export_utils
     - transform.py                          - ingestion
```

### File Structure

```
toolbox/
├── backend/app/
│   ├── main.py                         # MODIFY: Add ghl_router
│   ├── api/
│   │   └── ghl.py                      # NEW: GHL API routes
│   ├── models/
│   │   └── ghl.py                      # NEW: Pydantic models
│   └── services/
│       └── ghl/
│           ├── __init__.py             # NEW: Service exports
│           ├── transform_service.py    # NEW: CSV transformation logic
│           └── export_service.py       # NEW: Export CSV with transforms applied
├── frontend/src/
│   ├── App.tsx                         # MODIFY: Add /ghl route
│   ├── components/
│   │   └── Sidebar.tsx                 # MODIFY: Add GHL nav item
│   └── pages/
│       └── Ghl.tsx                     # NEW: GHL tool page
```

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **api/ghl.py** | HTTP routes, request validation, response formatting | transform_service, export_service, ingestion |
| **models/ghl.py** | Pydantic models for requests/responses | api/ghl.py |
| **services/ghl/transform_service.py** | CSV parsing, column transforms, JSON extraction | models/ghl.py, pandas |
| **services/ghl/export_service.py** | Generate cleaned CSV with transforms | transform_service, shared/export_utils |
| **pages/Ghl.tsx** | UI for upload, preview, filter, export | api/ghl.py (via fetch), DataTable, FileUpload |

## Data Flow

### Upload → Transform → Preview → Export

```
1. User uploads Mineral export CSV via FileUpload component
   └─> POST /api/ghl/upload

2. Backend validates CSV (ingestion.validate_upload)
   └─> transform_service.parse_csv()
   └─> Returns structured rows + transformation preview

3. Frontend displays transformed data in DataTable
   └─> User reviews changes (title-case, campaign extraction, phone mapping)

4. User clicks export
   └─> POST /api/ghl/export/csv
   └─> export_service.to_csv()
   └─> Returns cleaned CSV ready for GHL import
```

### Transform Pipeline Structure

The `transform_service.py` implements a **pipeline pattern** where each transform is a discrete function:

```python
def transform_row(row: dict) -> GhlContactRow:
    """Apply all transforms to a single Mineral export row."""
    return GhlContactRow(
        full_name=title_case_transform(row.get("Full Name", "")),
        first_name=title_case_transform(row.get("First Name", "")),
        last_name=title_case_transform(row.get("Last Name", "")),
        campaign_name=extract_campaign_unit(row.get("Campaign Name", "")),
        phone=map_phone(row.get("Phone 1", "")),
        contact_owner=ensure_contact_owner(row.get("Contact Owner", "")),
        # ... all other columns with transforms applied
    )
```

**Transform functions:**
- `title_case_transform(value: str) -> str` — Title-case ALL CAPS text fields
- `extract_campaign_unit(json_str: str) -> str` — Parse JSON array, extract unit name
- `map_phone(phone1: str) -> str` — Create primary Phone column from Phone 1
- `ensure_contact_owner(value: str) -> str` — Keep if present, add blank if missing

## Patterns to Follow

### Backend Patterns (Consistent with Extract/Title/Proration/Revenue)

1. **API Router Structure** (`api/ghl.py`)
   ```python
   from __future__ import annotations

   from fastapi import APIRouter, UploadFile, File, HTTPException
   from app.core.ingestion import validate_upload, persist_job_result, file_response
   from app.models.ghl import GhlUploadResponse, GhlExportRequest
   from app.services.ghl.transform_service import parse_and_transform_csv
   from app.services.ghl.export_service import to_csv

   router = APIRouter()

   @router.post("/upload", response_model=GhlUploadResponse)
   async def upload_csv(file: UploadFile = File(...)):
       file_bytes = await validate_upload(file, allowed_extensions=[".csv"])
       result = parse_and_transform_csv(file_bytes, file.filename)
       result.job_id = await persist_job_result(...)
       return GhlUploadResponse(message="Success", result=result)

   @router.post("/export/csv")
   async def export_csv(request: GhlExportRequest):
       csv_bytes = to_csv(request.rows)
       return file_response(csv_bytes, f"{request.filename}.csv")
   ```

2. **Pydantic Models** (`models/ghl.py`)
   ```python
   from pydantic import BaseModel, Field

   class GhlContactRow(BaseModel):
       """A single contact row after transformation."""
       full_name: str = Field(..., description="Title-cased full name")
       first_name: str = Field(default="", description="Title-cased first name")
       last_name: str = Field(default="", description="Title-cased last name")
       campaign_name: str = Field(default="", description="Extracted campaign unit name")
       phone: str = Field(default="", description="Primary phone from Phone 1")
       contact_owner: str = Field(default="", description="Contact owner (kept or blank)")
       # ... all other columns

   class GhlTransformResult(BaseModel):
       """Result of transforming Mineral export CSV."""
       success: bool
       rows: list[GhlContactRow] = Field(default_factory=list)
       total_count: int = Field(default=0)
       source_filename: str | None = None
       job_id: str | None = None

   class GhlUploadResponse(BaseModel):
       message: str
       result: GhlTransformResult | None = None

   class GhlExportRequest(BaseModel):
       rows: list[GhlContactRow]
       filename: str = Field(default="ghl_export")
   ```

3. **Service Layer** (`services/ghl/transform_service.py`)
   ```python
   from __future__ import annotations

   import json
   import pandas as pd
   from app.models.ghl import GhlContactRow, GhlTransformResult

   def parse_and_transform_csv(file_bytes: bytes, filename: str) -> GhlTransformResult:
       """Parse Mineral CSV and apply all transforms."""
       df = pd.read_csv(io.BytesIO(file_bytes))
       rows = [transform_row(row) for _, row in df.iterrows()]
       return GhlTransformResult(
           success=True,
           rows=rows,
           total_count=len(rows),
           source_filename=filename,
       )

   def transform_row(row: pd.Series) -> GhlContactRow:
       """Apply transforms to a single row."""
       # Implementation here

   def title_case_transform(value: str) -> str:
       """Convert ALL CAPS to Title Case."""
       if not value or not value.isupper():
           return value
       return value.title()

   def extract_campaign_unit(json_str: str) -> str:
       """Extract campaign unit name from JSON array string."""
       try:
           campaigns = json.loads(json_str)
           if isinstance(campaigns, list) and len(campaigns) > 0:
               return campaigns[0].get("unit_name", "")
       except (json.JSONDecodeError, TypeError, KeyError):
           pass
       return ""

   def map_phone(phone1: str) -> str:
       """Map Phone 1 to primary Phone column."""
       return phone1 if phone1 else ""

   def ensure_contact_owner(value: str) -> str:
       """Keep if present, add blank if missing."""
       return value if value else ""
   ```

4. **Export Service** (`services/ghl/export_service.py`)
   ```python
   from __future__ import annotations

   import pandas as pd
   from app.models.ghl import GhlContactRow
   from app.services.shared.export_utils import dataframe_to_csv_bytes

   def to_csv(rows: list[GhlContactRow]) -> bytes:
       """Convert transformed rows to CSV bytes."""
       df = pd.DataFrame([row.model_dump() for row in rows])
       return dataframe_to_csv_bytes(df)
   ```

### Frontend Patterns (Consistent with Extract/Title/Proration/Revenue)

1. **Page Structure** (`pages/Ghl.tsx`)
   ```typescript
   import { useState } from 'react'
   import { FileUpload, DataTable, Modal } from '../components'
   import { Download, Upload } from 'lucide-react'

   interface GhlContactRow {
     full_name: string
     first_name: string
     last_name: string
     campaign_name: string
     phone: string
     contact_owner: string
     // ... all other fields
   }

   interface GhlTransformResult {
     success: boolean
     rows: GhlContactRow[]
     total_count: number
     source_filename?: string
     job_id?: string
   }

   export default function Ghl() {
     const [result, setResult] = useState<GhlTransformResult | null>(null)
     const [isProcessing, setIsProcessing] = useState(false)
     const [error, setError] = useState<string | null>(null)

     const handleFilesSelected = async (files: File[]) => {
       // Upload to /api/ghl/upload
     }

     const handleExport = async () => {
       // Export via /api/ghl/export/csv
     }

     return (
       <div className="space-y-6">
         {/* Header */}
         {/* Upload Section with FileUpload */}
         {/* Results Preview with DataTable */}
         {/* Export Button */}
       </div>
     )
   }
   ```

2. **Routing** (`App.tsx`)
   ```typescript
   import Ghl from './pages/Ghl'

   // Inside Routes:
   <Route path="ghl" element={<Ghl />} />
   ```

3. **Navigation** (`Sidebar.tsx`)
   ```typescript
   import { FileCode } from 'lucide-react'

   const navGroups: NavGroup[] = [
     {
       id: 'tools',
       label: 'Tools',
       icon: Wrench,
       items: [
         { name: 'Extract', path: '/extract', icon: FileSearch },
         { name: 'Title', path: '/title', icon: FileText },
         { name: 'Proration', path: '/proration', icon: Calculator },
         { name: 'Revenue', path: '/revenue', icon: DollarSign },
         { name: 'GHL Prep', path: '/ghl', icon: FileCode },  // NEW
       ],
     },
   ]
   ```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Tight Coupling to Mineral Format
**What goes wrong:** Hardcoding Mineral column names directly in transform logic makes it brittle.
**Why bad:** If Mineral export format changes, breaks the entire tool.
**Instead:** Define expected columns as constants at top of transform_service.py, validate on upload.

### Anti-Pattern 2: In-Place DataFrame Mutation
**What goes wrong:** Mutating pandas DataFrame rows during iteration causes unpredictable behavior.
**Why bad:** DataFrame mutation during iteration is not guaranteed to work correctly.
**Instead:** Build new list of transformed rows, then create DataFrame from list.

### Anti-Pattern 3: Frontend CSV Parsing
**What goes wrong:** Parsing CSV in browser (e.g., with PapaParse) duplicates transform logic.
**Why bad:** Transform logic should live in one place (backend), not duplicated across layers.
**Instead:** Backend does all parsing and transformation, frontend only displays results.

### Anti-Pattern 4: Lossy Transforms
**What goes wrong:** Applying transforms that lose original data (e.g., overwriting columns).
**Why bad:** User can't undo transforms if they don't like the result.
**Instead:** Either preserve original + show transformed, or make transforms deterministic and reversible.

## Scalability Considerations

| Concern | At 100 rows | At 10K rows | At 100K rows |
|---------|-------------|-------------|--------------|
| Memory | Negligible | Load CSV into pandas, transform in memory | Consider chunked processing if CSV > 50MB |
| Processing Time | <1s | ~5-10s | ~1-2 min, consider async job queue |
| Preview Display | Show all rows | Paginate with DataTable (10-50 per page) | Paginate + add search/filter |
| Firestore Persistence | Batch write 100 rows | Batch write 10K rows in 20 batches (500/batch) | Consider skipping Firestore, only persist job metadata |

**Current approach:** Synchronous processing is fine for typical Mineral exports (100-1000 rows). If CSVs grow to 10K+ rows, consider adding background job support similar to RRC data pipeline.

## New vs Modified Files

### NEW Files (7 total)

| File | Purpose | Lines (est) |
|------|---------|-------------|
| `backend/app/api/ghl.py` | API routes for upload/export | ~100 |
| `backend/app/models/ghl.py` | Pydantic models | ~80 |
| `backend/app/services/ghl/__init__.py` | Service exports | ~5 |
| `backend/app/services/ghl/transform_service.py` | CSV parsing + transforms | ~150 |
| `backend/app/services/ghl/export_service.py` | Export to CSV | ~30 |
| `frontend/src/pages/Ghl.tsx` | GHL tool page | ~400 |
| `.planning/research/ARCHITECTURE-GHL.md` | This file | ~600 |

**Total new code:** ~1,365 lines

### MODIFIED Files (3 total)

| File | Change | Impact |
|------|--------|--------|
| `backend/app/main.py` | Add `ghl_router` import + include | +3 lines |
| `frontend/src/App.tsx` | Add `/ghl` route | +2 lines |
| `frontend/src/components/Sidebar.tsx` | Add GHL nav item to tools group | +1 line |

**Total modified lines:** ~6 lines (minimal integration points)

## Build Order (Dependencies)

1. **Backend Models** (`models/ghl.py`)
   - No dependencies, defines data contracts
   - Can be built and tested in isolation

2. **Backend Transform Service** (`services/ghl/transform_service.py`)
   - Depends on: `models/ghl.py`
   - Can be unit tested with sample CSV data

3. **Backend Export Service** (`services/ghl/export_service.py`)
   - Depends on: `models/ghl.py`, `shared/export_utils.py`
   - Can be unit tested with sample rows

4. **Backend API Routes** (`api/ghl.py`)
   - Depends on: `models/ghl.py`, `transform_service.py`, `export_service.py`
   - Requires `main.py` update to register router

5. **Frontend Page** (`pages/Ghl.tsx`)
   - Depends on: Backend API routes being registered
   - Can be developed with mock API responses

6. **Frontend Integration** (`App.tsx`, `Sidebar.tsx`)
   - Depends on: `pages/Ghl.tsx` existing
   - Final step: wire up navigation

**Recommended order:** Backend (1→2→3→4) → Frontend (5→6)

**Critical path:** Transform service → API routes → Frontend page

## Testing Strategy

### Backend Tests (pytest)

```python
# tests/test_ghl_transform.py
def test_title_case_transform():
    assert title_case_transform("JOHN DOE") == "John Doe"
    assert title_case_transform("John Doe") == "John Doe"  # no-op

def test_extract_campaign_unit():
    json_str = '[{"unit_name": "ABC-123", "status": "active"}]'
    assert extract_campaign_unit(json_str) == "ABC-123"

def test_transform_row():
    row = pd.Series({
        "Full Name": "JOHN DOE",
        "Campaign Name": '[{"unit_name": "Unit-1"}]',
        "Phone 1": "555-1234",
    })
    result = transform_row(row)
    assert result.full_name == "John Doe"
    assert result.campaign_name == "Unit-1"
    assert result.phone == "555-1234"
```

### Frontend Tests (Manual QA Checklist)

- [ ] Upload valid Mineral CSV → displays transformed preview
- [ ] Upload invalid CSV → shows error message
- [ ] Preview shows title-cased names (ALL CAPS → Title Case)
- [ ] Preview shows extracted campaign names (not full JSON)
- [ ] Preview shows Phone column populated from Phone 1
- [ ] Export button generates CSV download
- [ ] Downloaded CSV opens in Excel without errors
- [ ] Downloaded CSV has correct column headers for GHL import

## Integration Verification Checklist

- [ ] `backend/app/main.py` includes `ghl_router` with prefix `/api/ghl`
- [ ] Health check endpoint `GET /api/ghl/health` returns 200
- [ ] Upload endpoint `POST /api/ghl/upload` accepts CSV files
- [ ] Export endpoint `POST /api/ghl/export/csv` returns CSV download
- [ ] Frontend route `/ghl` renders Ghl.tsx page
- [ ] Sidebar shows "GHL Prep" nav item in Tools group
- [ ] Clicking sidebar nav navigates to `/ghl` route
- [ ] API proxy forwards `/api/ghl` requests to backend (Vite dev mode)
- [ ] Production build serves GHL page without 404
- [ ] Firestore job persistence works (optional, non-blocking)

## Sources

- Existing codebase patterns (`api/extract.py`, `services/extract/export_service.py`, `pages/Extract.tsx`)
- FastAPI documentation for async routes and file uploads
- Pandas documentation for DataFrame operations
- React + TypeScript patterns from existing pages
- Pydantic v2 documentation for model validation

**Confidence Level:** HIGH — All patterns are well-established in the existing codebase. No new architectural decisions required. GHL Prep is a straightforward CSV-to-CSV transform tool following the exact same patterns as Extract and Title tools.
