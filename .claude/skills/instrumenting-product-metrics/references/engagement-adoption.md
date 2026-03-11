# Engagement & Adoption Reference

## Contents
- Daily/Weekly Active Users
- Tool Usage Frequency
- Feature Discovery Tracking
- Power User Identification

---

## Engagement Metrics

### Daily Active Users (DAU)

```python
# backend/app/api/analytics.py
from datetime import datetime, date, timedelta, timezone
from app.services.firestore_service import get_firestore_client, EVENTS_COLLECTION

async def get_dau(target_date: date | None = None) -> int:
    """Count unique users who tracked any event on target_date."""
    d = target_date or datetime.now(tz=timezone.utc).date()
    db = get_firestore_client()

    start = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    events = db.collection(EVENTS_COLLECTION).where(
        "timestamp", ">=", start
    ).where("timestamp", "<", end).stream()

    unique_users: set[str] = set()
    async for doc in events:
        unique_users.add(doc.to_dict()["user_id"])
    return len(unique_users)
```

**WARNING:** Firestore has no `COUNT(DISTINCT user_id)`. You must stream all events and deduplicate in memory. For >10k events/day, export to BigQuery.

---

## Tool Usage Frequency

### Track Tool Sessions

```typescript
// Track when user STARTS using a tool (not just page view)
// frontend/src/pages/Extract.tsx
const Extract = () => {
  const { track } = useAnalytics()
  const sessionIdRef = useRef(crypto.randomUUID())
  const sessionStartRef = useRef(Date.now())

  useEffect(() => {
    track('tool_session_started', {
      tool: 'extract',
      session_id: sessionIdRef.current,
    })

    return () => {
      track('tool_session_ended', {
        tool: 'extract',
        session_id: sessionIdRef.current,
        duration_seconds: Math.floor((Date.now() - sessionStartRef.current) / 1000),
      })
    }
  }, [])  // Run once on mount/unmount only
}
```

**WHY:** Page views don't indicate actual usage. `tool_session_ended` duration tells you whether users stay engaged or immediately leave.

### DO/DON'T: Measuring Feature Adoption

**BAD - Only track success cases:**
```typescript
// Tracks downloads but misses users who clicked but got an error
track('csv_export_downloaded', { tool: 'extract' })
```

**GOOD - Track attempts vs completions to find failure rate:**
```typescript
// Track export button click (attempt)
<button onClick={() => {
  track('export_attempted', { tool: 'extract', format: 'csv' })
  handleExport()
}}>Export CSV</button>

// Track actual download (completion)
const handleExport = async () => {
  try {
    const blob = await fetch('/api/extract/export/csv', { method: 'POST', body: ... }).then(r => r.blob())
    track('export_completed', { tool: 'extract', format: 'csv', rows: entries.length })
    // create download link...
  } catch {
    track('export_failed', { tool: 'extract', format: 'csv' })
  }
}
```

**WHY:** `attempt` vs `completed` ratio reveals silent failures. If 80% of export attempts don't complete, there's a bug or UX issue.

---

## Feature Discovery Events

### Track When Users Find Hidden Features

```typescript
// Track filter usage in Extract/Title tools (filters have no discovery mechanism)
const handleFilterChange = (filterName: string, enabled: boolean) => {
  if (enabled) {
    track('filter_enabled', {
      tool: 'extract',
      filter_name: filterName,
    })
  }
  setActiveFilter(enabled ? filterName : null)
}
```

**WARNING:** Filters in Extract, Title, and Proration tools have NO discovery mechanism beyond the UI. Users must visually notice them. If `filter_enabled` counts are near zero, consider adding tooltip prompts.

### Track Multiple Export Format Usage

```typescript
// Track which export formats are actually used vs. available
track('export_completed', {
  tool: 'title',
  format: 'mineral',   // 'csv' | 'excel' | 'mineral' — is mineral format discovered?
  rows: entries.length,
})
```

**Action:** If `format: 'mineral'` is never tracked but the endpoint exists, users don't know about it. Add UI callout.

---

## Power User Identification

```python
async def get_power_users(days: int = 30, min_jobs: int = 10) -> list[dict]:
    """Find users with high job volume in recent period."""
    db = get_firestore_client()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    jobs_stream = db.collection("jobs").where(
        "created_at", ">=", cutoff
    ).stream()

    user_job_counts: dict[str, int] = {}
    async for doc in jobs_stream:
        uid = doc.to_dict().get("user_id")
        if uid:
            user_job_counts[uid] = user_job_counts.get(uid, 0) + 1

    power_users = [
        {"user_id": uid, "job_count": count}
        for uid, count in user_job_counts.items()
        if count >= min_jobs
    ]
    return sorted(power_users, key=lambda x: x["job_count"], reverse=True)
```

**Use Case:** Power users are candidates for feedback interviews. Their workflows reveal use cases you haven't anticipated — query the `jobs` collection (Firestore already tracks these via `history.py`) to find them without adding new tracking.

See the **firestore** skill for streaming patterns and the **fastapi** skill for building the analytics API endpoint.
