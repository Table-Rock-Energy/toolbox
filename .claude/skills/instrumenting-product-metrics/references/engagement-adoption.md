# Engagement & Adoption Reference

## Contents
- Daily/Weekly Active Users
- Feature Discovery Tracking
- Tool Usage Frequency
- Power User Identification

---

## Engagement Metrics

### Daily Active Users (DAU)

```python
# backend/app/api/analytics.py
from datetime import datetime, timedelta
from app.services.firestore_service import get_firestore_client, EVENTS_COLLECTION

async def get_dau(date: date = None) -> int:
    """Count users who tracked ANY event on given date."""
    target_date = date or datetime.utcnow().date()
    db = get_firestore_client()
    
    # Query events for the date
    events = db.collection(EVENTS_COLLECTION).where(
        "timestamp", ">=", datetime.combine(target_date, datetime.min.time())
    ).where(
        "timestamp", "<", datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    ).stream()
    
    # Deduplicate by user_id
    unique_users = set()
    async for event in events:
        unique_users.add(event.to_dict()["user_id"])
    
    return len(unique_users)
```

**WARNING:** Firestore queries don't support `COUNT(DISTINCT user_id)`. Must fetch all events and deduplicate in memory. For large datasets (>10k events/day), use BigQuery export.

### Weekly Active Users (WAU)

```python
async def get_wau(week_start: date = None) -> int:
    """Count users active in 7-day window."""
    start = week_start or (datetime.utcnow().date() - timedelta(days=7))
    end = start + timedelta(days=7)
    
    db = get_firestore_client()
    events = db.collection(EVENTS_COLLECTION).where(
        "timestamp", ">=", datetime.combine(start, datetime.min.time())
    ).where(
        "timestamp", "<", datetime.combine(end, datetime.min.time())
    ).stream()
    
    unique_users = set()
    async for event in events:
        unique_users.add(event.to_dict()["user_id"])
    
    return len(unique_users)
```

---

## Tool Usage Frequency

### Track Tool Sessions

```typescript
// Track when user STARTS using a tool (not just page view)
const Extract = () => {
  const { track } = useAnalytics()
  
  useEffect(() => {
    const sessionId = uuidv4()
    const sessionStart = Date.now()
    
    track('tool_session_started', {
      tool: 'extract',
      session_id: sessionId,
    })
    
    return () => {
      track('tool_session_ended', {
        tool: 'extract',
        session_id: sessionId,
        duration_seconds: (Date.now() - sessionStart) / 1000,
      })
    }
  }, [])
}
```

**WHY:** Page views don't indicate actual usage. Track session start/end to measure engaged time.

### DO/DON'T: Measuring Feature Adoption

**BAD - Only track success cases:**
```typescript
track('csv_export_downloaded', { tool: 'extract' })
```

**GOOD - Track attempts vs successes:**
```typescript
// Track export button click (attempt)
<button onClick={() => {
  track('export_attempted', { tool: 'extract', format: 'csv' })
  exportToCSV()
}}>

// Track actual download (success)
const exportToCSV = async () => {
  const blob = await fetch('/api/extract/export/csv').then(r => r.blob())
  track('export_completed', { tool: 'extract', format: 'csv', rows: entries.length })
  // ... download blob
}
```

**WHY:** Tracking both attempts and completions reveals failure rates and UX friction.

---

## Power User Identification

### Query Heavy Users

```python
async def get_power_users(days: int = 30, min_jobs: int = 10) -> list[dict]:
    """Find users with high job volume."""
    db = get_firestore_client()
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    jobs = db.collection(JOBS_COLLECTION).where(
        "created_at", ">=", cutoff
    ).stream()
    
    # Count jobs per user
    user_job_counts = {}
    async for job in jobs:
        job_data = job.to_dict()
        user_id = job_data.get("user_id")
        if user_id:
            user_job_counts[user_id] = user_job_counts.get(user_id, 0) + 1
    
    # Filter to power users
    power_users = [
        {"user_id": uid, "job_count": count}
        for uid, count in user_job_counts.items()
        if count >= min_jobs
    ]
    
    return sorted(power_users, key=lambda x: x["job_count"], reverse=True)
```

**Use Case:** Identify users for beta testing, feedback interviews, or case studies.

---

## Feature Discovery Events

Track when users discover hidden features:

```typescript
// Track filter usage in Extract tool
const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)

const handleFilterChange = (filterName: string, enabled: boolean) => {
  if (enabled) {
    track('filter_enabled', {
      tool: 'extract',
      filter_name: filterName,
      is_first_use: !localStorage.getItem(`filter_${filterName}_used`),
    })
    localStorage.setItem(`filter_${filterName}_used`, 'true')
  }
  
  setShowIndividualsOnly(enabled)
}
```

**WARNING:** Filters in Extract/Title/Proration tools have NO discovery mechanism. Users must notice the UI elements. Add tooltips with tracking:

```typescript
<Tooltip content="Show only individual entities" onShow={() => {
  track('filter_tooltip_viewed', { filter: 'individuals_only' })
}}>
  <Checkbox onChange={handleFilterChange} />
</Tooltip>