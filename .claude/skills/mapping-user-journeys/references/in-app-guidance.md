# In-App Guidance Reference

## Contents
- Contextual Help Text
- Error Message Clarity
- Tooltip Patterns
- Field Validation Feedback
- Help Page Discoverability

---

## Contextual Help Text

### Inline Guidance Without Clutter

Help text should be visible when needed, invisible when not.

**GOOD - Expandable help sections:**
```typescript
// pages/Proration.tsx
const [showHelp, setShowHelp] = useState(false);

<div className="bg-gray-50 border border-gray-200 p-4 rounded mb-4">
  <button 
    onClick={() => setShowHelp(!showHelp)}
    className="flex items-center gap-2 text-tre-teal hover:underline"
  >
    <HelpCircle className="w-4 h-4" />
    <span>What is Net Revenue Acreage (NRA)?</span>
    {showHelp ? <ChevronUp /> : <ChevronDown />}
  </button>
  
  {showHelp && (
    <div className="mt-3 text-sm text-gray-700">
      <p>NRA = Gross Acres × Royalty Interest × Ownership %</p>
      <p className="mt-2">
        This calculation determines your proportional share of revenue 
        from oil and gas production based on RRC proration data.
      </p>
    </div>
  )}
</div>
```

**BAD - Always-visible walls of text:**
```typescript
<div className="mb-4">
  <p>Net Revenue Acreage (NRA) is calculated by multiplying gross acres...</p>
  <p>This is important because...</p>
  <p>You should use this when...</p>
  {/* 200 more lines of explanation */}
</div>
```

**Why This Breaks:** Expert users who run calculations daily must scroll past help text every time. They disable guides or work around them.

---

## Error Message Clarity

### Backend Validation Errors

FastAPI returns detailed validation errors, but they're often too technical for end users.

**Current Pattern:**
```python
# backend/app/api/proration.py
if not csv_file.filename.endswith('.csv'):
    raise HTTPException(
        status_code=400,
        detail="Invalid file type: application/octet-stream. Expected text/csv"
    )
```

**GOOD - User-friendly error mapping:**
```python
# backend/app/api/proration.py
if not csv_file.filename.endswith('.csv'):
    raise HTTPException(
        status_code=400,
        detail={
            "message": "Wrong file type",
            "explanation": "Please upload a CSV file. Excel files (.xlsx) are not supported for this tool.",
            "action": "Convert your Excel file to CSV and try again.",
        }
    )
```

**Frontend display:**
```typescript
// pages/Proration.tsx
if (error) {
  const errorData = typeof error === 'string' ? {message: error} : error;
  
  return (
    <div className="bg-red-50 border border-red-200 p-4 rounded">
      <h4 className="font-bold text-red-800">{errorData.message}</h4>
      {errorData.explanation && <p className="mt-2">{errorData.explanation}</p>}
      {errorData.action && (
        <p className="mt-2 font-semibold text-red-800">→ {errorData.action}</p>
      )}
    </div>
  );
}
```

**Why This Breaks:** Technical errors like "422 Unprocessable Entity: field required" confuse non-technical users. They screenshot and email support instead of self-correcting.

---

## Tooltip Patterns

### Field-Level Tooltips

Complex fields (especially in Title and Proration tools) need inline definitions.

**WARNING: No Tooltip Library Installed**

The project currently has no tooltip component. Consider adding `@radix-ui/react-tooltip` or building a simple custom tooltip:

```typescript
// components/Tooltip.tsx
import { useState } from 'react';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  
  return (
    <div 
      className="relative inline-block"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div className="absolute z-10 bg-gray-800 text-white text-sm rounded px-3 py-2 -top-10 left-0 whitespace-nowrap">
          {content}
          <div className="absolute -bottom-1 left-4 w-2 h-2 bg-gray-800 transform rotate-45" />
        </div>
      )}
    </div>
  );
}
```

**Usage in forms:**
```typescript
// pages/Title.tsx
<label className="flex items-center gap-2">
  <span>Ownership %</span>
  <Tooltip content="Percentage of mineral rights owned (0-100)">
    <HelpCircle className="w-4 h-4 text-gray-400" />
  </Tooltip>
</label>
<input type="number" step="0.01" min="0" max="100" />
```

**Why This Breaks:** Users guess at field meanings, enter invalid data, and get validation errors. Frustration compounds.

---

## Field Validation Feedback

### Real-Time Validation

Validate inputs as users type, not just on submit.

