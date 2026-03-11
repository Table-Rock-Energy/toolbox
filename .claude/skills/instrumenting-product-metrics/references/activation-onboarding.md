# Activation & Onboarding Reference

## Contents
- Activation Metrics Definition
- First-Run Experience Tracking
- Empty State Instrumentation
- Tool-Specific Onboarding Events
- Activation Cohort Analysis

---

## Activation Metrics for Table Rock Tools

**CRITICAL:** This app has NO onboarding flow. Users authenticate via Firebase and land directly on the Dashboard with five tool cards. No tutorial, no checklist, no progressive disclosure.

### Primary Activation Event

```typescript
// Track when user completes FIRST successful workflow
{
  event_name: 'user_activated',
  properties: {
    tool: 'extract' | 'title' | 'proration' | 'revenue' | 'ghl_prep',
    time_to_activation_seconds: 180,
    entries_exported: 45,
  }
}
```

**Activation Definition:** User who uploads a file, processes it, and downloads an export within 7 days of signup.

---

## First-Run Experience Events

### Tool Selection (Dashboard)

```typescript
// Track which tool user opens FIRST
const { track } = useAnalytics()

<Link to="/extract" onClick={() => {
  track('first_tool_selected', {
    tool: 'extract',
    seconds_since_signup: Math.floor((Date.now() - signupTime) / 1000),
  })
}}>
```

**WHY:** Understanding first tool choice reveals primary use case. If most users go to Proration first but get blocked by missing RRC data, that's a top-of-funnel problem.

### First Upload

```typescript
// Track FIRST file upload across ANY tool — use Firestore jobs count, not localStorage
const handleFilesSelected = async (files: File[]) => {
  // Query jobs collection to detect first upload (persistent across devices)
  const jobCount = await fetch('/api/history/jobs?limit=1').then(r => r.json())
  const isFirstUpload = jobCount.total === 0

  if (isFirstUpload) {
    track('first_file_uploaded', {
      tool: currentTool,
      file_type: files[0].type,
      file_size_mb: files[0].size / 1024 / 1024,
    })
  }
}
```

**WARNING:** NEVER use `localStorage` to detect first uploads. It clears on logout and doesn't sync across devices. Query `/api/history/jobs` or Firestore `jobs` collection for `user_id` instead.

---

## Empty State Instrumentation

### DO/DON'T: Track Empty State Views

**BAD - No visibility into drop-off:**
```typescript
<div className="text-center text-gray-500">
  <p>No files uploaded yet. Upload a PDF to get started.</p>
</div>
```

**GOOD - Track empty state views to measure confusion:**
```typescript
const sessionStart = useRef(Date.now())

useEffect(() => {
  if (entries.length === 0 && !isProcessing) {
    track('empty_state_viewed', {
      tool: 'extract',
      session_duration_seconds: Math.floor((Date.now() - sessionStart.current) / 1000),
    })
  }
}, [entries.length, isProcessing])
```

**WHY:** High empty-state view counts without subsequent uploads indicates users don't understand what to upload. Threshold: >3 views per user on same tool = add contextual guidance.

---

## Tool-Specific Onboarding

### Extract Tool Events

```typescript
const EXTRACT_ACTIVATION_FUNNEL = [
  'extract_page_viewed',           // User opens /extract
  'extract_pdf_uploaded',          // PDF upload submitted
  'extract_processing_complete',   // API returns entries
  'extract_csv_downloaded',        // First export (activation)
] as const
```

```python
# backend/app/api/extract.py — track on successful processing
async def upload_extract_pdf(file: UploadFile, user=Depends(get_current_user)):
    result = await pdf_extraction_service.process(file)
    await track_event(
        "extract_processing_complete",
        user_id=user.uid,
        properties={
            "total_entries": len(result.entries),
            "flagged_count": result.flagged_count,
            "processing_time_seconds": elapsed,
        }
    )
    return result
```

### Proration Tool (Blocked by RRC Data)

**BLOCKER:** Proration requires RRC data before first use. Track this gate:

```python
# backend/app/api/proration.py
async def upload_proration(file: UploadFile, user=Depends(get_current_user)):
    rrc_status = await rrc_data_service.get_status()
    if rrc_status["oil_count"] == 0 and rrc_status["gas_count"] == 0:
        await track_event(
            "proration_blocked_no_rrc_data",
            user_id=user.uid,
            properties={"attempted_upload": True},
        )
        raise HTTPException(
            status_code=400,
            detail="RRC data not downloaded. Go to RRC Status panel to download it."
        )
```

**FIX:** Add tracked "Download RRC Data" CTA to the Proration empty state:

```typescript
<button onClick={async () => {
  track('rrc_download_initiated', { source: 'proration_empty_state' })
  await fetch('/api/proration/rrc/download', { method: 'POST' })
}}>
  Download RRC Data (Required for Proration)
</button>
```

---

## Activation Cohort Analysis

```python
# backend/app/api/analytics.py
from datetime import date, datetime, timedelta, timezone

async def get_activation_rate(signup_date: date) -> dict:
    """Rate of users who signed up on date and activated within 7 days."""
    db = get_firestore_client()

    start = datetime.combine(signup_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Collect signups — materialize to list first to avoid exhausted generator
    signup_stream = db.collection(USERS_COLLECTION).where(
        "created_at", ">=", start
    ).where("created_at", "<", end).stream()

    signup_ids: list[str] = []
    async for user_doc in signup_stream:
        signup_ids.append(user_doc.id)

    if not signup_ids:
        return {"cohort_date": str(signup_date), "signups": 0, "activated": 0, "activation_rate": 0}

    # Check for activation events within 7 days of signup
    activated: set[str] = set()
    for i in range(0, len(signup_ids), 10):  # Firestore `in` limit = 10
        chunk = signup_ids[i:i + 10]
        activation_events = db.collection(EVENTS_COLLECTION).where(
            "event_name", "==", "user_activated"
        ).where("user_id", "in", chunk).where(
            "timestamp", "<", start + timedelta(days=7)
        ).stream()
        async for doc in activation_events:
            activated.add(doc.to_dict()["user_id"])

    return {
        "cohort_date": str(signup_date),
        "signups": len(signup_ids),
        "activated": len(activated),
        "activation_rate": len(activated) / len(signup_ids),
    }
```

**WARNING:** The previous version called `len(list(signups))` twice — the second call returns 0 because the async generator is exhausted. Always materialize to a list first.

See the **firestore** skill for client initialization and the **fastapi** skill for dependency injection patterns.
