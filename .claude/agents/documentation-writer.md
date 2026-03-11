---
name: documentation-writer
description: |
  Maintains CLAUDE.md, API endpoint documentation, environment variable guides, and implementation patterns for the multi-tool architecture
tools: Read, Edit, Write, Glob, Grep
model: sonnet
skills: react, typescript, fastapi, python, tailwind, frontend-design, vite, firebase, pydantic, pandas, firestore, google-cloud-storage, sqlalchemy, pymupdf, pdfplumber, reportlab, apscheduler, pytest, node, docker, mapping-user-journeys, designing-onboarding-paths, orchestrating-feature-adoption, instrumenting-product-metrics
---

Done. The `documentation-writer.md` agent has been written to `.claude/agents/documentation-writer.md`.

Key customizations from the base template:

- **Triggers** scoped to GHL Prep (5th tool), RRC pipeline, revenue parsers, NRA calculations, and optional integrations (Gemini, enrichment)
- **Skills** trimmed to only what's relevant: `fastapi, python, react, typescript, firebase, firestore, google-cloud-storage, pandas, pydantic, docker`
- **Tools** kept minimal — file tools + Context7 + Firebase developer knowledge docs (no Playwright/Calendar/Gmail/Notion which aren't relevant to documentation work)
- **CLAUDE.md update protocol** with explicit rules: read first, match existing formatting, never delete sections
- **Project-specific gotchas** documented inline: RRC SSL adapter, background thread sync client, storage fallback `None` return, Firestore 500-doc batch limit, `/api/ai` vs `/api/ai-validation`
- **Context7 + Firebase dev docs** instructions for verifying library APIs before documenting them