---
name: pydantic
description: |
  Defines Pydantic models, validation, and Settings-based configuration for FastAPI backend with Firestore integration.
  Use when: creating API request/response models, validating data, managing environment-based configuration, defining database schemas, or enforring type safety at runtime.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Pydantic Skill

This project uses Pydantic 2.x for runtime validation, API contracts in FastAPI endpoints, and Settings-based environment configuration. All models use `Field(...)` descriptors with snake_case fields, and Settings classes use `@property` methods for computed values like `use_gcs`.

## Quick Start

### API Request/Response Models

```python
from pydantic import BaseModel, Field

class PartyEntry(BaseModel):
    """OCC Exhibit A party extraction result."""
    name: str = Field(..., description="Party legal name")
    address: str = Field(..., description="Full mailing address")
    entity_type: str = Field(..., description="Entity classification")
    page_number: int = Field(..., description="Source PDF page")
```

### Settings-Based Configuration

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gcs_bucket_name: str = Field(default="table-rock-tools-storage", description="GCS bucket")
    
    @property
    def use_gcs(self) -> bool:
        """Computed property - GCS enabled if bucket name set."""
        return bool(self.gcs_bucket_name)
    
    class Config:
        env_file = ".env"
```

### Enum with String Values

```python
from enum import Enum

class EntityType(str, Enum):
    """Entity type classification - use str for JSON serialization."""
    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    CORPORATION = "Corporation"
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `Field(...)` | Required field with description | `Field(..., description="Party name")` |
| `Field(default, ...)` | Optional field with default | `Field(default=None, description="Optional ID")` |
| `str, Enum` | String-serializable enum | `class Status(str, Enum): PENDING = "pending"` |
| `@property` | Computed Settings values | `@property def use_gcs(self) -> bool: ...` |
| `model_dump()` | Serialize to dict | `party.model_dump()` |
| `model_validate()` | Validate external data | `PartyEntry.model_validate(data)` |

## Common Patterns

### API Model with Nested Structure

**When:** FastAPI endpoints returning structured data with metadata.

```python
from pydantic import BaseModel, Field

class ProcessingResult(BaseModel):
    """Response from title opinion processing."""
    entries: list[OwnerEntry] = Field(..., description="Parsed owner entries")
    total_count: int = Field(..., description="Total entries processed")
    duplicate_count: int = Field(..., description="Flagged duplicates")
    timestamp: str = Field(..., description="ISO timestamp")
```

### Settings with Lazy Firebase Init

**When:** Environment-based configuration with optional services.

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    environment: str = Field(default="development", description="Deployment environment")
    firestore_enabled: bool = Field(default=True, description="Enable Firestore")
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

## WARNING: Common Anti-Patterns

See [patterns.md](references/patterns.md) for anti-patterns including mutable defaults, missing Field descriptions, and dict over model_dump().

## Related Skills

- **fastapi** - Uses Pydantic models for request/response validation
- **python** - Core language patterns and async/await usage
- **firestore** - Models stored/retrieved from Firestore collections
- **pytest** - Testing Pydantic validation logic

## Documentation Resources

> Fetch latest Pydantic documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` with query "pydantic documentation"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source repositories
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Recommended Queries:**
- "pydantic v2 field validation"
- "pydantic settings environment variables"
- "pydantic model serialization"