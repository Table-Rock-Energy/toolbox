# Activation & Onboarding Reference

## Contents
- Initial Landing Experience
- Tool Discovery Flow
- First Upload Guidance
- Empty State Patterns
- Common Friction Points

---

## Initial Landing Experience

### Auth Gate → Dashboard Transition

The first impression starts at login and continues through the Dashboard. This transition must be seamless.

**Current Flow:**
1. User visits root `/` → redirects to `/login` (see `frontend/src/App.tsx`)
2. Firebase auth completes → `AuthContext` updates state
3. `ProtectedRoute` wrapper allows access to `/dashboard`
4. Dashboard renders tool cards with usage stats

**GOOD - Clear post-auth redirect:**
```typescript
// frontend/src/contexts/AuthContext.tsx
useEffect(() => {
  const unsubscribe = onAuthStateChanged(auth, (user) => {
    setUser(user);
    setLoading(false);
    if (user && window.location.pathname === '/login') {
      navigate('/dashboard'); // Explicit redirect after auth
    }
  });
  return unsubscribe;
}, [navigate]);
```

**BAD - User stuck on login screen after auth:**
```typescript
// Missing redirect logic - user must manually navigate
setUser(user);
setLoading(false);
// No navigation happens here
```

**Why This Breaks:** Users see the login screen briefly flash to "authenticated" state but don't know where to go next. Creates confusion about whether login succeeded.

---

## Tool Discovery Flow

### Dashboard as Navigation Hub

Dashboard must clearly communicate what each tool does and when to use it.

**Current Implementation:**
- `frontend/src/pages/Dashboard.tsx` renders 4 tool cards
- Each card has icon, title, description, and "Open Tool" button
- No usage stats or "suggested next tool" guidance

**GOOD - Add first-time user hints:**
```typescript
// Dashboard.tsx - Add helpful context for new users
const tools = [
  {
    name: 'Extract',
    description: 'Extract party names from OCC Exhibit A PDFs',
    hint: 'Start here if you have Oklahoma Corporation Commission documents',
    route: '/extract',
  },
  // ...
];

{tool.hint && !hasUsedTool(tool.name) && (
  <p className="text-sm text-tre-teal mt-2">💡 {tool.hint}</p>
)}
```

**BAD - Generic descriptions with no context:**
```typescript
description: 'Process documents' // Too vague
```

**Why This Breaks:** New users don't know which tool matches their task. They either guess wrong (frustration) or ask for help (support burden).

**WARNING: Missing Onboarding Checklist**

The current app has NO first-run checklist or progressive disclosure. Consider adding:
- "Complete your first extraction" badge
- "Download RRC data" setup step for Proration users
- In-app tooltip system (e.g., `react-joyride`) for guided tours

---

## First Upload Guidance

### File Upload Validation Feedback

Users need immediate, actionable feedback when uploads fail validation.

**Current Pattern (FileUpload.tsx):**
```typescript
// frontend/src/components/FileUpload.tsx
const handleDrop = (e: React.DragEvent) => {
  const files = Array.from(e.dataTransfer.files);
  const validFiles = files.filter(f => 
    accept.split(',').some(type => f.name.endsWith(type.trim()))
  );
  
  if (validFiles.length === 0) {
    // ERROR: No user-visible feedback here
    return;
  }
  onFileSelect(validFiles);
};
```

**GOOD - Show specific validation errors:**
```typescript
const [validationError, setValidationError] = useState<string | null>(null);

const handleDrop = (e: React.DragEvent) => {
  setValidationError(null);
  const files = Array.from(e.dataTransfer.files);
  const invalidFiles = files.filter(f => 
    !accept.split(',').some(type => f.name.endsWith(type.trim()))
  );
  
  if (invalidFiles.length > 0) {
    setValidationError(
      `Invalid file type: ${invalidFiles[0].name}. Expected: ${accept}`
    );
    return;
  }
  onFileSelect(files);
};

// Render error below upload area
{validationError && (
  <p className="text-red-500 text-sm mt-2">{validationError}</p>
)}
```

**Why This Breaks:** Silent validation failures leave users wondering if their drag-and-drop worked. They retry multiple times before giving up.

---

## Empty State Patterns

### Zero-Data Screens

Every tool should have a helpful empty state before first use.

