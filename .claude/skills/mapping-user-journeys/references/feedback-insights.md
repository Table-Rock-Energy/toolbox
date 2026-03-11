# Feedback & Insights Reference

## Contents
- Reading Friction from Job Data
- Backend Error Signal Analysis
- Frontend State Gap Audit
- Common Error Patterns
- Acting on Signals

---

## Reading Friction from Job Data

Job records in Firestore are the primary friction signal. High `error_count` relative to `total_count`, or jobs with `status: "failed"`, indicate where users are struggling.

```bash
# Find tools with high failure rates
curl "http://localhost:8000/api/history/jobs?limit=500" | \
  python3 -c "
import json, sys, collections
data = json.load(sys.stdin)
by_tool = collections.defaultdict(lambda: {'jobs': 0, 'failed': 0})
for j in data['jobs']:
    by_tool[j['tool']]['jobs'] += 1
    if j.get('status') == 'failed':
        by_tool[j['tool']]['failed'] += 1
for t, s in sorted(by_tool.items()):
    rate = s['failed']/s['jobs']*100 if s['jobs'] else 0
    print(f'{t}: {s[\"failed\"]}/{s[\"jobs\"]} failed ({rate:.1f}%)')
"
```

High failure rate on a tool = look at backend logs + `HTTPException` detail strings for that tool.

---

## Backend Error Signal Analysis

FastAPI logs every unhandled exception. Key places to look:

```bash
# Production: Cloud Run logs
gcloud logs read "resource.type=cloud_run_revision" \
  --format="value(textPayload)" \
  --filter="severity=ERROR" \
  --project=tablerockenergy | head -50

# Local dev: backend stdout
make dev-backend 2>&1 | grep -E "ERROR|HTTPException|500"
```

**Most common error categories by tool:**

| Tool | Common Error | Root Cause |
|------|-------------|------------|
| Extract | 500 on upload | Scanned/image PDF, no text layer |
| Proration | 400 "RRC data not available" | RRC not downloaded |
| Proration | 400 on upload | CSV missing required columns |
| Revenue | 422 parsing failure | Unrecognized PDF format |
| GHL Prep | 400 on send | GHL connection not configured |

---

## Frontend State Gap Audit

Run this grep to find tool pages missing required state coverage:

```bash
# Check which pages handle all 4 states
for page in frontend/src/pages/*.tsx; do
  echo "=== $page ==="
  grep -c "isLoading\|isProcessing" "$page" || echo "  MISSING: loading state"
  grep -c "setError\|error &&" "$page" || echo "  MISSING: error state"
  grep -c "length === 0\|!results" "$page" || echo "  MISSING: empty state"
  echo ""
done
```

Pages missing any of these will create invisible friction — users see blank screens or no feedback during failures.

---

## Common Error Patterns

### Pattern 1: Silent Upload Validation Failure

**Signal:** Users report "dragging a file does nothing."

**Root cause:** `FileUpload` component silently drops invalid file types with no feedback. No `validationError` state exists in the component.

**Fix location:** `frontend/src/components/FileUpload.tsx`

```typescript
// Add to handleDrop:
const rejected = files.filter(f =>
  !accept.split(',').some(ext => f.name.toLowerCase().endsWith(ext.trim()))
);
if (rejected.length > 0) {
  setValidationError(`${rejected[0].name} is not a supported file type. Expected: ${accept}`);
  return;
}
```

### Pattern 2: RRC Download Appears Frozen

**Signal:** Users close the tab mid-download, complain "the app crashed."

**Root cause:** `/api/proration/rrc/download` is a long-running endpoint (30-60s). No progress signal reaches the frontend.

**Fix location:** `frontend/src/pages/Proration.tsx` (or Settings page where download is triggered)

Use the existing polling pattern from `rrc/status` every 3 seconds to show progress.

### Pattern 3: Unauthorized Users Stuck at Login

**Signal:** New users report being stuck on the login page after successful Google sign-in.

**Root cause:** `ProtectedRoute` checks `isAuthorized` (allowlist check) and silently redirects back to `/login` without explaining why.

**Fix location:** `frontend/src/App.tsx` — `ProtectedRoute` component

```typescript
if (user && !isAuthorized) {
  return (
    <div className="min-h-screen bg-tre-navy flex items-center justify-center">
      <div className="text-white text-center">
        <p className="text-xl">Access Pending</p>
        <p className="text-gray-400 mt-2">
          Your account ({user.email}) is awaiting approval.
        </p>
      </div>
    </div>
  );
}
```

---

## Acting on Signals

**Workflow: investigating a reported friction point**

1. Check `GET /api/history/jobs` for the tool — look at failure rate
2. Check Cloud Run logs for the time window when failures occurred
3. Grep the relevant `backend/app/api/{tool}.py` for `HTTPException` strings — do they match?
4. Check the frontend page for the 4 state variables — is the error reaching the UI?
5. Fix the weakest link: either the backend detail message or the frontend error rendering
6. Validate: reproduce the failure condition locally and confirm the improved message appears

For structuring fixes as phases, see the **roadmap-experiments** skill.
For adding event tracking to detect these patterns proactively, see the **instrumenting-product-metrics** skill.
