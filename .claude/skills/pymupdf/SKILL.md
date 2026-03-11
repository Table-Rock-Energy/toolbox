All three files have been rewritten. Here's what changed and why:

**Key corrections from the old files:**

1. **`fitz.open(stream=pdf_bytes, filetype="pdf")`** — old files showed `fitz.open(pdf_path)` (file paths), but the actual codebase always opens from bytes received from `UploadFile`. This is the most impactful fix.

2. **`"dict"` mode extraction** — the Extract tool uses `page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)` with column-aware block sorting, not the simple `page.get_text()` pattern the old files showed.

3. **Garbled text detection** — the Revenue tool doesn't just "try PyMuPDF first" — it scores both extractors and picks the winner. Old files described a simpler threshold-only fallback.

4. **`extract_spans_by_page()` / `TextSpan`** — position-aware span extraction for Enverus multi-column parsing was completely missing from old reference files.

5. **Extract tool vs Revenue tool are architecturally distinct** — old files treated them as the same pattern. Extract uses column detection + dict-mode; Revenue uses text-mode + garbled scoring.