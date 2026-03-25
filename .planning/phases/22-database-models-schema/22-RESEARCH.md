# Phase 22: Database Models & Schema - Research

**Researched:** 2026-03-25
**Domain:** SQLAlchemy models + Alembic migration tooling for PostgreSQL
**Confidence:** HIGH

## Summary

This phase extends the existing 10 SQLAlchemy models in `db_models.py` to cover all Firestore collections, adds auth columns to the User model, and initializes Alembic with the async template. The codebase already has a working async engine, session factory, and `DeclarativeBase` -- this is extension work, not greenfield.

The actual Firestore collection audit reveals **more than 13 collections** -- `ghl_connections`, `rrc_sync_jobs`, and `rrc_metadata` are used outside `firestore_service.py` and were not counted in the original estimate. These need models too, or Phase 25 (DB-05) will have gaps. The phase success criteria call for "all Firestore collections" so they must be included.

**Primary recommendation:** Add 6 new models (AppConfig, UserPreference, RRCCountyStatus, GHLConnection, RRCSyncJob, RRCMetadata) and 5 new columns to User. Initialize Alembic async template pointing at the existing engine. Generate one initial migration covering everything.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked -- infrastructure phase with all choices at Claude's discretion.

### Claude's Discretion
All implementation choices are at Claude's discretion. Key research findings to incorporate:
- PyJWT + pwdlib[bcrypt] for password hashing (FastAPI official recommendation)
- AppConfig as key/JSONB table (replaces Firestore app_config collection)
- UserPreference as user_id FK + JSONB data (replaces Firestore user_preferences collection)
- RRCCountyStatus for county download tracking (replaces Firestore rrc_county_status collection)
- Use Alembic async template (`alembic init --template async`)
- 10 of 13 models already exist in db_models.py -- extend, don't rewrite

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-02 | SQLAlchemy models cover all 13 Firestore collections (3 new models + auth columns on users table) | Full Firestore audit completed -- actually 6 new models needed (see Collection Inventory below). Existing 10 models verified as correct. User model needs password_hash, role, scope, tools, GHL connection needs its own table. |
| DB-03 | Alembic initialized with async template and initial migration auto-generated from models | Alembic 1.18.4 installed, async template confirmed available. `database.py` has the async engine. Alembic env.py must import all models and use `run_async()` with the existing engine URL. |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy[asyncio] | 2.0.48 (installed) | ORM + async DB access | Already in use in `database.py` and `db_models.py` |
| asyncpg | 0.31.0 (installed) | Async PostgreSQL driver | Already configured as engine driver |
| Alembic | 1.18.4 (installed) | Schema migrations | Already in requirements.txt, async template available |
| psycopg2-binary | 2.9.x (in requirements) | Sync driver for Alembic offline mode | Required by Alembic env.py |
| PostgreSQL | 16 (via Docker) | Database | Already in docker-compose.yml |

### New Dependencies
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pwdlib[bcrypt] | >=0.2.0 | Password hashing | Add to requirements.txt now -- User model needs `password_hash` column, and Phase 23 needs the hasher immediately |

**Installation:**
```bash
pip install "pwdlib[bcrypt]>=0.2.0"
```

Note: pwdlib is not needed for the schema itself (password_hash is just a String column), but adding it now avoids a gap when Phase 23 tries to hash passwords.

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── alembic.ini                    # Alembic config (points to backend/migrations/)
├── migrations/                    # Alembic migrations directory
│   ├── env.py                     # Async env.py using existing engine config
│   ├── script.py.mako             # Migration template
│   └── versions/
│       └── 001_initial_schema.py  # Auto-generated from all models
├── app/
│   ├── models/
│   │   └── db_models.py           # ALL models (extended with 6 new)
│   └── core/
│       └── database.py            # Unchanged (engine + session factory)
```

### Pattern 1: Alembic Async Template Configuration
**What:** Alembic `env.py` configured to use the existing async engine from `database.py`
**When to use:** Always -- this project uses async SQLAlchemy exclusively

**Key points for env.py:**
```python
# In migrations/env.py
from app.core.database import Base
from app.models import db_models  # noqa: F401 -- registers all models with Base
from app.core.config import settings

# target_metadata must reference Base.metadata
target_metadata = Base.metadata

