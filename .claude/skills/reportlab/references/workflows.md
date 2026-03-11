# ReportLab Workflows Reference

## Contents
- Full Proration PDF Export Pipeline
- FastAPI Integration: Response vs StreamingResponse
- Testing PDF Output
- Debugging Layout Issues
- Extending the Export (Adding Columns or Sections)

---

## Full Proration PDF Export Pipeline

**Flow:** `POST /api/proration/export/pdf` → `proration.py` route → `export_service.to_pdf()` → `bytes` → `Response`

```python
# backend/app/api/proration.py
from fastapi import APIRouter
from fastapi.responses import Response
from app.services.proration.export_service import to_pdf
from app.models.proration import MineralHolderRow

router = APIRouter(prefix="/api/proration")

@router.post("/export/pdf")
async def export_proration_pdf(rows: list[MineralHolderRow]):
    pdf_bytes = to_pdf(rows)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=proration.pdf"},
    )
```

```python
# backend/app/services/proration/export_service.py
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from app.models.proration import MineralHolderRow

def to_pdf(rows: list[MineralHolderRow]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    # Header row + data rows
    data = [["Owner", "County", "Interest", "RRC Acres", "Est NRA", "$/NRA", "Appraisal Value"]]
    for row in rows:
        data.append([
            row.owner or "",
            row.county or "",
            f"{row.interest:.4f}" if row.interest else "",
            f"{row.rrc_acres:.2f}" if row.rrc_acres else "",
            f"{row.est_nra:.4f}" if row.est_nra else "",
            f"${row.dollars_per_nra:.2f}" if row.dollars_per_nra else "",
            f"${row.appraisal_value:.2f}" if row.appraisal_value else "",
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    doc.build([table])
    buffer.seek(0)
    return buffer.read()
```

**Implementation Checklist:**

- [ ] Header row is first element in `data` list
- [ ] All numeric fields guarded with `if value else ""`
- [ ] `buffer.seek(0)` called before `buffer.read()`
- [ ] Function returns `bytes`, not `BytesIO`
- [ ] FastAPI uses `Response`, not `StreamingResponse`
- [ ] `Content-Disposition: attachment` header set
- [ ] Verify: `pdf_bytes[:4] == b"%PDF"`

---

## FastAPI Integration: Response vs StreamingResponse

Use `Response` when the full PDF is generated in memory (this codebase's pattern). Use `StreamingResponse` only for chunked generation or very large files.

```python
# GOOD - to_pdf() returns bytes, use Response
from fastapi.responses import Response

return Response(
    content=to_pdf(rows),
    media_type="application/pdf",
    headers={"Content-Disposition": "attachment; filename=proration.pdf"},
)
```

```python
# AVOID for this use case - StreamingResponse is for generators/iterators
from fastapi.responses import StreamingResponse

return StreamingResponse(
    iter([pdf_bytes]),  # Unnecessary wrapper
    media_type="application/pdf",
)
```

### Frontend Download Pattern

See the **react** skill for the full pattern. The key steps:

```typescript
// frontend/src/pages/Proration.tsx
const response = await fetch("/api/proration/export/pdf", {
  method: "POST",
  headers: { "Content-Type": "application/json", "Authorization": `Bearer ${idToken}` },
  body: JSON.stringify({ rows: prorationResults }),
});
const blob = await response.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement("a");
a.href = url;
a.download = "proration.pdf";
a.click();
URL.revokeObjectURL(url);
```

---

## Testing PDF Output

```python
# backend/tests/test_proration_export.py
import pytest
from app.services.proration.export_service import to_pdf
from app.models.proration import MineralHolderRow

def _make_row(**kwargs) -> MineralHolderRow:
    defaults = {
        "owner": "John Doe", "county": "Midland", "interest": 0.1250,
        "rrc_acres": 80.0, "est_nra": 10.0, "dollars_per_nra": 5.0,
        "appraisal_value": 50000.0,
    }
    return MineralHolderRow(**{**defaults, **kwargs})

def test_to_pdf_returns_valid_pdf():
    rows = [_make_row(), _make_row(owner="Jane Smith")]
    result = to_pdf(rows)
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"%PDF"

def test_to_pdf_handles_none_fields():
    """Missing optional fields should produce empty string cells, not crash."""
    rows = [_make_row(interest=None, est_nra=None, appraisal_value=None)]
    result = to_pdf(rows)
    assert result[:4] == b"%PDF"

def test_to_pdf_empty_rows():
    """Empty input produces a valid (header-only) PDF, not an exception."""
    result = to_pdf([])
    assert result[:4] == b"%PDF"

def test_to_pdf_large_dataset():
    """100+ rows should trigger Platypus auto-pagination without error."""
    rows = [_make_row(owner=f"Owner {i}") for i in range(150)]
    result = to_pdf(rows)
    assert result[:4] == b"%PDF"
```

**Run tests:**
```bash
cd backend
pytest tests/test_proration_export.py -v
```

**Validate until passing:**
1. Run tests
2. If `AssertionError: b'%PDF'` — check `buffer.seek(0)` is present
3. If `AttributeError` on row fields — verify `MineralHolderRow` model fields match
4. Only proceed when all 4 tests pass

---

## Debugging Layout Issues

### Quick Visual Check

Write to disk and open to inspect layout:

```python
# scripts/debug_pdf.py
from app.services.proration.export_service import to_pdf
from app.models.proration import MineralHolderRow

rows = [MineralHolderRow(owner=f"Owner {i}", county="Test", interest=0.125,
        rrc_acres=80.0, est_nra=10.0, dollars_per_nra=5.0, appraisal_value=50000.0)
        for i in range(50)]

with open("/tmp/debug_proration.pdf", "wb") as f:
    f.write(to_pdf(rows))

# macOS: open /tmp/debug_proration.pdf
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty PDF downloaded | `buffer.seek(0)` missing | Add before `buffer.read()` |
| PDF content is `"<_io.BytesIO object...>"` | Returned `BytesIO` instead of `bytes` | Call `.read()` after `.seek(0)` |
| Columns clipped on right edge | Total column widths exceed page | Reduce `colWidths`, check against usable width (~468pt) |
| Header row has wrong background | Row index off-by-one in style commands | Data rows start at index 1, not 0 |
| Table overflows onto new page unexpectedly | Platypus default row height too large | Set explicit `rowHeights` in `Table(data, rowHeights=...)` |

---

## Extending the Export (Adding Columns or Sections)

### Adding a New Column

1. Add header string to `data[0]` list
2. Add value to each row's list in same position
3. Add `colWidths` parameter to `Table()` — don't let Platypus auto-size with wide tables
4. Verify total width ≤ usable page width

```python
# Add "Notes" column
data = [["Owner", "County", "Interest", "RRC Acres", "Est NRA", "$/NRA", "Appraisal Value", "Notes"]]
for row in rows:
    data.append([
        row.owner or "",
        row.county or "",
        # ... existing fields ...
        row.notes or "",  # new column
    ])

from reportlab.lib.units import inch
table = Table(data, colWidths=[
    1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.0*inch, 1.5*inch
])
```

### Adding a Summary Section

```python
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
total_nra = sum(r.est_nra for r in rows if r.est_nra)

elements = [
    Paragraph(f"Total Est. NRA: {total_nra:.4f}", styles["Normal"]),
    Spacer(1, 12),
    table,
]
doc.build(elements)
```

See the **pydantic** skill for `MineralHolderRow` field definitions when adding new columns.
