# Engagement & Adoption Reference

## Contents
- Repeat Usage Patterns
- Feature Discovery Mechanisms
- Tool Switching Friction
- Export Format Adoption
- RRC Data Sync Engagement

---

## Repeat Usage Patterns

### Dashboard Return Rate

Users should naturally return to the Dashboard between tool sessions. Current navigation makes this awkward.

**Current Problem:**
- Sidebar navigation (`frontend/src/components/Sidebar.tsx`) has direct links to all tools
- Users jump from Extract → Title without seeing Dashboard
- No "return home" affordance after completing a task

**GOOD - Add post-task navigation:**
```typescript
// After export completes in any tool
{exportComplete && (
  <div className="mt-6 flex gap-4">
    <button 
      onClick={() => navigate('/dashboard')}
      className="btn-secondary"
    >
      ← Back to Dashboard
    </button>
    <button 
      onClick={() => window.location.reload()}
      className="btn-primary"
    >
      Process Another File
    </button>
  </div>
)}
```

**BAD - No guidance after task completion:**
```typescript
// User stuck on results screen with no clear next action
<button onClick={handleExport}>Export CSV</button>
// ... nothing after this
```

**Why This Breaks:** Users don't develop a mental model of "Dashboard = home base". They bookmark individual tool URLs and bypass the navigation hub.

---

## Feature Discovery Mechanisms

### Hidden Export Formats

Each tool supports multiple export formats (CSV, Excel, PDF for Proration), but users only discover one.

**Current Problem:**
```typescript
// pages/Extract.tsx - All export buttons look identical
<button onClick={exportCSV}>Export CSV</button>
<button onClick={exportExcel}>Export Excel</button>
```

**GOOD - Show format benefits and use cases:**
```typescript
const exportOptions = [
  {
    format: 'CSV',
    icon: FileText,
    description: 'Plain text format for databases and scripts',
    action: exportCSV,
  },
  {
    format: 'Excel',
    icon: FileSpreadsheet,
    description: 'Formatted spreadsheet with headers and filters',
    action: exportExcel,
  },
];

<div className="grid grid-cols-2 gap-4">
  {exportOptions.map(opt => (
    <button 
      key={opt.format}
      onClick={opt.action}
      className="p-4 border rounded hover:bg-tre-navy hover:text-white"
    >
      <opt.icon className="w-8 h-8 mb-2" />
      <h4 className="font-bold">{opt.format}</h4>
      <p className="text-sm text-gray-600">{opt.description}</p>
    </button>
  ))}
</div>
```

**Why This Breaks:** Users default to the first button they see (usually CSV) and never realize Excel exports have better formatting or that PDF exports exist for Proration.

---

## Tool Switching Friction

### Losing Work on Navigation

React Router unmounts components when navigating, losing unsaved state.

**Current Problem:**
```typescript
// User uploads CSV to Proration → processes → sees results
// User clicks "Help" in sidebar → component unmounts
// User clicks "Proration" again → all results gone
```

**GOOD - Persist results in sessionStorage:**
```typescript
// pages/Proration.tsx
const [results, setResults] = useState<MineralHolderRow[]>(() => {
  const cached = sessionStorage.getItem('proration-results');
  return cached ? JSON.parse(cached) : [];
});

useEffect(() => {
  if (results.length > 0) {
    sessionStorage.setItem('proration-results', JSON.stringify(results));
  }
}, [results]);

// Clear on explicit reset
const handleReset = () => {
  setResults([]);
  sessionStorage.removeItem('proration-results');
};
```

**BAD - No state persistence:**
```typescript
const [results, setResults] = useState<MineralHolderRow[]>([]);
// Lost on unmount
```

**Why This Breaks:** Users avoid exploring Help or Settings because they know it will destroy their work. Feature engagement drops.

---

## Export Format Adoption

### PDF Export Underutilization (Proration)

The Proration tool generates formatted PDF reports, but most users export to Excel and manually format.

**Current Implementation:**
```typescript
// pages/Proration.tsx
<button onClick={exportExcel}>Export Excel</button>
<button onClick={exportPDF}>Export PDF</button>
```

