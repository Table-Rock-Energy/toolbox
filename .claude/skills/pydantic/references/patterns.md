# Pydantic Patterns Reference

## Contents
- Field Definitions
- Settings Configuration
- Enums and String Types
- Validation Patterns
- Anti-Patterns

---

## Field Definitions

### Required Fields with Descriptions

**ALWAYS use `Field(...)` for required fields with descriptions.** FastAPI auto-generates OpenAPI docs from these.

```python
# GOOD - Clear contract for API consumers
class PartyEntry(BaseModel):
    name: str = Field(..., description="Party legal name from Exhibit A")
    address: str = Field(..., description="Complete mailing address")
    entity_type: str = Field(..., description="Entity classification (Individual, Trust, etc)")
    page_number: int = Field(..., description="Source PDF page number")
```

```python
# BAD - No descriptions, poor API documentation
class PartyEntry(BaseModel):
    name: str
    address: str
    entity_type: str
    page_number: int
```

**Why this matters:** The `description` becomes Swagger UI help text at `/docs`. Without it, API consumers don't understand field purpose.

### Optional Fields with Defaults

**Use `Field(default, description=...)` for optional fields.** Always provide descriptions even for optional fields.

```python
# GOOD - Clear default behavior
class RRCQueryResult(BaseModel):
    lease_number: str = Field(..., description="RRC lease identifier")
    well_count: int = Field(default=0, description="Number of wells on lease")
    last_updated: str | None = Field(default=None, description="ISO timestamp of last update")
```

```python
# BAD - Unclear what None means, no defaults
class RRCQueryResult(BaseModel):
    lease_number: str
    well_count: int | None
    last_updated: str | None
```

**Why this matters:** Explicit defaults make serialization predictable. `well_count=0` is different from `well_count=None` — zero means "no wells found", None means "not checked yet".

---

## Settings Configuration

### Settings with Computed Properties

**Use `@property` for computed configuration values.** NEVER store computed state in database-backed fields.

```python
# GOOD - Computed from bucket name, always in sync
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    gcs_bucket_name: str = Field(default="table-rock-tools-storage", description="GCS bucket")
    gcs_project_id: str = Field(default="tablerockenergy", description="GCP project")

    @property
    def use_gcs(self) -> bool:
        """GCS enabled when bucket name is set."""
        return bool(self.gcs_bucket_name)
```

```python
# BAD - use_gcs can get out of sync with bucket name
class Settings(BaseSettings):
    gcs_bucket_name: str = Field(default="table-rock-tools-storage")
    use_gcs: bool = Field(default=True)  # Can diverge from bucket_name state
```

**Why this breaks:** If someone sets `GCS_BUCKET_NAME=""` but forgets `USE_GCS=false`, you'll try to upload to an empty bucket name. The `@property` pattern makes `use_gcs` always correct.

### Environment Variable Mapping

**Use `model_config = SettingsConfigDict(...)` for automatic environment loading.** Never use `class Config` — that's the Pydantic v1 compat style.

```python
# GOOD - Auto-loads from .env, case-insensitive by default
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox",
        description="PostgreSQL connection string"
    )
    max_upload_size_mb: int = Field(default=50, description="Max file upload size")
```

```python
# BAD - Pydantic v1 compat syntax, avoid in v2 codebases
class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        case_sensitive = False
```

Environment variables `DATABASE_URL` or `database_url` both map to `database_url` field (case-insensitive by default in pydantic-settings).

---

## Enums and String Types

### String-Serializable Enums

**ALWAYS use `str, Enum` for enums in API models.** This makes them JSON-serializable by default.

```python
# GOOD - Serializes to string automatically
from enum import Enum

class EntityType(str, Enum):
    """Entity classification for party extraction."""
    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    CORPORATION = "Corporation"
    LLC = "LLC"
    PARTNERSHIP = "Partnership"

class PartyEntry(BaseModel):
    entity_type: EntityType = Field(..., description="Entity classification")
```

```python
# BAD - Plain Enum won't serialize to JSON without custom encoder
from enum import Enum

class EntityType(Enum):
    INDIVIDUAL = 1
    TRUST = 2
    CORPORATION = 3
```

**Why this breaks:** FastAPI can't serialize `EntityType.INDIVIDUAL` (integer enum) to JSON without a custom JSONEncoder. Using `str, Enum` makes it work automatically.

