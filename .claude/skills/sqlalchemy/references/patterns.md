# SQLAlchemy Patterns Reference

## Contents
- Model Definition (SQLAlchemy 2.x)
- Enum Columns
- JSONB and PostgreSQL-Specific Types
- Relationships
- Query Patterns
- Anti-Patterns

---

## Model Definition (SQLAlchemy 2.x)

### WARNING: Never Use Legacy `Column()` Style

**The Problem:**

```python
# BAD - SQLAlchemy 1.x legacy style
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    status = Column(String, default="pending")
    options = Column(JSON, default={})  # Also has mutable default bug
```

**Why This Breaks:**
1. `Column()` with bare `default={}` creates a shared mutable object across ALL instances
2. `declarative_base()` is deprecated in SQLAlchemy 2.x — use `DeclarativeBase`
3. No type annotations means no IDE support or mypy checking

**The Fix:**

```python
# GOOD - SQLAlchemy 2.x Mapped style (from db_models.py)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    options: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # factory, not {}
```

**Key differences:** `Mapped[T]` annotation provides type safety, `default=dict` is a callable (new dict per instance), `DeclarativeBase` is the 2.x base class.

### Optional vs Required Fields

```python
# Required field — Mapped[str] with no Optional
email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

# Optional field — Mapped[Optional[str]] with nullable=True (default)
display_name: Mapped[Optional[str]] = mapped_column(String(255))

# Optional with explicit nullable for clarity
error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

---

## Enum Columns

### Python Enum → PostgreSQL Enum

```python
# BAD - String column with no enforcement
class Job(Base):
    status = Column(String)  # anything goes

# GOOD - Enum column with Python enum validation (from db_models.py)
from enum import Enum as PyEnum
from sqlalchemy import Enum

class JobStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    tool: Mapped[ToolType] = mapped_column(Enum(ToolType), index=True)
```

Use `str, PyEnum` so values serialize to strings in JSON responses without extra config. See the **pydantic** skill for matching Pydantic models.

---

## JSONB and PostgreSQL-Specific Types

### When to Use JSONB

```python
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Job(Base):
    __tablename__ = "jobs"

    # UUID as string — consistent with Firestore doc IDs
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))

    # JSONB for flexible structured data
    options: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)   # processing options
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)                # RRC raw CSV row
    errors: Mapped[Optional[list]] = mapped_column(JSONB, default=list)    # error list
```

JSONB is queryable (PostgreSQL `->` operators) and indexed. Use it for:
- Processing options that vary per job
- Raw external data (RRC CSV rows) where schema is not fixed
- Arrays of simple values (error messages)

**Do NOT use JSONB** for data you need to filter/sort on — add a proper column instead.

---

## Relationships

### One-to-Many with Cascade Delete

```python
# Parent (from db_models.py Job model)
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, ...)

    extract_entries: Mapped[list["ExtractEntry"]] = relationship(
        "ExtractEntry", back_populates="job", cascade="all, delete-orphan"
    )

# Child
class ExtractEntry(Base):
    __tablename__ = "extract_entries"
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), index=True)
    job: Mapped["Job"] = relationship("Job", back_populates="extract_entries")
```

Always add `index=True` to foreign key columns — every FK is a potential query filter.

### Nested Eager Loading

```python
# From db_service.get_job_with_entries — load two levels deep
result = await db.execute(
    select(Job)
    .where(Job.id == job_id)
    .options(
        selectinload(Job.extract_entries),
        selectinload(Job.title_entries),
        selectinload(Job.revenue_statements).selectinload(RevenueStatement.rows),
    )
)
```

### WARNING: Lazy Loading in Async Context

**The Problem:**

```python
# BAD - triggers implicit lazy load
job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
entries = job.extract_entries  # MissingGreenlet error in async context!
```

**Why This Breaks:**
1. Async SQLAlchemy cannot execute implicit I/O outside an active session
2. Raises `sqlalchemy.exc.MissingGreenlet` — the relationship access triggers a sync query
3. No warning at model definition time — fails at runtime

**The Fix:**

```python
# GOOD - always use selectinload before accessing relationships
result = await db.execute(
    select(Job).where(Job.id == job_id).options(selectinload(Job.extract_entries))
)
job = result.scalar_one()
entries = job.extract_entries  # safe — already loaded
```

---

## Query Patterns

### Paginated listing with ordering

```python
# From db_service.get_user_jobs
query = select(Job).where(Job.user_id == user_id)
if tool:
    query = query.where(Job.tool == tool)
query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
result = await db.execute(query)
return result.scalars().all()
```

### Aggregation with func

```python
from sqlalchemy import func

# Scalar count
count_result = await db.execute(select(func.count(RRCOilProration.id)))
count = count_result.scalar() or 0

# Max timestamp
latest_result = await db.execute(select(func.max(RRCOilProration.updated_at)))
latest = latest_result.scalar()

# Grouped aggregation
result = await db.execute(
    select(Job.tool, func.count(Job.id).label("total_jobs"), func.sum(Job.total_count).label("total_entries"))
    .group_by(Job.tool)
)
```

### `flush()` vs `commit()`

```python
# flush() — write to DB within transaction, get auto-IDs, don't commit
db.add(statement)
await db.flush()        # statement.id is now populated
for row_data in rows:
    row = RevenueRow(statement_id=statement.id, ...)  # uses flushed id
    db.add(row)
await db.flush()
# commit() happens automatically in get_db() when response returns
```

NEVER call `await db.commit()` inside service functions. Commit is owned by `get_db()`. Only use `flush()` to materialize IDs mid-transaction.
