# Activation & Onboarding Reference

## Contents
- Auth Gate → Dashboard Transition
- Tool Discovery on Dashboard
- First Upload Guidance
- Empty State Patterns
- Critical Friction Points

---

## Auth Gate → Dashboard Transition

**Route definition** (`frontend/src/App.tsx`):
```typescript
// Public: /login
// Protected: everything under "/" wrapped in ProtectedRoute
<Route path="/login" element={<Login />} />
<Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
  <Route index element={<Dashboard />} />
  ...
</Route>
```

`ProtectedRoute` checks `useAuth()` for `user` + `isAuthorized`. New users who sign in but aren't on the allowlist (`data/allowed_users.json`) hit `isAuthorized = false` → redirected back to `/login` with no explanation.

**GOOD - Show "access pending" instead of silent redirect:**
```typescript
// frontend/src/App.tsx — ProtectedRoute
if (!user) return <Navigate to="/login" replace />;
if (!isAuthorized) return <UnauthorizedScreen email={user.email} />;
```

**BAD - Current behavior silently redirects:**
```typescript
if (!user || !isAuthorized) return <Navigate to="/login" replace />;
// User sees login form again with no indication why
```

**Why this breaks:** Authorized users who get provisioned mid-session never know their request was received. Support burden increases.

---

## Tool Discovery on Dashboard

Dashboard (`frontend/src/pages/Dashboard.tsx`) renders 5 tool cards with usage counts pulled from `/api/history/jobs`. This is the **primary navigation surface** — every session starts here.

**Current state:** Tool cards show description + "times used" count. No indication of which tool to start with or what prerequisites exist.

**GOOD - Add workflow ordering hint:**
```typescript
// Dashboard.tsx — toolConfigs
const toolConfigs = [
  {
    name: 'Extract',
    description: 'Extract party names from OCC Exhibit A PDFs',
    workflowHint: 'Typically first step for OCC document processing',
    ...
  },
  {
    name: 'Proration',
    description: 'NRA calculations using RRC lease data',
    workflowHint: 'Requires RRC data — download from Settings first',
    ...
  },
]
```

**BAD - Generic descriptions that don't guide task selection:**
```typescript
description: 'Process documents'  // No context about when to use this tool
```

---

## First Upload Guidance

Every tool page uses `FileUpload` component. The accepted file types differ per tool:
- Extract: `.pdf`
- Title: `.xlsx`, `.csv`
- Proration: `.csv`
- Revenue: `.pdf` (multiple)
- GHL Prep: `.csv`

**WARNING: Missing Validation Feedback**

The `FileUpload` component silently drops invalid files with no user-visible error. Users drag wrong file types and see no response.

**GOOD - Show validation error inline:**
```typescript
// frontend/src/components/FileUpload.tsx
const [dropError, setDropError] = useState<string | null>(null);

const handleDrop = (e: React.DragEvent) => {
  setDropError(null);
  const files = Array.from(e.dataTransfer.files);
  const valid = files.filter(f =>
    accept.split(',').some(ext => f.name.toLowerCase().endsWith(ext.trim()))
  );
  if (valid.length === 0) {
    setDropError(`Expected ${accept} — got ${files[0]?.name}`);
    return;
  }
  onFileSelect(valid);
};

// Render below upload zone
{dropError && <p className="text-red-500 text-sm mt-2">{dropError}</p>}
```

---

## Empty State Patterns

Each tool page has two empty states: before first upload (onboarding) and after processing with zero results (data quality issue). Both need distinct messaging.

**GOOD - Differentiate pre-upload vs zero-results:**
```typescript
// pages/Extract.tsx
if (!hasEverUploaded) {
  return (
    <div className="text-center py-16">
      <FileSearch className="w-16 h-16 mx-auto text-tre-teal mb-4" />
      <h3 className="text-xl font-semibold mb-2">Upload an OCC Exhibit A PDF</h3>
      <p className="text-gray-500 mb-6">
        Drag a PDF here or click to browse. Supports single and multi-exhibit files.
      </p>
    </div>
  );
}

if (results.length === 0) {
  return (
    <div className="text-center py-12 text-amber-700 bg-amber-50 rounded-xl">
      <AlertCircle className="w-12 h-12 mx-auto mb-3" />
      <p>No parties found. The PDF may be scanned — try a text-based PDF.</p>
    </div>
  );
}
```

**BAD - Single generic empty state:**
```typescript
{results.length === 0 && <p className="text-gray-500">No results</p>}
```

---

## Critical Friction Points

### 1. Proration Requires RRC Data — No Prereq Check

Users upload a mineral holders CSV to `/proration` only to get a backend error because RRC data hasn't been downloaded.

**Fix:** Check RRC status on page mount and show a blocking banner:
```typescript
// pages/Proration.tsx
const [rrcMissing, setRrcMissing] = useState(false);

useEffect(() => {
  fetch('/api/proration/rrc/status')
    .then(r => r.json())
    .then(s => setRrcMissing(s.oil_count === 0 && s.gas_count === 0));
}, []);

{rrcMissing && (
  <div className="bg-yellow-50 border border-yellow-300 rounded-xl p-4 mb-4">
    <p className="font-semibold text-yellow-800">RRC Data Required</p>
    <p className="text-sm text-yellow-700 mt-1">
      Download RRC lease data before processing mineral holders.
    </p>
    <button
      onClick={() => navigate('/settings')}
      className="mt-3 text-sm text-yellow-800 underline"
    >
      Go to Settings → Download RRC Data
    </button>
  </div>
)}
```

### 2. GHL Connection Required Before Send

The GHL send flow fails if no sub-account is connected. No pre-flight check exists.

**Fix:** Verify GHL connection state before showing the Send button in `GhlPrep.tsx`.

See the **designing-onboarding-paths** skill for full empty state implementation patterns.
