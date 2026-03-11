# Engagement & Adoption Reference

## Contents
- Usage Tracking Instrumentation
- Tool Usage Stats
- Re-engagement Patterns
- Feature Discovery Nudges
- Retention Metrics

---

## Usage Tracking Instrumentation

**Backend event tracking** via Firestore for analytics and adoption insights.

### Core Event Schema

```python
# models/analytics.py - Define usage event structure
from pydantic import BaseModel, Field
from datetime import datetime

class UsageEvent(BaseModel):
    """Usage event for analytics tracking."""
    user_email: str = Field(..., description="User who performed action")
    tool: str = Field(..., description="Tool name: extract, title, proration, revenue")
    action: str = Field(..., description="Action type: upload, export, view, calculate")
    metadata: dict = Field(default_factory=dict, description="Additional context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str | None = Field(None, description="Optional session grouping")
```

### Event Capture in API Routes

```python
# api/extract.py - Track upload event
from app.services import firestore_service as db

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_email)
):
    # ... process file ...
    
    # Track usage event
    await db.track_tool_usage(
        user_email=current_user,
        tool="extract",
        action="upload",
        metadata={
            "filename": file.filename,
            "file_size_kb": file.size // 1024,
            "parties_found": len(result.entries),
        }
    )
    
    return result
```

### Frontend Session Tracking

```tsx
// utils/analytics.ts - Client-side session helper
import { v4 as uuidv4 } from 'uuid';

let sessionId: string | null = null;

export function getSessionId(): string {
  if (!sessionId) {
    sessionId = sessionStorage.getItem('session_id');
    if (!sessionId) {
      sessionId = uuidv4();
      sessionStorage.setItem('session_id', sessionId);
    }
  }
  return sessionId;
}

export async function trackEvent(
  tool: string,
  action: string,
  metadata?: Record<string, unknown>
) {
  // Send to backend
  await fetch('/api/analytics/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool,
      action,
      metadata,
      session_id: getSessionId(),
    }),
  });
}
```

---

## Tool Usage Stats

**Dashboard.tsx already fetches real usage counts** from `/api/history/jobs` and aggregates by tool:

```tsx
// Dashboard.tsx - How toolCounts is computed today
useEffect(() => {
  const fetchJobs = async () => {
    const response = await fetch(`${API_BASE}/history/jobs?limit=50`);
    if (!response.ok) return;
    const data = await response.json();
    const jobs: RecentJob[] = data.jobs || [];

    // Count jobs per tool
    const counts: Record<string, number> = {};
    for (const job of jobs) {
      counts[job.tool] = (counts[job.tool] || 0) + 1;
    }
    setToolCounts(counts);
  };
  fetchJobs();
}, []);

// Displayed on each tool card:
<p className="text-2xl font-oswald font-semibold text-tre-navy">
  {toolCounts[tool.tool] || 0}
</p>
<p className="text-xs text-gray-400">times used</p>
```

**Limitation:** This only counts the last 50 jobs and includes all time, not a rolling window. If you need per-period or per-user breakdowns, add a dedicated analytics endpoint:

```python
# api/admin.py - Add analytics endpoint alongside existing admin routes
@router.get("/analytics/tool-usage")
async def get_tool_usage_stats(days: int = Query(30, ge=1, le=90)):
    """Get tool usage breakdown for the last N days."""
    from datetime import datetime, timedelta
    from app.services import firestore_service as db

    cutoff = datetime.utcnow() - timedelta(days=days)
    events = await db.get_usage_events_since(cutoff)

    counts: dict[str, int] = {}
    for event in events:
        tool = event["tool"]
        counts[tool] = counts.get(tool, 0) + 1

    return {
        "period_days": days,
        "total_events": len(events),
        "by_tool": counts,
        "unique_users": len({e["user_email"] for e in events}),
    }
```

---

## Re-engagement Patterns

**For internal tools:** Email campaigns don't work (users ignore internal emails). Use **in-app nudges** when they return.

