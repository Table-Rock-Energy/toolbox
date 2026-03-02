# ReportLab Patterns Reference

## Contents
- Canvas API vs Platypus (When to Use Each)
- Pagination and Page Breaks
- Numeric Alignment and Formatting
- Error Handling for PDF Generation
- WARNING: Manual Coordinate Calculations

---

## Canvas API vs Platypus

### Canvas API: Proration Export Use Case

The project uses **Canvas API** (`reportlab.pdfgen.canvas`) in `export_service.py` for precise control over layout.

```python
# toolbox/backend/app/services/proration/export_service.py pattern
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_pdf(rows: list[dict]) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    y = height - 100  # Start position
    for row in rows:
        pdf.drawString(50, y, row['owner'])
        pdf.drawRightString(300, y, f"{row['nra']:.4f}")
        y -= 20
        
        if y < 50:  # Manual page break
            pdf.showPage()
            y = height - 50
    
    pdf.save()
    buffer.seek(0)
    return buffer
```

**Why Canvas:** Direct control over x/y coordinates, no automatic layout overhead, simpler for tabular data with fixed columns.

### Platypus: When Reports Get Complex

**Use Platypus when:**
- Multi-paragraph text with automatic wrapping
- Mixed content (tables + paragraphs + images)
- Need automatic page breaks and flowables

```python
# GOOD - Platypus for complex layouts
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def create_complex_report(data: dict) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    elements.append(Paragraph("Proration Report", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Summary text
    summary = f"Total Mineral Holders: {len(data['rows'])}"
    elements.append(Paragraph(summary, styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Table
    table_data = [[col for col in data['headers']]]
    for row in data['rows']:
        table_data.append([row[key] for key in data['headers']])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
```

**DO:**
- Use Canvas for simple tabular exports (current proration pattern)
- Use Platypus for reports with mixed content types
- Stick with Canvas if you're already using it and it works

**DON'T:**
- Mix Canvas and Platypus in the same document (they conflict)
- Use Canvas for long paragraphs (no automatic wrapping)
- Use Platypus if you need pixel-perfect positioning

---

## Pagination and Page Breaks

### Manual Pagination with Canvas

```python
# GOOD - Track y-position and insert page breaks
def export_with_pagination(rows: list[dict]) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    y = height - 100
    row_height = 20
    bottom_margin = 50
    page_num = 1
    
    for idx, row in enumerate(rows):
        # Check if we need a new page BEFORE drawing
        if y < bottom_margin:
            pdf.showPage()  # Finalize current page
            page_num += 1
            y = height - 100  # Reset y-position
        
        pdf.drawString(50, y, row['owner'])
        y -= row_height
    
    pdf.save()
    buffer.seek(0)
    return buffer
```

### WARNING: Off-by-One Page Break Errors

**The Problem:**

```python
# BAD - Page break after drawing causes clipped content
for row in rows:
    pdf.drawString(50, y, row['owner'])  # Draws below margin
    y -= 20
    if y < 50:  # Too late, already drew past the margin
        pdf.showPage()
        y = height - 50
```

**Why This Breaks:**
1. Content drawn at y=40 (below 50px margin) gets clipped
2. User sees incomplete data at page bottom
3. Debugging is hard because it only fails with certain row counts

**The Fix:**

```python
# GOOD - Check BEFORE drawing
for row in rows:
    if y < 50:  # Check first
        pdf.showPage()
        y = height - 50
    pdf.drawString(50, y, row['owner'])  # Now safe to draw
    y -= 20
```

**When You Might Be Tempted:**
- "It's just one line, I'll check after" - NO. Always check before.
- "I'll add extra margin later" - NO. Fix the logic, not the symptoms.

---

## Numeric Alignment and Formatting

### Right-Align Decimals in Tables

```python
# GOOD - Right-align numeric columns for readability
def draw_numeric_column(pdf: canvas.Canvas, x: float, y: float, value: float, decimals: int):
    """Draw right-aligned number with consistent decimal precision."""
    formatted = f"{value:.{decimals}f}"
    pdf.drawRightString(x, y, formatted)

# Usage in proration export
columns = {
    'owner': (50, 'left', 200),      # (x, align, width)
    'nra': (250, 'right', 60),       # NRA uses 4 decimals
    'decimal': (310, 'right', 80),   # Decimal uses 6 decimals
}

for row in data:
    y_pos = current_y
    
    # Left-aligned text
    pdf.drawString(columns['owner'][0], y_pos, row['owner_name'])
    
    # Right-aligned numbers
    draw_numeric_column(pdf, columns['nra'][0] + columns['nra'][2], y_pos, row['nra'], 4)
    draw_numeric_column(pdf, columns['decimal'][0] + columns['decimal'][2], y_pos, row['decimal'], 6)
```

**Why This Matters:**
- Decimal points align vertically for easy comparison
- Consistent precision matches proration calculation standards (see **pydantic** skill for model definitions)
- Right-alignment is standard for numeric data in financial reports

### WARNING: Floating Point Display Bugs

**The Problem:**

```python
# BAD - Inconsistent decimal display
pdf.drawString(x, y, str(0.12345678))  # Might show "0.12345678" or "0.123457"
pdf.drawString(x, y, f"{0.1:.10f}")     # Shows "0.1000000000" - misleading precision
```

