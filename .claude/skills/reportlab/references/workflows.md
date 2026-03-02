# ReportLab Workflows Reference

## Contents
- Full Proration PDF Export Pipeline
- Testing PDF Generation Locally
- Debugging Layout Issues
- Integrating with FastAPI Endpoints
- WARNING: BytesIO Seek Position

---

## Full Proration PDF Export Pipeline

### End-to-End Workflow

**Context:** User uploads mineral holder CSV → Backend processes → Frontend downloads PDF via `/api/proration/export/pdf`.

```python
# toolbox/backend/app/api/proration.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.proration.export_service import generate_pdf

router = APIRouter(prefix="/api/proration")

@router.post("/export/pdf")
async def export_pdf(request: ProrationExportRequest):
    """Generate PDF export of proration results."""
    try:
        # 1. Validate request data (see pydantic skill)
        if not request.rows:
            raise HTTPException(status_code=400, detail="No rows to export")
        
        # 2. Generate PDF (ReportLab)
        pdf_buffer = generate_pdf(
            rows=request.rows,
            title=request.title or "Proration Report",
            metadata=request.metadata,
        )
        
        # 3. Return as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=proration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            }
        )
    except Exception as e:
        logger.error(f"PDF export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="PDF generation failed")
```

```python
# toolbox/backend/app/services/proration/export_service.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

def generate_pdf(rows: list[dict], title: str, metadata: dict | None = None) -> BytesIO:
    """Generate proration PDF with headers, table, and page numbers.
    
    Args:
        rows: List of proration calculation results
        title: Report title
        metadata: Optional metadata (date range, lease info)
    
    Returns:
        BytesIO buffer containing PDF data
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Constants
    margin = 50
    row_height = 20
    bottom_margin = 50
    top_margin = 100
    
    page_num = 1
    y = height - top_margin
    
    # Helper functions
    def add_header():
        nonlocal y
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, height - 40, title)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin, height - 60, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if metadata:
            pdf.drawString(margin, height - 75, f"Lease: {metadata.get('lease_number', 'N/A')}")
        pdf.line(margin, height - 85, width - margin, height - 85)
        y = height - top_margin
    
    def add_footer():
        pdf.setFont("Helvetica", 9)
        pdf.drawString(width / 2 - 20, 20, f"Page {page_num}")
    
    def check_page_break():
        nonlocal y, page_num
        if y < bottom_margin:
            add_footer()
            pdf.showPage()
            page_num += 1
            add_header()
    
    # Draw header on first page
    add_header()
    
    # Column definitions (see patterns.md)
    columns = [
        ('owner_name', 'Owner', margin, 180, 'left'),
        ('nra', 'NRA', margin + 190, 60, 'right'),
        ('decimal', 'Decimal', margin + 260, 80, 'right'),
        ('lease_number', 'Lease #', margin + 350, 100, 'left'),
    ]
    
    # Draw table header
    pdf.setFont("Helvetica-Bold", 10)
    for key, label, x, width, align in columns:
        pdf.drawString(x, y, label)
    y -= row_height
    pdf.line(margin, y + 5, width - margin, y + 5)  # Underline
    y -= 10
    
    # Draw rows
    pdf.setFont("Helvetica", 9)
    for row in rows:
        check_page_break()
        
        for key, label, x, col_width, align in columns:
            value = format_cell_value(row.get(key), key, align)
            if align == 'right':
                pdf.drawRightString(x + col_width, y, value)
            else:
                pdf.drawString(x, y, value)
        
        y -= row_height
    
    # Final footer
    add_footer()
    pdf.save()
    
    buffer.seek(0)  # CRITICAL - reset buffer position
    return buffer

def format_cell_value(value: any, key: str, align: str) -> str:
    """Format cell value based on column type."""
    if value is None:
        return ''
    
    if key == 'nra':
        return f"{float(value):.4f}"
    elif key == 'decimal':
        return f"{float(value):.6f}"
    else:
        return str(value)
```

**Workflow Checklist:**

Copy this checklist for implementing PDF exports:
- [ ] Define Pydantic request model with `rows: list[dict]`
- [ ] Create FastAPI endpoint with `StreamingResponse`
- [ ] Implement `generate_pdf()` in service layer
- [ ] Add header/footer functions with page tracking
- [ ] Define column layout (see patterns.md)
- [ ] Implement `check_page_break()` before each row
- [ ] Format numeric values with consistent precision
- [ ] Add `buffer.seek(0)` before returning
- [ ] Test with 1, 10, 100, 1000 rows (pagination)
- [ ] Verify filename includes timestamp
- [ ] Add error logging with `exc_info=True`

---

## Testing PDF Generation Locally

### Unit Test Pattern

