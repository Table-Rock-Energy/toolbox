---
name: sqlalchemy
description: |
  Configures SQLAlchemy async engine and ORM models for PostgreSQL (optional fallback DB).
  Use when: implementing PostgreSQL models, setting up async database connections, defining ORM relationships, or debugging database schema issues.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# SQLAlchemy Skill

SQLAlchemy provides optional PostgreSQL support in this project. **Firestore is the primary database** (see **firestore** skill). PostgreSQL via SQLAlchemy is disabled by default (`DATABASE_ENABLED=false`) and only used for local development when explicitly enabled. This skill covers async engine setup, ORM model patterns, and integration with FastAPI.

## Quick Start

### Async Engine Configuration

```python
# toolbox/backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,  # postgresql+asyncpg://...
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### ORM Model Definition

```python
# toolbox/backend/app/models/db_models.py
from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True)
    user_email = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    result_data = Column(Text)  # JSON stored as text
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Async engine | Non-blocking DB operations | `create_async_engine(url, echo=debug)` |
| AsyncSession | Async context for queries | `async with AsyncSessionLocal() as session:` |
| Declarative Base | ORM model inheritance | `class Model(Base): __tablename__ = "table"` |
| pool_pre_ping | Connection health check | Prevents "connection closed" errors |
| expire_on_commit | Keep objects usable post-commit | `expire_on_commit=False` |

## Common Patterns

### Dependency Injection for Sessions

**When:** FastAPI route needs database access

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/api/jobs")
async def create_job(db: AsyncSession = Depends(get_db)):
    job = Job(id=uuid4(), user_email="user@example.com")
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
```

### Conditional Database Usage

**When:** PostgreSQL is optional, fallback to Firestore

```python
from app.core.config import settings

if settings.database_enabled:
    from app.services.db_service import save_to_postgres
    await save_to_postgres(data)
else:
    from app.services.firestore_service import save_to_firestore
    await save_to_firestore(data)
```

## See Also

- [patterns](references/patterns.md) - ORM relationships, migrations, query patterns
- [workflows](references/workflows.md) - Schema setup, testing, migration workflows

## Related Skills

- **pydantic** - Integrates with SQLAlchemy for validation (see Pydantic skill)
- **fastapi** - Dependency injection for sessions (see FastAPI skill)
- **python** - Async/await patterns (see Python skill)
- **firestore** - Primary database (SQLAlchemy is optional fallback)
- **pytest** - Testing async database operations

## Documentation Resources

> Fetch latest SQLAlchemy documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "sqlalchemy"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Recommended Queries:**
- "sqlalchemy async engine setup"
- "sqlalchemy orm relationships"
- "sqlalchemy alembic migrations"