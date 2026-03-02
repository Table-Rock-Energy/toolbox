# Python Types Reference

## Contents
- Pydantic Models
- Enum Patterns
- Type Hints & Annotations
- Optional vs None
- Generic Types
- Model Validation

---

## Pydantic Models

All request/response models use **Pydantic BaseModel** with `Field(...)` descriptors.

### DO: Field Descriptors with Validation

```python
# backend/app/models/extract.py
from pydantic import BaseModel, Field
from enum import Enum

class EntityType(str, Enum):
    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    LLC = "LLC"
    CORPORATION = "Corporation"

class PartyEntry(BaseModel):
    name: str = Field(..., description="Full party name", min_length=1)
    entity_type: EntityType = Field(..., description="Entity classification")
    address: str | None = Field(None, description="Mailing address")
    ownership_pct: float = Field(..., ge=0, le=100, description="Ownership percentage")
    
    class Config:
        use_enum_values = True  # Serialize enums as strings
```

**Why:** `Field(...)` requires the field (no default). `Field(None, ...)` makes it optional. Validation runs automatically.

### DON'T: Plain Dataclasses or TypedDict

```python
# BAD - No validation, no serialization, manual type checking
from dataclasses import dataclass

@dataclass
class PartyEntry:
    name: str
    entity_type: str  # String instead of enum, no validation
    ownership_pct: float  # Could be negative or >100
```

**Why This Breaks:** Dataclasses don't validate. Pydantic catches invalid data at request time with clear error messages.

---

## Enum Patterns

### DO: str, Enum for String Enums

```python
# backend/app/models/proration.py
from enum import Enum

class WellType(str, Enum):
    OIL = "Oil"
    GAS = "Gas"
    BOTH = "Both"

# Serializes as "Oil", not "WellType.OIL"
row = MineralHolderRow(well_type=WellType.OIL)
assert row.model_dump()["well_type"] == "Oil"
```

**Why:** `str, Enum` inherits from both `str` and `Enum`, so values serialize as strings. Plain `Enum` serializes as enum objects.

### DON'T: SCREAMING_SNAKE Enum Values for User-Facing Data

```python
# BAD - Ugly API responses
class EntityType(Enum):
    INDIVIDUAL = "INDIVIDUAL"  # Returns "INDIVIDUAL" in JSON
    TRUST = "TRUST"
```

**Why This Breaks:** Enum values appear in API responses. Use PascalCase strings (`"Individual"`) for readability.

**The Fix:** `EntityType.INDIVIDUAL = "Individual"` (PascalCase value, SCREAMING_SNAKE name)

---

## Type Hints & Annotations

### DO: Modern Union Syntax with |

```python
# backend/app/models/revenue.py
from __future__ import annotations

class RevenueStatement(BaseModel):
    pdf_filename: str
    total_revenue: float | None = None  # Optional field
    line_items: list[dict] = []  # Empty list default
    processing_errors: list[str] | None = None
```

**Why:** `str | None` is Python 3.10+ syntax. `from __future__ import annotations` makes it work in 3.9.

### DON'T: Optional[] Everywhere

```python
# BAD - Verbose, outdated
from typing import Optional, List, Dict

class RevenueStatement(BaseModel):
    pdf_filename: str
    total_revenue: Optional[float] = None
    line_items: List[Dict] = []
```

**Why This Breaks:** `Optional[T]` is verbose. Use `T | None` instead. Same for `List` → `list`, `Dict` → `dict`.

---

## Optional vs None

### DO: Distinguish Missing vs Null

```python
from pydantic import BaseModel

class UpdateRequest(BaseModel):
    name: str | None = None  # Can be null to clear
    email: str | None = None

# Update only provided fields
def update_user(user_id: str, updates: UpdateRequest):
    data = updates.model_dump(exclude_unset=True)
    # data = {"name": "John"} if only name provided
    db.update(user_id, data)
```

**Why:** `exclude_unset=True` omits fields not provided in JSON. Allows partial updates.

### WARNING: Default Mutable Arguments

**The Problem:**

```python
# BAD - Shared mutable default, causes state leaks
def process_rows(rows: list[dict], errors: list[str] = []):
    errors.append("Processing started")  # MUTATES SHARED LIST
    return errors

# All calls share the same list!
result1 = process_rows([])  # ["Processing started"]
result2 = process_rows([])  # ["Processing started", "Processing started"]
```

**Why This Breaks:** Default arguments are evaluated once at function definition. Mutable defaults (lists, dicts) are shared across all calls.

**The Fix:**

```python
# GOOD - Create new list per call
def process_rows(rows: list[dict], errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []
    errors.append("Processing started")
    return errors
```

---

## Generic Types

### DO: Generic DataTable Props

```python
from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

# Usage
response = PaginatedResponse[PartyEntry](
    items=[entry1, entry2],
    total=100,
    page=1,
    page_size=20
)
```

**Why:** Generics allow reusable models with type safety. IDE autocomplete knows `response.items[0]` is a `PartyEntry`.

---

## Model Validation

### DO: Custom Validators with @field_validator

```python
from pydantic import BaseModel, field_validator

class MineralHolderRow(BaseModel):
    name: str
    nra: float
    
    @field_validator("nra")
    @classmethod
    def nra_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("NRA must be positive")
        return v
```

**Why:** Runs validation automatically on model creation. Clear error messages for API clients.

### DON'T: Manual Validation in Route Handlers

```python
# BAD - Scattered validation logic
@router.post("/upload")
async def upload(data: MineralHolderRow):
    if data.nra <= 0:
        raise HTTPException(400, "NRA must be positive")
    # Business logic...
```

**Why This Breaks:** Validation should be in the model. Keeps route handlers focused on business logic.