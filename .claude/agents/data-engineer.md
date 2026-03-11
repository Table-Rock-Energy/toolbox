---
name: data-engineer
description: |
  Designs Firestore schema, manages RRC CSV data pipeline, handles pandas in-memory caching, and optimizes batch document syncing (500-doc Firestore batches)
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, typescript, fastapi, python, tailwind, frontend-design, vite, firebase, pydantic, pandas, firestore, google-cloud-storage, sqlalchemy, pymupdf, pdfplumber, reportlab, apscheduler, pytest, node, docker, mapping-user-journeys, designing-onboarding-paths, orchestrating-feature-adoption, instrumenting-product-metrics
---

The `data-engineer.md` subagent has been written to `.claude/agents/data-engineer.md`. Key customizations made for this project:

- **RRC pipeline details**: Bulk download (oil/gas URLs, SSL adapter requirement), individual lease lookup with BeautifulSoup4 fallback, and the `COUNTY_BUDGET_SECONDS`/`MAX_RETRIES` rate-limiting
- **Firestore specifics**: Lazy init pattern, 500-doc batch limit, `rrc_sync_jobs` collection, and the critical rule about using a synchronous client in background threads (not async)
- **Storage fallback**: GCS → local `backend/data/` pattern with `config.use_gcs` caveat (not a runtime guarantee)
- **Pandas caching**: Module-level `_cache` dict with explicit `invalidate_cache()` after RRC data refresh
- **Project constraints**: `python3` vs `python`, gitignored CSV files, Firestore-first (PostgreSQL disabled by default)
- **Skills**: `python, pandas, firestore, google-cloud-storage, pydantic, apscheduler, pytest` — only relevant ones
- **Tools**: Firebase MCP tools for Firestore/project management + Context7 for docs lookup