# Use settings.database_url for the connection string
# The async template's run_async_migrations() handles asyncpg
```

**alembic.ini key settings:**
```ini
[alembic]
script_location = migrations
# sqlalchemy.url is overridden in env.py from settings.database_url
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox
```

### Pattern 2: Model Extension (not rewrite)
**What:** Add new models and columns to the existing `db_models.py` file
**When to use:** This phase -- all models share `Base` from `database.py`

**Critical:** All new models MUST import and use `Base` from `app.core.database`. The existing `init_db()` function does `from app.models import db_models` to register models, and Alembic's `env.py` must do the same.

### Pattern 3: User Model Primary Key Change
**What:** The User.id is currently `String(128)` described as "Firebase UID". For local auth, IDs should be generated server-side.
**When to use:** This migration.

**Decision:** Keep `String(128)` as the PK type but change the default to `uuid4()` instead of Firebase UID. This is backwards-compatible -- existing FK references from jobs, audit_logs all use `String(128)`. The Firestore migration script (Phase 27) will preserve existing Firebase UIDs as the PK.

### Anti-Patterns to Avoid
- **Separate Base per model file:** All models must use the single `Base` from `database.py`. Alembic autogenerate only sees one metadata.
- **Running `create_all` alongside Alembic:** Remove or guard `init_db()` usage. Once Alembic manages schema, `create_all` should only be used as a fallback when Alembic is not configured.
- **Nullable password_hash:** The column must be nullable initially because existing users migrated from Firebase won't have passwords. Phase 23 seeds the admin password.

## Firestore Collection Inventory (Complete Audit)

| # | Firestore Collection | SQLAlchemy Model | Status | Source File |
|---|---------------------|------------------|--------|-------------|
| 1 | `users` | `User` | EXISTS -- needs 5 new columns | `db_models.py` |
| 2 | `jobs` | `Job` | EXISTS -- ready | `db_models.py` |
| 3 | `extract_entries` | `ExtractEntry` | EXISTS -- ready | `db_models.py` |
| 4 | `title_entries` | `TitleEntry` | EXISTS -- ready | `db_models.py` |
| 5 | `proration_rows` | `ProrationRow` | EXISTS -- ready | `db_models.py` |
| 6 | `revenue_statements` | `RevenueStatement` | EXISTS -- ready | `db_models.py` |
| 7 | `revenue_rows` (sub-docs in Firestore) | `RevenueRow` | EXISTS -- ready | `db_models.py` |
| 8 | `rrc_oil_proration` | `RRCOilProration` | EXISTS -- ready | `db_models.py` |
| 9 | `rrc_gas_proration` | `RRCGasProration` | EXISTS -- ready | `db_models.py` |
| 10 | `rrc_data_syncs` | `RRCDataSync` | EXISTS -- ready | `db_models.py` |
| 11 | `audit_logs` | `AuditLog` | EXISTS -- ready | `db_models.py` |
| 12 | `app_config` | **AppConfig** | **NEW** | `firestore_service.py` |
| 13 | `user_preferences` | **UserPreference** | **NEW** | `firestore_service.py` |
| 14 | `rrc_county_status` | **RRCCountyStatus** | **NEW** | `firestore_service.py` |
| 15 | `ghl_connections` | **GHLConnection** | **NEW** | `ghl/connection_service.py` |
| 16 | `rrc_sync_jobs` | **RRCSyncJob** | **NEW** | `rrc_background.py` |
| 17 | `rrc_metadata` | **RRCMetadata** | **NEW** | `firestore_service.py` |

**Total: 10 existing + 6 new models. User model needs 5 new columns.**

Note: The CONTEXT.md says "3 new models" based on the FEATURES.md count of 13 collections. The actual audit reveals 3 additional collections (`ghl_connections`, `rrc_sync_jobs`, `rrc_metadata`) used outside `firestore_service.py`. These must be modeled now or Phase 25 (DB-05: port all Firestore functions) will be blocked.

## New Model Schemas

### User Model Changes (5 new columns)
```python
# Add to existing User model:
password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # nullable for Firebase-migrated users
role: Mapped[str] = mapped_column(String(20), default="user")  # admin, user, viewer
scope: Mapped[str] = mapped_column(String(20), default="all")  # all, land, revenue, operations
tools: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # ["extract", "title", "proration", "revenue"]
added_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

Also update the docstring from "synced from Firebase Auth" to "Application user".

Also change the `id` default from no-default (Firebase UID) to `default=lambda: str(uuid4())` while keeping `String(128)` type for backwards compatibility.

### AppConfig Model (key/JSONB pattern)
```python
class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Firestore usage: `get_config_doc("allowed_users")` returns `{"users": [...]}`, `set_config_doc("enrichment", {...})`. The key is the document ID, data is the document body.

### UserPreference Model
```python
class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.id"), unique=True, index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", backref="preferences")
```

Firestore usage: Document ID is derived from email (`email.replace("@", "_at_").replace(".", "_")`). In PostgreSQL, use `user_id` FK instead.

### RRCCountyStatus Model
```python
class RRCCountyStatus(Base):
    __tablename__ = "rrc_county_status"

    key: Mapped[str] = mapped_column(String(20), primary_key=True)  # "08-003" (district-county_code)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, success, failed
    oil_record_count: Mapped[int] = mapped_column(Integer, default=0)
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Firestore usage: Document ID is the county key (e.g., "08-003"). Fields: status, oil_record_count, last_downloaded_at, error_message.