**Why This Breaks:**
1. `str(float)` uses arbitrary precision, inconsistent output
2. Over-formatting (10 decimals for 1 sig fig) implies false accuracy
3. Users trust the displayed precision, leading to calculation errors

**The Fix:**

```python
# GOOD - Match precision to actual calculation accuracy
# Proration uses 4 decimals for NRA, 6 for decimal interest
nra_display = f"{nra_value:.4f}"        # 0.1234
decimal_display = f"{decimal_value:.6f}" # 0.123456

# Always use consistent formatting helper
def format_nra(value: float) -> str:
    """Format NRA with project-standard 4 decimal precision."""
    return f"{value:.4f}"

def format_decimal(value: float) -> str:
    """Format decimal interest with 6 decimal precision."""
    return f"{value:.6f}"
```

**When You Might Be Tempted:**
- "I'll just use str() for simplicity" - NO. Precision matters in financial calculations.
- "More decimals = more accurate" - NO. Match precision to calculation accuracy.

---

## Error Handling for PDF Generation

### Graceful Fallback for Missing Data

```python
# GOOD - Handle missing/invalid data without crashing PDF generation
def safe_format_nra(row: dict) -> str:
    """Safely format NRA, defaulting to '0.0000' if missing."""
    try:
        nra = float(row.get('nra', 0))
        return f"{nra:.4f}"
    except (ValueError, TypeError):
        logger.warning(f"Invalid NRA value for row: {row.get('owner_name', 'unknown')}")
        return "0.0000"

def generate_pdf_with_validation(rows: list[dict]) -> BytesIO:
    """Generate PDF with error handling for malformed data."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    valid_rows = []
    for row in rows:
        if not row.get('owner_name'):
            logger.warning(f"Skipping row with missing owner_name: {row}")
            continue
        valid_rows.append(row)
    
    if not valid_rows:
        raise ValueError("No valid rows to export")
    
    # Proceed with valid_rows...
    pdf.save()
    buffer.seek(0)
    return buffer
```

**DO:**
- Log warnings for malformed data, don't silently skip
- Provide default values for optional fields
- Validate critical fields (owner name, decimals) before PDF generation
- Raise clear exceptions if PDF cannot be generated

**DON'T:**
- Catch all exceptions and return empty PDF (user won't know what failed)
- Use `try/except` around the entire function (too broad)
- Ignore validation - users will blame the PDF tool for upstream data issues

---

## WARNING: Manual Coordinate Calculations

**The Problem:**

The current implementation in `export_service.py` uses hardcoded x/y coordinates.

```python
# BAD - Hardcoded coordinates are brittle
pdf.drawString(50, y, owner)       # x=50 hardcoded
pdf.drawString(250, y, nra)        # x=250 hardcoded
pdf.drawString(350, y, decimal)    # x=350 hardcoded

# What happens when you add a column?
# All downstream x-coordinates must be manually adjusted
```

**Why This Breaks:**
1. Adding/removing columns requires updating 10+ hardcoded numbers
2. Column width changes ripple through entire file
3. Easy to introduce alignment bugs (e.g., header x=50, data x=55)
4. No compile-time checks for overlapping columns

**The Fix:**

```python
# GOOD - Define column layout once, calculate positions
from dataclasses import dataclass

@dataclass
class ColumnDef:
    key: str
    label: str
    width: int
    align: str  # 'left' | 'right' | 'center'

# Single source of truth for table layout
PRORATION_COLUMNS = [
    ColumnDef('owner_name', 'Owner', 200, 'left'),
    ColumnDef('nra', 'NRA', 60, 'right'),
    ColumnDef('decimal', 'Decimal', 80, 'right'),
    ColumnDef('lease_number', 'Lease #', 100, 'left'),
]

def calculate_column_positions(columns: list[ColumnDef], margin: int = 50, spacing: int = 10):
    """Calculate x-positions from column definitions."""
    positions = []
    x = margin
    for col in columns:
        positions.append((col, x))
        x += col.width + spacing
    return positions

# Usage
column_positions = calculate_column_positions(PRORATION_COLUMNS)

for col, x in column_positions:
    # Header
    pdf.drawString(x, header_y, col.label)
    
    # Data rows
    for row in data:
        value = format_value(row[col.key], col.align)
        if col.align == 'right':
            pdf.drawRightString(x + col.width, data_y, value)
        else:
            pdf.drawString(x, data_y, value)
```

**When You Might Be Tempted:**
- "It's just a few columns, hardcoding is faster" - Until you need to add a column.
- "I'll refactor later" - Later never comes, and the technical debt grows.
- "The layout won't change" - Requirements always change.

**Refactoring Checklist:**

Copy this checklist when refactoring coordinate logic:
- [ ] Extract column definitions to constants (dataclass or dict)
- [ ] Write `calculate_column_positions()` helper
- [ ] Replace all hardcoded x-coordinates with calculated positions
- [ ] Test with different column counts (3, 5, 10 columns)
- [ ] Verify alignment for left/right/center columns
- [ ] Check page width constraints (sum of widths < page width)