```python
# toolbox/backend/tests/test_proration_export.py
import pytest
from io import BytesIO
from PyPDF2 import PdfReader
from app.services.proration.export_service import generate_pdf

def test_generate_pdf_basic():
    """Test basic PDF generation with sample data."""
    rows = [
        {'owner_name': 'John Doe', 'nra': 0.1234, 'decimal': 0.123456, 'lease_number': 'L-001'},
        {'owner_name': 'Jane Smith', 'nra': 0.5678, 'decimal': 0.567890, 'lease_number': 'L-002'},
    ]
    
    buffer = generate_pdf(rows, title="Test Report")
    
    # Verify buffer is valid PDF
    assert isinstance(buffer, BytesIO)
    assert buffer.tell() == 0  # Seek position reset
    
    # Read PDF content
    pdf = PdfReader(buffer)
    assert len(pdf.pages) == 1  # Should fit on one page
    
    # Extract text and verify content
    text = pdf.pages[0].extract_text()
    assert "Test Report" in text
    assert "John Doe" in text
    assert "0.1234" in text  # NRA formatted correctly

def test_generate_pdf_pagination():
    """Test pagination with large dataset."""
    # Generate 100 rows (should span multiple pages)
    rows = [
        {'owner_name': f'Owner {i}', 'nra': i * 0.01, 'decimal': i * 0.001, 'lease_number': f'L-{i:03d}'}
        for i in range(100)
    ]
    
    buffer = generate_pdf(rows, title="Pagination Test")
    pdf = PdfReader(buffer)
    
    # Verify multiple pages
    assert len(pdf.pages) > 1
    
    # Verify page numbers on each page
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        assert f"Page {page_num}" in text

def test_generate_pdf_missing_data():
    """Test graceful handling of missing/invalid data."""
    rows = [
        {'owner_name': 'Valid Row', 'nra': 0.1, 'decimal': 0.01, 'lease_number': 'L-001'},
        {'owner_name': '', 'nra': None, 'decimal': None, 'lease_number': ''},  # Invalid
        {'owner_name': 'Another Valid', 'nra': 0.2, 'decimal': 0.02, 'lease_number': 'L-002'},
    ]
    
    # Should not crash, should skip invalid rows or show defaults
    buffer = generate_pdf(rows, title="Missing Data Test")
    pdf = PdfReader(buffer)
    
    text = pdf.pages[0].extract_text()
    assert "Valid Row" in text
    assert "Another Valid" in text
```

### Manual Testing Script

```python
# scripts/test_pdf_export.py
"""
Manual testing script for PDF generation.
Usage: python3 scripts/test_pdf_export.py
"""
from app.services.proration.export_service import generate_pdf
import random

def generate_sample_data(count: int) -> list[dict]:
    """Generate sample proration data."""
    owners = ['John Doe', 'Jane Smith', 'Acme Corp', 'Smith Family Trust', 'XYZ LLC']
    return [
        {
            'owner_name': random.choice(owners),
            'nra': random.uniform(0.0001, 1.0),
            'decimal': random.uniform(0.000001, 0.1),
            'lease_number': f'L-{i:05d}',
        }
        for i in range(count)
    ]

if __name__ == '__main__':
    # Test small dataset
    print("Generating PDF with 10 rows...")
    data = generate_sample_data(10)
    buffer = generate_pdf(data, title="Small Test Report")
    with open('test_small.pdf', 'wb') as f:
        f.write(buffer.getvalue())
    print("✓ Saved to test_small.pdf")
    
    # Test large dataset (pagination)
    print("Generating PDF with 500 rows...")
    data = generate_sample_data(500)
    buffer = generate_pdf(data, title="Large Test Report")
    with open('test_large.pdf', 'wb') as f:
        f.write(buffer.getvalue())
    print("✓ Saved to test_large.pdf")
    
    # Test edge cases
    print("Generating PDF with missing data...")
    data = [
        {'owner_name': 'Valid', 'nra': 0.1, 'decimal': 0.01, 'lease_number': 'L-001'},
        {'owner_name': '', 'nra': None, 'decimal': None, 'lease_number': ''},
        {'owner_name': 'Also Valid', 'nra': 0.2, 'decimal': 0.02, 'lease_number': 'L-002'},
    ]
    buffer = generate_pdf(data, title="Edge Case Test")
    with open('test_edge_cases.pdf', 'wb') as f:
        f.write(buffer.getvalue())
    print("✓ Saved to test_edge_cases.pdf")
```

**Run tests:**
```bash
cd toolbox/backend

# Unit tests
pytest tests/test_proration_export.py -v

# Manual script
python3 scripts/test_pdf_export.py
open test_small.pdf  # macOS
```

---

## Debugging Layout Issues

### Visual Debugging with Grid Lines

