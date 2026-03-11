# ReportLab Patterns Reference

## Contents
- Platypus vs Canvas: Which to Use
- TableStyle Cell Selectors
- Column Widths and Page Fitting
- Numeric Formatting
- WARNING: Returning bytes vs BytesIO
- WARNING: Missing `buffer.seek(0)`

---

## Platypus vs Canvas

This codebase uses **Platypus only**. Do not introduce Canvas unless you need pixel-precise manual layout.

| Approach | Use When | Auto-Pagination | Complexity |
|----------|----------|-----------------|------------|
| Platypus (`SimpleDocTemplate`) | Tabular reports, mixed content | YES | Low |
| Canvas (`pdfgen.canvas`) | Pixel-precise layout, watermarks | NO (manual) | High |

```python
# GOOD - What this project uses
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

buffer = io.BytesIO()
doc = SimpleDocTemplate(buffer, pagesize=letter)
doc.build([table, paragraph])
buffer.seek(0)
return buffer.read()
```

```python
# AVOID - Canvas requires manual y-coordinate tracking and page breaks
from reportlab.pdfgen import canvas
pdf = canvas.Canvas(buffer, pagesize=letter)
pdf.drawString(50, 700, "text")  # Manual coordinate
pdf.showPage()  # Manual page break
pdf.save()
```

**NEVER mix Canvas and Platypus in the same document** — they produce separate PDF streams and will corrupt the output.

---

## TableStyle Cell Selectors

Cell selectors use `(col, row)` tuples (0-indexed). `(-1, -1)` means last cell.

```python
TableStyle([
    # Entire header row (row 0, all columns)
    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",  (0, 0), (-1, 0), 12),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),

    # All data rows (row 1 to last, all columns)
    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),

    # Full grid
    ("GRID", (0, 0), (-1, -1), 1, colors.black),

    # Alignment (CENTER, LEFT, RIGHT)
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),

    # Specific column right-aligned (column 2, all rows)
    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
])
```

### WARNING: Row Index in Dynamic Style Commands

**The Problem:**
```python
# BAD - row index 0 is the header, data rows start at 1
for i, row in enumerate(rows):
    if row.est_nra == 0:
        style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.red))
        # When i=0, this styles the HEADER, not the first data row
```

**The Fix:**
```python
# GOOD - offset by 1 to skip header
for i, row in enumerate(rows, start=1):
    if row.est_nra == 0:
        style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.lightyellow))
```

---

## Column Widths and Page Fitting

Letter page = 612 points wide. Default margins are ~72pt each side = ~468pt usable.

```python
from reportlab.lib.units import inch

# Named widths are clearer than magic numbers
COL_WIDTHS = [
    2.0 * inch,   # Owner (wide)
    1.0 * inch,   # County
    0.8 * inch,   # Interest
    0.8 * inch,   # RRC Acres
    0.8 * inch,   # Est NRA
    0.8 * inch,   # $/NRA
    1.0 * inch,   # Appraisal Value
]
# Total = 7.2 inches — fits letter with standard margins

table = Table(data, colWidths=COL_WIDTHS)
```

### WARNING: Table Overflow

**The Problem:** ReportLab silently clips content that exceeds page width. You won't get an error — data just disappears off the right edge.

**The Fix:**
```python
# Validate total width before building
usable_width = letter[0] - 2 * 72  # 612 - 144 = 468 pts
total_col_width = sum(COL_WIDTHS)
if total_col_width > usable_width:
    raise ValueError(f"Table too wide: {total_col_width}pt > {usable_width}pt usable")
```

---

## Numeric Formatting

Match display precision to what the proration model stores — false precision misleads users.

```python
# Project-standard precision (matches MineralHolderRow field definitions)
f"{row.interest:.4f}"          # 4 decimals for interest/NRA
f"{row.rrc_acres:.2f}"         # 2 decimals for acreage
f"${row.appraisal_value:.2f}"  # 2 decimals for dollar amounts
f"{row.est_nra:.4f}"           # 4 decimals for estimated NRA

# Guard None/missing values inline
f"{row.interest:.4f}" if row.interest else ""
f"${row.appraisal_value:.2f}" if row.appraisal_value else ""
```

```python
# BAD - str(float) produces arbitrary precision
str(0.12345678)    # "0.12345678" — inconsistent
str(0.1)           # "0.1" — not "0.1000"
f"{value:.10f}"    # Implies false accuracy
```

---

## WARNING: Returning bytes vs BytesIO

**The Problem:**

The FastAPI endpoint expects `bytes`, not `BytesIO`. Returning `BytesIO` directly to `Response(content=...)` produces a string representation of the object, not PDF content.

```python
# BAD - returns BytesIO object, not bytes
def to_pdf(rows) -> BytesIO:
    buffer = BytesIO()
    doc.build(elements)
    return buffer  # FastAPI Response gets "<_io.BytesIO object at 0x...>"
```

**The Fix:**

```python
# GOOD - return bytes as in the actual export_service.py
def to_pdf(rows: list[MineralHolderRow]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()  # bytes, not BytesIO
```

Use `Response(content=pdf_bytes, media_type="application/pdf")` in FastAPI — not `StreamingResponse` when the full payload is already in memory.

---

## WARNING: Missing `buffer.seek(0)`

**The Problem:**

`doc.build()` writes to the buffer and leaves the seek position at the end. `buffer.read()` then returns `b""`.

```python
# BAD
doc.build(elements)
return buffer.read()  # Reads from EOF → returns b""
```

**The Fix:**

```python
# GOOD - always seek before read
doc.build(elements)
buffer.seek(0)
return buffer.read()
```

**Validation — iterate until this passes:**
1. Call `to_pdf(sample_rows)`
2. `assert len(pdf_bytes) > 0`
3. `assert pdf_bytes[:4] == b"%PDF"` (valid PDF magic bytes)
