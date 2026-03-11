All three files have been rewritten. Here's what changed:

**SKILL.md** — Full rewrite:
- Corrected to SQLAlchemy 2.x `Mapped`/`mapped_column` style throughout (previous version used legacy `Column()`)
- Session example shows `get_db()` owns commit/rollback, services use `flush()` only
- Upsert pattern matches actual `upsert_rrc_oil_record` in `db_service.py`
- Key concepts table updated with `expire_on_commit=False` and `UUID(as_uuid=False)` context

**references/patterns.md** — Full rewrite:
- Lead WARNING against `Column()` with concrete consequences (shared mutable default)
- `DeclarativeBase` vs `declarative_base()` distinction
- `JSONB`/`UUID(as_uuid=False)` patterns matching actual model fields
- `flush()` vs `commit()` explanation — critical for the service layer pattern
- Lazy loading `MissingGreenlet` warning with fix

**references/workflows.md** — Full rewrite:
- "Enabling optional DB" section (env vars + docker-compose)
- New model checklist + template matching existing model structure
- Service function template matching `db_service.py` patterns
- Async SQLite test fixture matching project's pytest setup
- Troubleshooting for the 5 most common async SQLAlchemy errors