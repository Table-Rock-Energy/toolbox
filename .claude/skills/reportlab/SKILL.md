All three skill files have been rewritten. Key corrections made:

**`SKILL.md`** — Corrected the fundamental inaccuracy: the project uses Platypus (`SimpleDocTemplate` + `Table`), not Canvas. Quick Start now shows the actual `to_pdf()` function from `export_service.py`. Return type is `bytes`, not `BytesIO`.

**`references/patterns.md`** — Replaced Canvas-focused patterns with accurate Platypus content:
- `TableStyle` cell selector syntax with 0-indexed `(col, row)` tuples
- Column width calculation against letter page usable width (~468pt)
- Off-by-one warning for dynamic row highlighting (data rows start at index 1)
- WARNING sections for returning `bytes` vs `BytesIO` and the `buffer.seek(0)` gotcha

**`references/workflows.md`** — Rewrote with accurate pipeline:
- Actual `to_pdf()` → `Response` pattern (not `StreamingResponse`)
- 4 concrete `pytest` tests with `MineralHolderRow` fixtures
- Debug table for common symptoms with root causes
- Step-by-step guide for adding columns or summary sections