**GOOD - Show PDF preview or highlight benefits:**
```typescript
const [showPdfPreview, setShowPdfPreview] = useState(false);

<button 
  onClick={() => setShowPdfPreview(true)}
  className="btn-secondary"
>
  Preview PDF Report
</button>

{showPdfPreview && (
  <Modal onClose={() => setShowPdfPreview(false)}>
    <h3>PDF Report Features</h3>
    <ul className="list-disc ml-6 mb-4">
      <li>Formatted for printing and email</li>
      <li>Includes legal descriptions and NRA calculations</li>
      <li>Professional layout with Table Rock branding</li>
    </ul>
    <button onClick={exportPDF}>Download PDF</button>
  </Modal>
)}
```

**Why This Breaks:** Users don't realize PDFs are print-ready and client-facing quality. They waste time reformatting Excel exports.

---

## RRC Data Sync Engagement

### Monthly Update Awareness

RRC data updates monthly (1st of month, 2 AM via APScheduler), but users don't know when it was last updated.

**Current Problem:**
```python
# backend/app/api/proration.py
@router.get("/rrc/status")
async def get_rrc_status():
    return {
        "oil_count": len(rrc_service.oil_data),
        "gas_count": len(rrc_service.gas_data),
    }
```

**GOOD - Show last update timestamp and staleness:**
```python
# Add to status response
return {
    "oil_count": len(rrc_service.oil_data),
    "gas_count": len(rrc_service.gas_data),
    "last_updated": rrc_service.last_download_time,  # ISO timestamp
    "is_stale": rrc_service.is_data_stale(),  # > 35 days old
}
```

**Frontend display:**
```typescript
// pages/Proration.tsx
{rrcStatus?.is_stale && (
  <div className="bg-yellow-50 border border-yellow-200 p-4 rounded mb-4">
    <h4>⚠️ RRC Data May Be Outdated</h4>
    <p>Last updated: {new Date(rrcStatus.last_updated).toLocaleDateString()}</p>
    <button onClick={handleManualSync}>Update Now</button>
  </div>
)}
```

**Why This Breaks:** Users process mineral holders with stale RRC data, get incorrect NRA calculations, and blame the tool for inaccuracy.

---

## Common Engagement Killers

### 1. No Batch Processing

**The Problem:** Revenue tool accepts multiple PDFs, but Extract/Title/Proration only process one file at a time. Users with 20 documents must manually repeat 20 times.

**Current Pattern:**
```typescript
// pages/Extract.tsx
<FileUpload 
  accept=".pdf"
  multiple={false}  // Only single file
  onFileSelect={handleUpload}
/>
```

**GOOD - Add batch mode:**
```typescript
const [batchMode, setBatchMode] = useState(false);

<label className="flex items-center gap-2 mb-4">
  <input 
    type="checkbox" 
    checked={batchMode}
    onChange={e => setBatchMode(e.target.checked)}
  />
  <span>Process multiple files</span>
</label>

<FileUpload 
  accept=".pdf"
  multiple={batchMode}
  onFileSelect={handleBatchUpload}
/>

{batchMode && (
  <p className="text-sm text-gray-600">
    Upload up to 10 PDFs. Results will be combined into one export.
  </p>
)}
```

**Why This Breaks:** High-volume users abandon the tool and revert to manual processing. Adoption plateaus.

### 2. No Saved Searches or Filters

**The Problem:** DataTable component supports filtering, but filters reset on page refresh.

**GOOD - Persist filter state:**
```typescript
// components/DataTable.tsx
const [filters, setFilters] = useState<Record<string, string>>(() => {
  const cached = sessionStorage.getItem(`filters-${tableName}`);
  return cached ? JSON.parse(cached) : {};
});

useEffect(() => {
  sessionStorage.setItem(`filters-${tableName}`, JSON.stringify(filters));
}, [filters, tableName]);
```

**Why This Breaks:** Users who repeatedly filter for "Oklahoma County" or "Trust" entries must re-enter filters every session. Feature feels half-baked.

### 3. No Keyboard Shortcuts

**The Problem:** Power users (land team processing 50+ documents daily) rely on mouse for everything.

**GOOD - Add common shortcuts:**
```typescript
// pages/Extract.tsx
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.metaKey || e.ctrlKey) {
      if (e.key === 'u') {
        e.preventDefault();
        document.getElementById('file-upload-input')?.click();
      } else if (e.key === 'e') {
        e.preventDefault();
        exportCSV();
      }
    }
  };
  
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, [exportCSV]);

// Show shortcuts in UI
<div className="text-sm text-gray-500 mt-2">
  Shortcuts: Cmd+U to upload, Cmd+E to export
</div>
```

**Why This Breaks:** Power users feel the tool is "slow" even though processing is fast. They want keyboard-driven workflows.