### GHLConnection Model
```python
class GHLConnection(Base):
    __tablename__ = "ghl_connections"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    encrypted_token: Mapped[str] = mapped_column(Text)  # Fernet-encrypted API token
    token_last4: Mapped[str] = mapped_column(String(4))
    location_id: Mapped[str] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Source: `ghl/connection_service.py` lines 44-55. Fields: name, encrypted_token, token_last4, location_id, notes, validation_status, created_at, updated_at.

### RRCSyncJob Model
```python
class RRCSyncJob(Base):
    __tablename__ = "rrc_sync_jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # e.g. "rrc-sync-2026-03-25T02-00-00"
    status: Mapped[str] = mapped_column(String(30), default="downloading_oil")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    oil_rows: Mapped[int] = mapped_column(Integer, default=0)
    gas_rows: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
```

Source: `rrc_background.py` lines 54-63.

### RRCMetadata Model
```python
class RRCMetadata(Base):
    __tablename__ = "rrc_metadata"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "counts"
    oil_rows: Mapped[int] = mapped_column(Integer, default=0)
    gas_rows: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    new_records: Mapped[int] = mapped_column(Integer, default=0)
    updated_records: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Source: `firestore_service.py` lines 652-698. Currently only one document ("counts") but modeled as a table for flexibility.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migrations | Manual SQL scripts | Alembic `--autogenerate` | Tracks schema state, generates diffs from models, handles upgrades across environments |
| UUID generation | Custom ID logic | `uuid4()` in column default | Already used in existing models (Job.id), consistent pattern |
| Async migration runner | Custom asyncio wrapper | Alembic async template | Built-in `run_async_migrations()` handles async engine properly |

## Common Pitfalls

### Pitfall 1: Alembic can't find models
**What goes wrong:** `alembic revision --autogenerate` generates an empty migration
**Why it happens:** Models aren't imported before autogenerate runs, so `Base.metadata` has no tables
**How to avoid:** In `env.py`, explicitly `import app.models.db_models` before setting `target_metadata = Base.metadata`
**Warning signs:** Migration file with empty `upgrade()` and `downgrade()` functions

### Pitfall 2: Engine URL mismatch between app and Alembic
**What goes wrong:** Alembic connects to wrong database or fails to connect
**Why it happens:** `alembic.ini` has hardcoded URL while `database.py` reads from env
**How to avoid:** Override `sqlalchemy.url` in `env.py` using `settings.database_url`. Do NOT rely on `alembic.ini` URL.
**Warning signs:** "could not connect to server" or migrations applied to wrong database

### Pitfall 3: asyncpg URL in Alembic offline mode
**What goes wrong:** Alembic offline mode (`--sql`) fails with `postgresql+asyncpg://` URL
**Why it happens:** Offline mode generates SQL without connecting, but asyncpg driver prefix is invalid for psycopg2
**How to avoid:** In `env.py` offline mode, replace `+asyncpg` with `+psycopg2` in the URL string
**Warning signs:** `ModuleNotFoundError: No module named 'asyncpg'` during offline migration

### Pitfall 4: DeclarativeBase vs declarative_base()
**What goes wrong:** Existing code uses `class Base(DeclarativeBase)` -- Alembic examples sometimes show `declarative_base()`
**Why it happens:** Two different API styles in SQLAlchemy 2.0
**How to avoid:** Use the existing `Base` class from `database.py` everywhere. Do not create a second Base.
**Warning signs:** "Table already defined" warnings or duplicate table creation

### Pitfall 5: Enum types in PostgreSQL
**What goes wrong:** Alembic generates `CREATE TYPE` for Python enums but doesn't handle drops properly
**Why it happens:** PostgreSQL requires explicit `CREATE TYPE` / `DROP TYPE` for enum columns
**How to avoid:** Existing models already use `Enum(ToolType)` and `Enum(JobStatus)`. Don't add new enum types unless necessary -- use `String` for new status/role columns.
**Warning signs:** `type "jobstatus" already exists` errors on re-run

### Pitfall 6: init_db() conflicts with Alembic
**What goes wrong:** Both Alembic and `init_db()` try to create tables, causing conflicts
**Why it happens:** `init_db()` calls `Base.metadata.create_all` which bypasses Alembic versioning
**How to avoid:** Guard `init_db()` so it only runs when Alembic is not configured (no `alembic_version` table exists), or remove it entirely and always use `alembic upgrade head`
**Warning signs:** Tables exist but `alembic_version` table is empty/missing