**GOOD - Immediate feedback for CSV column headers:**
```typescript
// pages/Proration.tsx
const [csvPreview, setCsvPreview] = useState<string[]>([]);
const [missingColumns, setMissingColumns] = useState<string[]>([]);

const requiredColumns = ['Owner Name', 'Gross Acres', 'Royalty Interest'];

const handleFileSelect = async (files: File[]) => {
  const text = await files[0].text();
  const lines = text.split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  
  setCsvPreview(headers);
  
  const missing = requiredColumns.filter(col => !headers.includes(col));
  setMissingColumns(missing);
};

{missingColumns.length > 0 && (
  <div className="bg-yellow-50 border border-yellow-200 p-4 rounded">
    <h4>⚠️ Missing Required Columns</h4>
    <ul className="list-disc ml-6">
      {missingColumns.map(col => (
        <li key={col}>{col}</li>
      ))}
    </ul>
    <p className="mt-2">Add these columns to your CSV and re-upload.</p>
  </div>
)}
```

**BAD - Validation only on submit:**
```typescript
// User uploads CSV → clicks "Process" → 5 seconds later gets error
// "Column 'Owner Name' not found"
```

**Why This Breaks:** Users waste time uploading large files only to discover formatting issues. No opportunity to fix before processing.

---

## Help Page Discoverability

### Contextual Links to Help

Help page exists (`frontend/src/pages/Help.tsx`) but users don't find it when stuck.

**Current Problem:**
- Help link only in sidebar navigation
- No in-tool links to relevant Help sections
- Help page is generic, not tool-specific

**GOOD - Link to relevant help from error states:**
```typescript
// pages/Extract.tsx
{error && (
  <div className="bg-red-50 border border-red-200 p-4 rounded">
    <h4 className="font-bold">PDF Extraction Failed</h4>
    <p>{error}</p>
    <a 
      href="/help#extract-troubleshooting"
      className="text-tre-teal hover:underline mt-2 inline-block"
    >
      → View troubleshooting guide
    </a>
  </div>
)}
```

**Update Help page structure:**
```typescript
// pages/Help.tsx
<div id="extract-troubleshooting" className="mb-8">
  <h2 className="text-2xl font-bold mb-4">Extract Tool Issues</h2>
  
  <h3 className="text-xl font-semibold mt-4">Common Problems</h3>
  
  <div className="mt-2">
    <h4 className="font-bold">❌ "No parties found"</h4>
    <p>Cause: PDF is scanned image, not searchable text</p>
    <p>Fix: Run OCR on the PDF before uploading</p>
  </div>
  
  <div className="mt-4">
    <h4 className="font-bold">❌ "Upload failed"</h4>
    <p>Cause: File size exceeds 50MB limit</p>
    <p>Fix: Split multi-document PDF into separate files</p>
  </div>
</div>
```

**Why This Breaks:** Help page becomes a documentation graveyard. Users never visit it because it's not contextually linked from failure points.

---

## Common Guidance Gaps

### 1. No Sample Files

**The Problem:** Users don't know what valid input looks like.

**GOOD - Provide downloadable samples:**
```typescript
// pages/Proration.tsx
<div className="bg-blue-50 border border-blue-200 p-4 rounded mb-4">
  <h4 className="font-bold mb-2">First time using Proration?</h4>
  <p className="mb-2">Download a sample CSV to see the required format:</p>
  <a 
    href="/samples/mineral_holders_sample.csv"
    download
    className="btn-secondary inline-flex items-center gap-2"
  >
    <Download className="w-4 h-4" />
    Download Sample CSV
  </a>
</div>
```

**Backend route to serve samples:**
```python
# backend/app/api/proration.py
@router.get("/sample")
async def get_sample_csv():
    sample_content = "Owner Name,Gross Acres,Royalty Interest,Ownership %\nJohn Doe,100.5,0.125,50.0\n"
    return Response(
        content=sample_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample.csv"}
    )
```

**Why This Breaks:** Users guess at CSV structure, get validation errors, and iterate blindly until it works (or they give up).

### 2. No Field Examples

**The Problem:** Legal description parser accepts multiple formats, but users don't know which.

**GOOD - Show accepted format examples:**
```typescript
// pages/Proration.tsx
<label>Legal Description</label>
<input type="text" placeholder="Section 12, Township 5N, Range 3W" />
<details className="mt-2">
  <summary className="text-sm text-tre-teal cursor-pointer">
    See accepted formats
  </summary>
  <ul className="text-sm text-gray-600 list-disc ml-6 mt-2">
    <li>S12-T5N-R3W</li>
    <li>Section 12, T5N, R3W</li>
    <li>Sec 12 Twp 5N Rge 3W</li>
  </ul>
</details>
```

**Why This Breaks:** Parser rejects user input silently, no feedback on what went wrong or how to fix it.