**GOOD - Extract page empty state:**
```typescript
// pages/Extract.tsx
{!results || results.length === 0 ? (
  <div className="text-center py-12">
    <FileText className="w-16 h-16 mx-auto text-tre-teal mb-4" />
    <h3 className="text-xl mb-2">No parties extracted yet</h3>
    <p className="text-gray-600 mb-4">
      Upload an OCC Exhibit A PDF to get started
    </p>
    <FileUpload 
      accept=".pdf"
      onFileSelect={handleUpload}
      label="Drop your PDF here or click to browse"
    />
  </div>
) : (
  <DataTable data={results} columns={columns} />
)}
```

**BAD - Blank screen or generic "No data":**
```typescript
{results.length === 0 && <p>No results</p>}
```

**Why This Breaks:** New users see an empty table and don't know what to do next. No call-to-action or guidance.

---

## Common Friction Points

### 1. RRC Data Prerequisite for Proration

**The Problem:** Users upload mineral holders CSV to Proration tool, but RRC data hasn't been downloaded yet. Backend returns cryptic error.

**Current Error Response:**
```python
# backend/app/api/proration.py
if not rrc_service.has_data():
    raise HTTPException(status_code=400, detail="RRC data not available")
```

**GOOD - Proactive empty state check:**
```typescript
// pages/Proration.tsx
const [rrcStatus, setRrcStatus] = useState<{oil: number, gas: number} | null>(null);

useEffect(() => {
  fetch('/api/proration/rrc/status')
    .then(r => r.json())
    .then(setRrcStatus);
}, []);

if (rrcStatus && rrcStatus.oil === 0 && rrcStatus.gas === 0) {
  return (
    <div className="bg-yellow-50 border border-yellow-200 p-4 rounded">
      <h3>⚠️ RRC Data Required</h3>
      <p>Download RRC lease data before using the Proration tool.</p>
      <button onClick={() => navigate('/settings')}>Download Now</button>
    </div>
  );
}
```

**Why This Breaks:** Users waste time uploading CSV, processing fails, then they have to figure out what "RRC data" means and where to get it.

### 2. No Progress Indicator for Long Operations

**The Problem:** RRC download takes 30-60 seconds. User sees frozen UI and thinks it crashed.

**Current Implementation (backend):**
```python
# backend/app/api/proration.py
@router.post("/rrc/download")
async def download_rrc_data():
    result = await rrc_service.download_and_sync()  # Takes 30-60s
    return result
```

**GOOD - Streaming status updates or polling:**
```typescript
// Frontend polling pattern
const [downloadStatus, setDownloadStatus] = useState<string>('idle');

const handleDownload = async () => {
  setDownloadStatus('downloading');
  fetch('/api/proration/rrc/download', {method: 'POST'});
  
  // Poll for completion
  const interval = setInterval(async () => {
    const status = await fetch('/api/proration/rrc/status').then(r => r.json());
    if (status.oil > 0 && status.gas > 0) {
      setDownloadStatus('complete');
      clearInterval(interval);
    }
  }, 2000);
};

{downloadStatus === 'downloading' && (
  <div>
    <LoadingSpinner />
    <p>Downloading RRC data... This may take up to 1 minute.</p>
  </div>
)}
```

**Why This Breaks:** Users close the browser tab thinking the app froze, interrupting the download. Support requests spike.

### 3. Missing "What Happens Next?" After Export

**The Problem:** User clicks "Export to CSV" → file downloads → then what? No guidance on using the exported data.

**GOOD - Post-export guidance:**
```typescript
const [exportComplete, setExportComplete] = useState(false);

const handleExport = async () => {
  const blob = await fetch('/api/extract/export/csv', {
    method: 'POST',
    body: JSON.stringify({entries: results}),
  }).then(r => r.blob());
  
  // Trigger download
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'parties.csv';
  a.click();
  
  setExportComplete(true);
};

{exportComplete && (
  <div className="bg-green-50 border border-green-200 p-4 rounded mt-4">
    <h3>✅ Export Complete</h3>
    <p>Your CSV has been downloaded. Next steps:</p>
    <ul className="list-disc ml-6">
      <li>Open in Excel or Google Sheets</li>
      <li>Review party names for accuracy</li>
      <li>Upload to your internal CRM</li>
    </ul>
  </div>
)}
```

**Why This Breaks:** Export feels like a dead-end. Users don't know if they should stay on the page, start a new extraction, or close the browser.