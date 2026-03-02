---
name: reportlab
description: |
  Generates PDF exports for proration calculations and reports using ReportLab 4.x.
  Use when: creating PDF exports for proration results, generating formatted reports with tables/text, building multi-page PDF documents with headers/footers
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# ReportLab Skill

Generates proration calculation PDFs with formatted tables and custom page layouts. This project uses ReportLab exclusively in `toolbox/backend/app/services/proration/export_service.py` for PDF exports triggered via `/api/proration/export/pdf`. The implementation uses a canvas-based approach with manual layout calculations, which provides precise control but requires careful coordinate management.

## Quick Start

### Basic PDF Generation Pattern

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

def generate_proration_pdf(data: list[dict]) -> BytesIO:
    """Generate proration PDF export with formatted table."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(100, height - 50, "Proration Report")
    
    # Table setup
    y = height - 100
    row_height = 20
    
    # Draw rows
    for row in data:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, row['name'])
        y -= row_height
        
        if y < 50:  # Page break
            pdf.showPage()
            y = height - 50
    
    pdf.save()
    buffer.seek(0)
    return buffer
```

### Table-Based Layout (Recommended)

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

def generate_with_table(data: list[dict]) -> BytesIO:
    """Use platypus Table for automatic pagination and styling."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Convert data to table format
    table_data = [["Owner", "NRA", "Decimal"]]  # Header
    for row in data:
        table_data.append([row['owner'], f"{row['nra']:.4f}", f"{row['decimal']:.6f}"])
    
    # Create table with style
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Canvas API | Low-level drawing with precise coordinates | `pdf.drawString(x, y, text)` |
| Platypus | High-level document assembly with auto-pagination | `SimpleDocTemplate`, `Table`, `Paragraph` |
| Coordinate System | Origin at bottom-left, y increases upward | `letter = (612, 792)` points |
| BytesIO Buffer | In-memory PDF storage for FastAPI responses | `buffer = BytesIO()` |
| Page Break Logic | Manual page breaks when y-coordinate too low | `if y < 50: pdf.showPage()` |

## Common Patterns

### Proration Export with Headers/Footers

**When:** Exporting multi-page proration results with consistent branding

```python
def add_page_header(pdf: canvas.Canvas, width: float, height: float, title: str):
    """Add consistent header to each page."""
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 40, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, height - 60, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.line(50, height - 70, width - 50, height - 70)  # Horizontal line

def add_page_footer(pdf: canvas.Canvas, width: float, page_num: int):
    """Add page number footer."""
    pdf.setFont("Helvetica", 9)
    pdf.drawString(width / 2 - 20, 30, f"Page {page_num}")
```

### Decimal Formatting for NRA Calculations

**When:** Displaying decimal precision for NRA (Net Revenue Acre) values

```python
# Project uses 4-decimal precision for NRA, 6-decimal for decimals
nra_formatted = f"{nra_value:.4f}"  # 0.1234
decimal_formatted = f"{decimal_value:.6f}"  # 0.123456

# Right-align numeric columns
pdf.drawRightString(x + 100, y, nra_formatted)
```

### Multi-Column Table Layout

**When:** Displaying mineral holder data with multiple fields

```python
def draw_table_row(pdf: canvas.Canvas, y: float, row: dict, columns: list[tuple]):
    """Draw a single table row with defined columns.
    
    Args:
        columns: List of (x_position, key, width, align) tuples
    """
    for x, key, width, align in columns:
        value = str(row.get(key, ''))
        if align == 'right':
            pdf.drawRightString(x + width, y, value)
        else:
            pdf.drawString(x, y, value)

# Usage
columns = [
    (50, 'owner_name', 200, 'left'),
    (250, 'nra', 60, 'right'),
    (310, 'decimal', 80, 'right'),
    (390, 'lease_number', 100, 'left'),
]
```

## See Also

- [patterns](references/patterns.md) - Canvas vs Platypus, pagination, error handling
- [workflows](references/workflows.md) - Full export pipeline, testing, debugging

## Related Skills

- **python** - Core Python patterns for service implementation
- **fastapi** - API endpoint integration for PDF downloads
- **pydantic** - Data validation for proration models
- **pandas** - Data preparation before PDF generation

## Documentation Resources

> Fetch latest ReportLab documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "reportlab"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/reportlab/reportlab` _(resolve using mcp__plugin_context7_context7__resolve-library-id, prefer /websites/ when available)_

**Recommended Queries:**
- "reportlab platypus table styling"
- "reportlab canvas coordinate system"
- "reportlab page templates and headers"
- "reportlab number formatting and alignment"