**When you're tempted:** You might think integer enums save space. They don't — JSON is text-based anyway. String enums are self-documenting in API responses.

---

## Validation Patterns

### Custom Validators

**Use `@field_validator` for field-level validation, `@model_validator` for cross-field checks.**

```python
from pydantic import BaseModel, Field, field_validator, model_validator

class MineralHolderRow(BaseModel):
    lease_number: str = Field(..., description="RRC lease number")
    decimal_interest: float = Field(..., description="Decimal NRA (0.0-1.0)")
    
    @field_validator("decimal_interest")
    @classmethod
    def validate_decimal_range(cls, v: float) -> float:
        """Ensure decimal interest is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Decimal interest must be 0.0-1.0, got {v}")
        return v
    
    @model_validator(mode="after")
    def validate_lease_format(self) -> "MineralHolderRow":
        """Ensure lease number matches RRC format."""
        if not self.lease_number.isdigit():
            raise ValueError(f"Lease number must be numeric: {self.lease_number}")
        return self
```

**Why this matters:** FastAPI runs these validators automatically on request payloads. Invalid data returns 422 Unprocessable Entity with validation errors — no need for manual checks.

---

## Anti-Patterns

### WARNING: Mutable Default Arguments

**The Problem:**

```python
# BAD - List is shared across all instances
class ProcessingResult(BaseModel):
    entries: list[OwnerEntry] = []
```

**Why This Breaks:**
1. **Shared state:** All instances share the same list object
2. **Data leakage:** Appending to one instance affects others
3. **Hard-to-debug:** Mutation happens silently across unrelated requests

**The Fix:**

```python
# GOOD - Use Field with default_factory
class ProcessingResult(BaseModel):
    entries: list[OwnerEntry] = Field(default_factory=list, description="Parsed entries")
```

**When You Might Be Tempted:**
When you want an empty list default. Python's mutable default argument gotcha applies to Pydantic too.

---

### WARNING: Missing Field Descriptions

**The Problem:**

```python
# BAD - No descriptions, poor OpenAPI docs
class RevenueStatement(BaseModel):
    statement_date: str
    total_revenue: float
    operator_name: str
```

**Why This Breaks:**
1. **Unusable API docs:** Swagger UI at `/docs` shows no help text
2. **Integration friction:** External teams don't understand fields
3. **Maintenance burden:** Future developers guess field meanings

**The Fix:**

```python
# GOOD - Self-documenting API
class RevenueStatement(BaseModel):
    statement_date: str = Field(..., description="Statement period end date (ISO format)")
    total_revenue: float = Field(..., description="Total revenue in USD")
    operator_name: str = Field(..., description="Operating company name")
```

**When You Might Be Tempted:**
When prototyping quickly. Add descriptions BEFORE committing — they're harder to add later when you've forgotten context.

---

### WARNING: Using dict() Instead of model_dump()

**The Problem:**

```python
# BAD - Deprecated in Pydantic v2
party_data = party_entry.dict()
```

**Why This Breaks:**
1. **Deprecated:** `dict()` removed in future Pydantic versions
2. **Missing features:** `model_dump()` has exclude/include options
3. **Type hints:** `model_dump()` has better type checking

**The Fix:**

```python
# GOOD - Pydantic v2 standard
party_data = party_entry.model_dump()

# With exclusions
party_data = party_entry.model_dump(exclude={"page_number"})

# As JSON string
party_json = party_entry.model_dump_json()
```

**When You Might Be Tempted:**
When migrating from Pydantic v1 code. Search-and-replace `.dict()` → `.model_dump()` across the codebase.

---

### WARNING: Not Using TYPE_CHECKING for Type Hints

**The Problem:**

```python
# BAD - Imports Firestore client at module load, breaks if not configured
from google.cloud import firestore

class JobRecord(BaseModel):
    user_id: str
    firestore_client: firestore.Client  # Imported at runtime
```

**Why This Breaks:**
1. **Import errors:** Fails if Firestore not configured (local dev)
2. **Slow startup:** Imports heavy libraries even when unused
3. **Circular imports:** Can create dependency cycles

**The Fix:**

```python
# GOOD - Import only for type checking
from __future__ import annotations
from typing import TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from google.cloud import firestore

class JobRecord(BaseModel):
    user_id: str
    # Use string annotation to avoid runtime import
```

**When You Might Be Tempted:**
When type hints require heavy dependencies. Always use TYPE_CHECKING for Firebase, GCS, or other optional services.