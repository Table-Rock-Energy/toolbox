# SQLAlchemy Workflows Reference

## Contents
- Enabling the Optional DB
- Adding a New Model
- Adding a Service Function
- Testing with Async SQLite
- Troubleshooting Common Errors

---

## Enabling the Optional DB

PostgreSQL is disabled by default. Enable it for local development:

```bash
# docker-compose.yml already includes a postgres service
make docker-up

# Set env vars (backend/.env or shell)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox
DATABASE_ENABLED=true
```

The `init_db()` function in `core/database.py` creates tables on startup via `Base.metadata.create_all`. This is fine for development — use Alembic migrations for production schema changes.

**In production (Cloud Run):** Firestore is used — do NOT enable `DATABASE_ENABLED=true` in production unless you've set up Cloud SQL. See the **firestore** skill for the primary DB patterns.

---

## Adding a New Model

Checklist:
- [ ] Add model class to `backend/app/models/db_models.py`
- [ ] Use `Mapped[T]`/`mapped_column` (2.x style) — never `Column()`
- [ ] Index FK columns and frequently filtered fields
- [ ] Add relationship on parent with `cascade="all, delete-orphan"`
- [ ] Import model in `init_db()` to register with Base metadata
- [ ] Add CRUD functions to `backend/app/services/db_service.py`

### Model template

```python
# In db_models.py
class NewToolEntry(Base):
    """Entry for new tool — linked to Job."""

    __tablename__ = "new_tool_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id"), index=True
    )

    # Data fields
    primary_field: Mapped[str] = mapped_column(String(500))
    optional_field: Mapped[Optional[str]] = mapped_column(String(255))
    flag: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Timestamps only if needed — job already has created_at
    job: Mapped["Job"] = relationship("Job", back_populates="new_tool_entries")

    def __repr__(self) -> str:
        return f"<NewToolEntry {self.primary_field}>"
```

Then add the relationship on `Job`:

```python
# In the Job class
new_tool_entries: Mapped[list["NewToolEntry"]] = relationship(
    "NewToolEntry", back_populates="job", cascade="all, delete-orphan"
)
```

And register in `init_db()`:

```python
# core/database.py init_db()
async def init_db() -> None:
    async with engine.begin() as conn:
        from app.models import db_models  # noqa: F401  — registers all models
        await conn.run_sync(Base.metadata.create_all)
```

---

## Adding a Service Function

All DB functions take `AsyncSession` as first arg and use `flush()` (not `commit()`).

```python
# In db_service.py
async def save_new_tool_entries(
    db: AsyncSession,
    job_id: str,
    entries: list[dict],
) -> int:
    """Save new tool entries for a job. Returns count saved."""
    count = 0
    for entry_data in entries:
        entry = NewToolEntry(
            job_id=job_id,
            primary_field=entry_data.get("primary_field", ""),
            optional_field=entry_data.get("optional_field"),
            flag=entry_data.get("flag", False),
        )
        db.add(entry)
        count += 1
    await db.flush()
    logger.info(f"Saved {count} new tool entries for job {job_id}")
    return count


async def get_new_tool_entries(
    db: AsyncSession,
    job_id: str,
) -> Sequence[NewToolEntry]:
    """Get entries for a job."""
    result = await db.execute(
        select(NewToolEntry).where(NewToolEntry.job_id == job_id)
    )
    return result.scalars().all()
```

### Wiring into a route

```python
# In api/new_tool.py
@router.post("/upload")
async def upload(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    if not settings.database_enabled:
        # Fall through to Firestore path
        ...

    job = await db_service.create_job(db, tool=ToolType.EXTRACT, source_filename=file.filename)
    entries = process_file(file)  # your service logic
    await db_service.save_new_tool_entries(db, job.id, entries)
    await db_service.update_job_status(db, job.id, JobStatus.COMPLETED, total_count=len(entries))
    # db commits automatically when get_db() exits
    return {"job_id": job.id, "count": len(entries)}
```

---

## Testing with Async SQLite

Use SQLite in-memory for tests — no PostgreSQL needed. Note: JSONB and UUID(as_uuid=False) are PostgreSQL-specific. For tests, swap to `JSON` and `String` if tests fail on SQLite type errors.

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.db_models import Base

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()
```

```python
# tests/test_db_service.py
import pytest
from app.services import db_service
from app.models.db_models import ToolType, JobStatus

@pytest.mark.asyncio
async def test_create_and_update_job(db_session):
    job = await db_service.create_job(
        db_session, tool=ToolType.EXTRACT, source_filename="test.pdf"
    )
    assert job.status == JobStatus.PENDING

    await db_session.flush()  # materialize for subsequent queries

    updated = await db_service.update_job_status(
        db_session, job.id, JobStatus.COMPLETED, total_count=5, success_count=5
    )
    assert updated.status == JobStatus.COMPLETED
    assert updated.total_count == 5
```

Iterate-until-pass:
1. Run: `cd backend && pytest -v tests/test_db_service.py`
2. Fix missing `await`, wrong field names, or type mismatches
3. Repeat until all pass

---

## Troubleshooting Common Errors

### `MissingGreenlet: greenlet_spawn has not been called`

Cause: Accessing a relationship outside an active session, or lazy loading in async context.

Fix: Add `selectinload(Model.relationship)` to the query before accessing it.

### `sqlalchemy.exc.InterfaceError: (asyncpg.exceptions._base.InterfaceError) cannot perform operation: another operation is in progress`

Cause: Concurrent queries on the same session. SQLAlchemy async sessions are NOT thread-safe.

Fix: One session per request (guaranteed by `get_db()` dependency injection). Never share a session across concurrent tasks.

### `AttributeError: 'coroutine' object has no attribute 'scalars'`

Cause: Missing `await` on `db.execute(...)`.

Fix: `result = await db.execute(select(...))` — every DB call must be awaited.

### `sqlalchemy.exc.InvalidRequestError: Session is already flushing`

Cause: Calling `await db.flush()` inside an event listener or inside another flush.

Fix: Remove nested flush. Let the outermost flush or commit handle it.

### Tables not created / `relation does not exist`

Cause: Model not imported before `Base.metadata.create_all` runs.

Fix: In `init_db()`, ensure `from app.models import db_models  # noqa: F401` runs before `create_all`. The import registers all models with `Base.metadata`.
