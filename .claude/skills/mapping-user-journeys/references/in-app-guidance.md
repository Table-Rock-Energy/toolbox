# In-App Guidance Reference

## Contents
- Error Message Clarity
- Prerequisite Banners
- Long-Operation Feedback
- Contextual Help Text
- Post-Action Guidance

---

## Error Message Clarity

Backend `HTTPException` detail strings are the primary error surface. Vague details become unusable UI copy.

**GOOD - Actionable error with recovery path:**
```python
# backend/app/api/proration.py
raise HTTPException(
    status_code=400,
    detail="RRC data not downloaded. Go to Settings → RRC Data to download it first."
)
```

**BAD - Opaque error that dead-ends the user:**
```python
raise HTTPException(status_code=400, detail="RRC data not available")
```

**Why this breaks:** "Not available" gives no action. Users file support tickets or abandon the tool. Every error detail should answer: *what happened and where do I go to fix it?*

Frontend pattern for surfacing errors with a recovery button:
```typescript
// Any tool page — error banner with optional action
{error && (
  <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
    <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
    <div>
      <p className="text-sm text-red-700">{error}</p>
      {errorAction && (
        <button
          onClick={errorAction.handler}
          className="mt-2 text-sm text-red-600 underline"
        >
          {errorAction.label}
        </button>
      )}
    </div>
  </div>
)}
```

---

## Prerequisite Banners

Two tools require setup before first use:

**Proration** — requires RRC data (`/api/proration/rrc/status`)
**GHL Prep → Send** — requires GHL sub-account connection

Both should show a blocking banner at page top, not a post-upload error.

```typescript
// pages/Proration.tsx — check prereq on mount
const [prereqStatus, setPrereqStatus] = useState<'checking' | 'ok' | 'missing'>('checking');

useEffect(() => {
  fetch('/api/proration/rrc/status')
    .then(r => r.json())
    .then(s => setPrereqStatus(
      s.oil_count > 0 || s.gas_count > 0 ? 'ok' : 'missing'
    ))
    .catch(() => setPrereqStatus('ok'));  // Don't block on check failure
}, []);

{prereqStatus === 'missing' && (
  <div className="mb-4 p-4 bg-amber-50 border border-amber-300 rounded-xl">
    <p className="font-semibold text-amber-800">Setup Required</p>
    <p className="text-sm text-amber-700 mt-1">
      RRC lease data must be downloaded before processing mineral holders.
    </p>
    <button
      onClick={() => navigate('/settings')}
      className="mt-2 text-sm text-amber-700 underline"
    >
      Go to Settings → Download RRC Data
    </button>
  </div>
)}
```

---

## Long-Operation Feedback

Three operations take more than a few seconds:
- RRC bulk download (30-60s)
- Revenue PDF batch processing (scales with file count)
- GHL bulk send (SSE-tracked, `useSSEProgress.ts`)

GHL send already uses SSE via `useSSEProgress.ts`. RRC download and revenue batch use polling.

**GOOD - Progress message with time estimate:**
```typescript
// Polling pattern with user-visible status
const [downloadStatus, setDownloadStatus] = useState<'idle' | 'running' | 'done'>('idle');

const handleDownload = async () => {
  setDownloadStatus('running');
  await fetch('/api/proration/rrc/download', { method: 'POST' });

  const poll = setInterval(async () => {
    const s = await fetch('/api/proration/rrc/status').then(r => r.json());
    if (s.oil_count > 0) {
      setDownloadStatus('done');
      clearInterval(poll);
    }
  }, 3000);
};

{downloadStatus === 'running' && (
  <div className="flex items-center gap-3 text-gray-600">
    <LoadingSpinner className="w-5 h-5" />
    <span className="text-sm">Downloading RRC data — this takes about 1 minute...</span>
  </div>
)}
```

**BAD - No feedback during long operation:**
```typescript
const handleDownload = () => fetch('/api/proration/rrc/download', { method: 'POST' });
// User sees nothing for 60 seconds
```

---

## Contextual Help Text

Each tool has domain-specific terminology that internal users may not know. Inline help text placed near the relevant input reduces support requests.

**GOOD - Inline hint near file upload:**
```typescript
// pages/Proration.tsx
<FileUpload
  accept=".csv"
  onFileSelect={handleUpload}
  label="Drop mineral holders CSV or click to browse"
/>
<p className="text-xs text-gray-500 mt-1">
  CSV must include columns: name, legal_description, decimal_interest
</p>
```

**GOOD - Tooltip on ambiguous column headers:**
```typescript
// DataTable — column header with tooltip
<th>
  NRA
  <span title="Net Revenue Acres — calculated from decimal interest × total acres">
    <HelpCircle className="w-3.5 h-3.5 inline ml-1 text-gray-400" />
  </span>
</th>
```

---

## Post-Action Guidance

After export, users need to know what to do with the file. Currently export silently downloads with no follow-up.

**GOOD - Post-export panel:**
```typescript
{exportComplete && (
  <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-xl">
    <div className="flex items-center gap-2 mb-2">
      <CheckCircle className="w-5 h-5 text-green-600" />
      <span className="font-semibold text-green-800">Export complete</span>
    </div>
    <p className="text-sm text-gray-600">Your CSV is in your Downloads folder.</p>
    <button
      onClick={resetForNextUpload}
      className="mt-3 text-sm text-tre-teal underline"
    >
      Process another file
    </button>
  </div>
)}
```

See the **designing-onboarding-paths** skill for full empty state and first-run patterns.
See the **frontend-design** skill for Tailwind patterns using `tre-*` brand colors.