```python
def draw_debug_grid(pdf: canvas.Canvas, width: float, height: float):
    """Draw grid lines for debugging layout issues.
    
    Remove this before production.
    """
    pdf.setStrokeColorRGB(0.9, 0.9, 0.9)  # Light gray
    pdf.setLineWidth(0.5)
    
    # Vertical lines every 50 points
    for x in range(0, int(width), 50):
        pdf.line(x, 0, x, height)
        pdf.setFont("Helvetica", 6)
        pdf.drawString(x + 2, 5, str(x))
    
    # Horizontal lines every 50 points
    for y in range(0, int(height), 50):
        pdf.line(0, y, width, y)
        pdf.setFont("Helvetica", 6)
        pdf.drawString(5, y + 2, str(y))
    
    # Reset stroke color
    pdf.setStrokeColorRGB(0, 0, 0)

# Usage during development
pdf = canvas.Canvas(buffer, pagesize=letter)
draw_debug_grid(pdf, width, height)  # Add temporarily
# ... rest of PDF generation
```

### Logging Layout Calculations

```python
# Add detailed logging for pagination debugging
def check_page_break_with_logging(y: float, row_idx: int, total_rows: int):
    if y < bottom_margin:
        logger.debug(f"Page break at row {row_idx}/{total_rows}, y={y}")
        pdf.showPage()
        page_num += 1
        y = height - top_margin
        logger.debug(f"New page {page_num}, reset y={y}")
    return y, page_num
```

### Common Layout Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Text clipped at page bottom | Page break check after drawing | Check `if y < margin` BEFORE `drawString` |
| Columns misaligned | Hardcoded x-coordinates | Use calculated positions (see patterns.md) |
| Numbers not aligned | Using `drawString` instead of `drawRightString` | Use `drawRightString(x + width, y, text)` |
| Missing page numbers | Forgot `add_footer()` before `showPage()` | Call footer before page break |
| First page has no header | Header added after first row | Call `add_header()` before loop |
| Blank PDF | Forgot `buffer.seek(0)` | Add `buffer.seek(0)` before returning |

---

## Integrating with FastAPI Endpoints

### StreamingResponse Pattern

```python
# toolbox/backend/app/api/proration.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime

@router.post("/export/pdf")
async def export_proration_pdf(request: ProrationExportRequest):
    """Export proration results as PDF.
    
    Returns PDF as streaming response with attachment header.
    """
    try:
        # Generate PDF
        pdf_buffer = generate_pdf(
            rows=request.rows,
            title=request.title or "Proration Report",
            metadata=request.metadata,
        )
        
        # Filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"proration_{timestamp}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache",  # Don't cache PDFs
            }
        )
    except ValueError as e:
        # Expected errors (validation, missing data)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors
        logger.error(f"PDF export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="PDF generation failed")
```

### Frontend Integration (React)

```typescript
// toolbox/frontend/src/pages/Proration.tsx
const handleExportPDF = async () => {
  try {
    setIsExporting(true);
    
    const response = await fetch('/api/proration/export/pdf', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${idToken}`,
      },
      body: JSON.stringify({
        rows: prorationResults,  // From state
        title: 'Proration Report',
        metadata: { lease_number: selectedLease },
      }),
    });
    
    if (!response.ok) {
      throw new Error('PDF export failed');
    }
    
    // Download PDF
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `proration_${Date.now()}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
  } catch (error) {
    console.error('PDF export error:', error);
    alert('Failed to generate PDF');
  } finally {
    setIsExporting(false);
  }
};
```

**See the react and fastapi skills for more integration patterns.**

---

## WARNING: BytesIO Seek Position

**The Problem:**

```python
# BAD - Buffer seek position not reset
def generate_pdf(rows: list[dict]) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    # ... draw content
    pdf.save()  # Leaves buffer seek position at end
    return buffer  # FastAPI reads from current position (EOF), returns empty PDF
```

**Why This Breaks:**
1. `canvas.save()` writes PDF data and advances buffer position to end
2. FastAPI `StreamingResponse` reads from current position
3. Current position is EOF, so response body is empty (0 bytes)
4. User downloads blank PDF, no error logged

**The Fix:**

```python
# GOOD - Reset buffer seek position
def generate_pdf(rows: list[dict]) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    # ... draw content
    pdf.save()
    buffer.seek(0)  # CRITICAL - reset to beginning
    return buffer
```

**When You Might Be Tempted:**
- "The buffer is new, it should start at position 0" - NO. `save()` advances the position.
- "I'll let the caller handle it" - NO. The function should return a ready-to-use buffer.
- "It works locally" - Maybe you're debugging with `getvalue()` which doesn't care about position, but production streaming does.

**Validation:**

Iterate until this test passes:
1. Generate PDF with `generate_pdf()`
2. Check buffer position: `assert buffer.tell() == 0`
3. Read buffer: `data = buffer.read()`
4. Verify non-empty: `assert len(data) > 0`
5. Only proceed when all assertions pass