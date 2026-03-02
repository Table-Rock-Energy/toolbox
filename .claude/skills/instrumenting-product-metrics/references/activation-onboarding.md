# Activation & Onboarding Reference

## Contents
- Activation Metrics Definition
- First-Run Experience Tracking
- Empty State Instrumentation
- Tool-Specific Onboarding Events

---

## Activation Metrics for Table Rock Tools

**CRITICAL:** This application has NO onboarding flow. Users authenticate via Firebase and land directly on the Dashboard with four tool cards. There is no tutorial, no checklist, no progressive disclosure.

### Primary Activation Event

```typescript
// Track when user completes FIRST successful workflow
{
  event_name: 'user_activated',
  properties: {
    tool: 'extract' | 'title' | 'proration' | 'revenue',
    time_to_activation_seconds: 180,
    files_processed: 1,
    rows_extracted: 45,
  }
}
```

**Activation Definition:** User who has uploaded a file, processed it successfully, and downloaded an export within 7 days of signup.

---

## First-Run Experience Events

### Tool Selection (Dashboard)

```typescript
// Track which tool user tries FIRST
const { track } = useAnalytics()

<Link to="/extract" onClick={() => {
  track('first_tool_selected', { 
    tool: 'extract',
    seconds_since_signup: 120 
  })
}}>
```

**WHY:** Understanding first tool choice reveals primary use case and helps prioritize documentation.

### First Upload

```typescript
// Track FIRST file upload across ANY tool
const handleFilesSelected = async (files: File[]) => {
  const isFirstUpload = !localStorage.getItem('has_uploaded')
  
  if (isFirstUpload) {
    track('first_file_uploaded', {
      tool: currentTool,
      file_type: files[0].type,
      file_size_mb: files[0].size / 1024 / 1024,
    })
    localStorage.setItem('has_uploaded', 'true')
  }
}
```

**WARNING:** Using `localStorage` for first-upload detection is fragile (clears on logout, doesn't sync across devices). Better: query Firestore `jobs` collection for `user_id` with count.

### DO/DON'T: Empty State Tracking

**BAD - No visibility into drop-off:**
```typescript
<div className="text-center text-gray-500">
  <p>No files uploaded yet. Upload a PDF to get started.</p>
</div>
```

**GOOD - Track empty state views:**
```typescript
useEffect(() => {
  if (entries.length === 0 && !isProcessing) {
    track('empty_state_viewed', { 
      tool: 'extract',
      session_duration_seconds: Date.now() - sessionStart 
    })
  }
}, [entries, isProcessing])
```

**WHY:** High empty-state view counts indicate users don't understand what to upload or how to start.

---

## Tool-Specific Onboarding

### Extract Tool Activation

```typescript
// Complete activation flow for OCC Exhibit A extraction
const EXTRACT_ACTIVATION_EVENTS = [
  'extract_page_viewed',          // User opens /extract
  'extract_pdf_uploaded',         // PDF upload starts
  'extract_processing_complete',  // Backend returns entries
  'extract_entries_reviewed',     // User scrolls through results
  'extract_csv_downloaded',       // First export
]
```

Track time between each step to identify friction:

```python
# backend/app/api/extract.py
async def upload_extract_pdf(file: UploadFile):
    # After successful processing
    await track_event(
        "extract_processing_complete",
        user_id=current_user.id,
        properties={
            "total_entries": len(result.entries),
            "flagged_count": result.flagged_count,
            "processing_time_seconds": elapsed,
        }
    )
```

### Proration Tool Activation (Requires RRC Data)

**BLOCKER:** Proration tool requires RRC data download before first use. Track this dependency:

```python
# Track RRC data readiness
await track_event(
    "proration_blocked_no_rrc_data",
    user_id=user.id,
    properties={
        "attempted_upload": True,
        "last_rrc_sync": rrc_status.get("last_updated"),
    }
)
```

**FIX:** Add "Download RRC Data" CTA to empty state with tracking:

```typescript
<button onClick={async () => {
  track('rrc_download_initiated', { source: 'empty_state' })
  await fetch('/api/proration/rrc/download', { method: 'POST' })
}}>
  Download RRC Data (Required)
</button>
```

---

## Activation Cohort Analysis

Query Firestore to calculate activation rate:

```python
# backend/app/api/analytics.py
async def get_activation_cohort(signup_date: date):
    """Get users who signed up on date and activated within 7 days."""
    db = get_firestore_client()
    
    # Get signups
    signups = db.collection(USERS_COLLECTION).where(
        "created_at", ">=", signup_date
    ).where(
        "created_at", "<", signup_date + timedelta(days=1)
    ).stream()
    
    activated_users = []
    for user in signups:
        # Check for activation event within 7 days
        activation = db.collection(EVENTS_COLLECTION).where(
            "user_id", "==", user.id
        ).where(
            "event_name", "==", "user_activated"
        ).where(
            "timestamp", "<", user.to_dict()["created_at"] + timedelta(days=7)
        ).limit(1).get()
        
        if activation:
            activated_users.append(user.id)
    
    return {
        "cohort_date": signup_date,
        "signups": len(list(signups)),
        "activated": len(activated_users),
        "activation_rate": len(activated_users) / len(list(signups)),
    }
```

**WARNING:** This is an N+1 query. For production, denormalize activation status onto `users` collection.