### Pattern: "You Haven't Used X in a While"

```tsx
// Dashboard.tsx - Nudge for inactive tools
const [inactiveTools, setInactiveTools] = useState<string[]>([]);

useEffect(() => {
  const checkInactivity = async () => {
    const response = await fetch('/api/analytics/user-activity');
    const data = await response.json();
    
    // Tools not used in 14+ days
    const inactive = data.tools_by_last_use
      .filter(t => t.days_since_last_use > 14)
      .map(t => t.tool_name);
    
    setInactiveTools(inactive);
  };
  
  checkInactivity();
}, []);

// Show tip on dashboard
{inactiveTools.includes('proration') && (
  <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4">
    <div className="flex items-start gap-3">
      <Calculator className="w-5 h-5 text-purple-600" />
      <div>
        <p className="font-medium text-purple-900 text-sm">
          Try the Proration tool again
        </p>
        <p className="text-sm text-purple-700 mt-1">
          We added auto-download for RRC data—no more manual CSVs.
        </p>
        <Link
          to="/proration"
          className="text-sm text-purple-800 underline mt-2 inline-block"
        >
          Open Proration →
        </Link>
      </div>
    </div>
  </div>
)}
```

---

## Feature Discovery Nudges

**Problem:** Users stick to one tool and never discover others.

**Solution:** Show "Try X next" suggestions after successful workflow.

```tsx
// Extract.tsx - Cross-promote Title tool
const [showTitleSuggestion, setShowTitleSuggestion] = useState(false);

const handleExportComplete = () => {
  // After user exports Extract results, suggest Title
  const hasUsedTitle = localStorage.getItem('title_tool_used');
  if (!hasUsedTitle) {
    setShowTitleSuggestion(true);
  }
};

// Dismissible banner after export
{showTitleSuggestion && (
  <div className="fixed bottom-4 right-4 max-w-sm bg-white shadow-xl rounded-lg border border-gray-200 p-4">
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-5 h-5 text-green-500" />
          <h4 className="font-semibold text-tre-navy">Try Title Next</h4>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          Consolidate owner info from title opinions with entity detection.
        </p>
        <Link
          to="/title"
          className="text-sm text-tre-teal hover:underline"
        >
          Open Title Tool →
        </Link>
      </div>
      <button
        onClick={() => {
          setShowTitleSuggestion(false);
          localStorage.setItem('title_suggestion_dismissed', 'true');
        }}
        className="text-gray-400 hover:text-gray-600"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
)}
```

---

## Retention Metrics

**Key metrics for internal tools:**

| Metric | Definition | Target |
|--------|------------|--------|
| DAU/MAU | Daily active / Monthly active users | >40% (internal tools) |
| Tool adoption | % of users who've used each tool | 100% (all tools) |
| Time to first success | Days from account creation to first export | <1 day |
| Stickiness | % of users returning weekly | >60% |

**Backend query for retention:**

```python
# api/analytics.py
@router.get("/retention")
async def get_retention_stats():
    """Calculate DAU/MAU and tool adoption."""
    from datetime import datetime, timedelta
    from app.services import firestore_service as db
    
    # Get events from last 30 days
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    cutoff_1d = datetime.utcnow() - timedelta(days=1)
    
    events_30d = await db.get_usage_events_since(cutoff_30d)
    events_1d = await db.get_usage_events_since(cutoff_1d)
    
    # Unique users
    mau = len(set(e["user_email"] for e in events_30d))
    dau = len(set(e["user_email"] for e in events_1d))
    
    # Tool adoption per user
    user_tools = {}
    for event in events_30d:
        email = event["user_email"]
        tool = event["tool"]
        user_tools.setdefault(email, set()).add(tool)
    
    return {
        "dau": dau,
        "mau": mau,
        "dau_mau_ratio": round(dau / mau, 2) if mau > 0 else 0,
        "users_using_all_tools": sum(1 for tools in user_tools.values() if len(tools) == 5),
        "total_users": mau,
    }