## Code Examples

### Alembic Async env.py (key sections)
```python
# migrations/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base and all models
from app.core.database import Base
from app.models import db_models  # noqa: F401
from app.core.config import settings

config = context.config

# Override URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Generating Initial Migration
```bash
cd backend
alembic init --template async migrations
# Edit env.py as shown above
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `declarative_base()` | `class Base(DeclarativeBase)` | SQLAlchemy 2.0 (2023) | Already using new style |
| `Column()` | `mapped_column()` | SQLAlchemy 2.0 (2023) | Already using new style |
| Sync Alembic | `alembic init --template async` | Alembic 1.12+ (2023) | Use async template |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | PostgreSQL container | Yes | 29.1.5 | -- |
| Docker Compose | `docker compose up db` | Yes | 5.0.1 | -- |
| PostgreSQL (via Docker) | Schema creation | Yes (docker-compose) | 16-alpine | -- |
| psql CLI | Manual DB inspection | No | -- | Use `docker exec` into postgres container |
| Alembic | Migration tooling | Yes | 1.18.4 | -- |
| SQLAlchemy | ORM | Yes | 2.0.48 | -- |
| asyncpg | Async PG driver | Yes | 0.31.0 | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- psql CLI not installed locally -- use `docker exec -it <container> psql -U postgres toolbox` for inspection

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ with pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/test_db_models.py -x` |
| Full suite command | `cd backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-02 | All 16 models importable, all have `__tablename__`, correct column types | unit | `cd backend && python3 -m pytest tests/test_db_models.py -x` | No -- Wave 0 |
| DB-02 | User model has password_hash, role, scope, tools, added_by columns | unit | `cd backend && python3 -m pytest tests/test_db_models.py::test_user_model_auth_columns -x` | No -- Wave 0 |
| DB-03 | `alembic upgrade head` succeeds on empty database | integration | `cd backend && alembic upgrade head` (requires running PostgreSQL) | N/A -- CLI command |
| DB-03 | Alembic migration creates all expected tables | integration | `cd backend && python3 -m pytest tests/test_db_models.py::test_migration_creates_tables -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_db_models.py -x`
- **Per wave merge:** `cd backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_db_models.py` -- covers DB-02 (model completeness, column types, relationships)
- [ ] Alembic integration test requires running PostgreSQL via Docker -- manual verification acceptable

## Open Questions

1. **RRCMetadata as separate table vs AppConfig row**
   - What we know: Firestore uses a dedicated `rrc_metadata` collection with one document ("counts"). Could be a row in `app_config` table instead.
   - What's unclear: Whether future metadata documents beyond "counts" are likely.
   - Recommendation: Keep as a separate table. The fields are typed (int, datetime) not arbitrary JSONB, and the RRC pipeline reads it frequently. A dedicated table avoids JSONB extraction overhead.

2. **GHLConnection ownership**
   - What we know: Firestore `ghl_connections` are global (no user_id). All users see all connections.
   - What's unclear: Whether connections should eventually be user-scoped.
   - Recommendation: No user_id FK for now -- matches current behavior. Add later via Alembic migration if needed.

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/app/models/db_models.py` -- 10 existing models verified
- Codebase: `backend/app/services/firestore_service.py` -- 13 collections, ~40 functions audited
- Codebase: `backend/app/services/ghl/connection_service.py` -- GHL connection schema extracted
- Codebase: `backend/app/services/rrc_background.py` -- RRC sync job schema extracted
- Codebase: `backend/app/core/database.py` -- async engine + Base class verified
- Codebase: `backend/app/core/auth.py` -- AllowedUser model (role, scope, tools fields)
- Local: `alembic list_templates` -- confirmed `async` template available at v1.18.4
- Local: `pip3 show` -- SQLAlchemy 2.0.48, asyncpg 0.31.0, Alembic 1.18.4

### Secondary (MEDIUM confidence)
- STACK.md research -- PyJWT + pwdlib recommendations from FastAPI official docs
- FEATURES.md research -- Firestore-to-PostgreSQL mapping (corrected with additional collections)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages already installed, versions verified locally
- Architecture: HIGH - existing patterns in codebase, Alembic async template documented
- Pitfalls: HIGH - based on direct codebase analysis of existing patterns and known SQLAlchemy/Alembic issues
- Collection inventory: HIGH - every `.collection("...")` call in the backend was grep-audited

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable infrastructure, no fast-moving dependencies)
