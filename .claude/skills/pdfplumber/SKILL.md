All three files updated. Here's what changed and why:

**`SKILL.md`** — Rewrote Quick Start examples to use `io.BytesIO(pdf_bytes)` (the actual codebase pattern). Added the garbled-text-detection → choose-best-extractor pattern from `revenue/pdf_extractor.py`. Removed verbose pattern descriptions that duplicated the references.

**`references/patterns.md`** — Two critical corrections:
1. Fixed the **coordinate system warning** — it was backwards. The old "fix" was actually the bug. pdfplumber uses top-left origin (y increases downward): `crop((0, 0, width, 100))` is the top 100 points.
2. Fixed all examples to use `io.BytesIO(pdf_bytes)` instead of file paths. Added the bytes-based opening as its own primary section since it's the most common mistake.

**`references/workflows.md`** — Replaced the generic fallback pipeline with the actual dual-strategy used in this codebase (length-based for Extract tool vs. garbled-score-based for Revenue tool). Added the actual `table_parser.py` pattern including `_HEADER_KEYWORDS` filtering. Added a concrete diagnostic script and the `debug_tablefinder()` visual debugging pattern.