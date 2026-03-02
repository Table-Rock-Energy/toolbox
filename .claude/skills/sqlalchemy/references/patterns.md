# SQLAlchemy Patterns Reference

## Contents
- Engine and Session Configuration
- ORM Model Patterns
- Relationship Definitions
- Query Patterns
- Common Anti-Patterns

---

## Engine and Session Configuration

### Async Engine Setup

```python
# toolbox/backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# GOOD - Connection pooling with health checks
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
)
```

**Why `pool_pre_ping=True`?** Without this, you'll encounter "connection closed" errors after idle periods. The pre-ping checks connection health before each checkout.

**Why `expire_on_commit=False`?** By default, SQLAlchemy expires all objects after commit, requiring a refresh. In async contexts where you immediately return the object, this causes lazy-load errors.

### WARNING: Synchronous Engine in Async Context

**The Problem:**

```python
# BAD - Blocks the event loop
from sqlalchemy import create_engine

engine = create_engine("postgresql://...")  # Synchronous
session = Session(engine)
result = session.execute(select(Job))  # Blocks async runtime
```

**Why This Breaks:**
1. Synchronous I/O blocks FastAPI's async event loop
2. All other requests stall while waiting for database
3. Connection pool deadlocks under concurrent load

**The Fix:**

```python
# GOOD - Non-blocking async operations
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine("postgresql+asyncpg://...")
async with AsyncSessionLocal() as session:
    result = await session.execute(select(Job))
```

**When You Might Be Tempted:** When copying SQLAlchemy 1.x examples or migrating sync code. Always use `asyncpg` driver and async engine.

---

## ORM Model Patterns

### Base Model with Common Fields

```python
# toolbox/backend/app/models/db_models.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True)
    user_email = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    status = Column(String, default="pending")
```

**Index Strategy:** Add indexes on foreign keys and frequently filtered columns (`user_email`, `status`). Missing indexes cause full table scans.

### JSON Columns for Structured Data

```python
from sqlalchemy import Column, JSON

class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"
    
    id = Column(String, primary_key=True)
    result_data = Column(JSON)  # PostgreSQL native JSON
    metadata = Column(JSON, default=dict)
```

**PostgreSQL JSON vs Text:** Use `JSON` type for queryable fields (supports `->` operators). Use `Text` for opaque blobs.

### WARNING: Mutable Default Arguments

**The Problem:**

```python
# BAD - Shared mutable default across all instances
class Job(Base):
    __tablename__ = "jobs"
    tags = Column(JSON, default={})  # Shared dict instance!
```

**Why This Breaks:**
1. All new `Job` instances share the same `{}` object
2. Modifying one instance's tags affects all others
3. Causes data corruption in production

**The Fix:**

```python
# GOOD - Factory function creates new dict per instance
class Job(Base):
    __tablename__ = "jobs"
    tags = Column(JSON, default=lambda: {})  # New dict each time
```

---

## Relationship Definitions

### One-to-Many with Lazy Loading

```python
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True)
    jobs = relationship("Job", back_populates="user", lazy="selectin")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    user_email = Column(String, ForeignKey("users.email"))
    user = relationship("User", back_populates="jobs")
```

**Lazy Loading Options:**
- `lazy="selectin"` - Eager load with separate SELECT (async-safe)
- `lazy="joined"` - JOIN at query time (faster for small datasets)
- `lazy="raise"` - Prevent lazy loads (explicit control)

### WARNING: N+1 Query Problem

**The Problem:**

```python
# BAD - One query per user's jobs
async with AsyncSessionLocal() as session:
    users = await session.execute(select(User))
    for user in users.scalars():
        print(user.jobs)  # Triggers separate SELECT for EACH user
```

**Why This Breaks:**
1. 1 query for users + N queries for jobs = 1+N total queries
2. Scales poorly (100 users = 101 queries)
3. Destroys performance under load

**The Fix:**

```python
# GOOD - Eager load relationships
from sqlalchemy.orm import selectinload

async with AsyncSessionLocal() as session:
    result = await session.execute(
        select(User).options(selectinload(User.jobs))
    )
    users = result.scalars().all()  # All jobs loaded in 2 queries
```

**When You Might Be Tempted:** When iterating over query results without thinking about relationship loading. Always use `selectinload` or `joinedload` for accessed relationships.

---

## Query Patterns

### Basic CRUD Operations

```python
from sqlalchemy import select, update, delete
from app.models.db_models import Job

# Create
async with AsyncSessionLocal() as session:
    job = Job(id="123", user_email="user@example.com", tool_name="extract")
    session.add(job)
    await session.commit()
    await session.refresh(job)

# Read
async with AsyncSessionLocal() as session:
    result = await session.execute(select(Job).where(Job.id == "123"))
    job = result.scalar_one_or_none()

# Update
async with AsyncSessionLocal() as session:
    await session.execute(
        update(Job).where(Job.id == "123").values(status="completed")
    )
    await session.commit()

# Delete
async with AsyncSessionLocal() as session:
    await session.execute(delete(Job).where(Job.id == "123"))
    await session.commit()
```

### Filtering and Ordering

```python
from sqlalchemy import select, and_, or_, desc

# Multiple conditions
result = await session.execute(
    select(Job).where(
        and_(
            Job.user_email == "user@example.com",
            Job.status == "completed"
        )
    )
)

# Ordering and limits
result = await session.execute(
    select(Job)
    .where(Job.tool_name == "extract")
    .order_by(desc(Job.created_at))
    .limit(10)
)
```

### WARNING: Missing `await` on Execute

**The Problem:**

```python
# BAD - Returns coroutine, not result
result = session.execute(select(Job))  # Missing await!
jobs = result.scalars().all()  # TypeError: coroutine is not iterable
```

**Why This Breaks:**
1. `session.execute()` returns a coroutine in async context
2. You get a coroutine object instead of query results
3. Accessing `.scalars()` or `.all()` raises TypeError

**The Fix:**

```python
# GOOD - Await the query execution
result = await session.execute(select(Job))
jobs = result.scalars().all()
```

**When You Might Be Tempted:** When copying sync SQLAlchemy code. Every database operation must be awaited in async context.

---

## Common Anti-Patterns

### WARNING: Session Management Without Context Manager

**The Problem:**

```python
# BAD - Manual session lifecycle, leak risk
session = AsyncSessionLocal()
try:
    result = await session.execute(select(Job))
    await session.commit()
finally:
    await session.close()  # Easy to forget
```

**Why This Breaks:**
1. Exception before `close()` leaks connections
2. Pool exhaustion under load
3. Hard to debug connection leaks

**The Fix:**

```python
# GOOD - Context manager guarantees cleanup
async with AsyncSessionLocal() as session:
    result = await session.execute(select(Job))
    await session.commit()
# Automatically closed on exit
```

### WARNING: Mixing Firestore and PostgreSQL for Same Data

**The Problem:**

```python
# BAD - Dual writes to both databases
await firestore_service.save_job(job_data)
await db_service.save_job(job_data)  # Now you have sync issues
```

**Why This Breaks:**
1. No transaction across both databases
2. Data inconsistency if one write fails
3. Doubles storage costs and maintenance burden

**The Fix:**

```python
# GOOD - Use one database as source of truth
if settings.database_enabled:
    await db_service.save_job(job_data)
else:
    await firestore_service.save_job(job_data)
```

**When You Might Be Tempted:** When "gradually migrating" from Firestore to PostgreSQL. Pick one database per data type and stick with it. This project uses **Firestore as primary** with PostgreSQL as optional local dev DB.