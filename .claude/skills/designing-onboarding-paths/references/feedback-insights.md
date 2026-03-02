# Feedback & Insights Reference

## Contents
- User Feedback Collection
- Support Request Patterns
- Feature Request Tracking
- Usage Analytics Insights
- Anti-Patterns

---

## User Feedback Collection

Table Rock Tools currently has **no feedback mechanism** beyond the static "Contact Support" link in Help page.

### In-App Feedback Widget

```tsx
// toolbox/frontend/src/components/FeedbackWidget.tsx
import { useState } from 'react'
import { MessageSquare, X, Send } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function FeedbackWidget() {
  const { user } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [category, setCategory] = useState<'bug' | 'feature' | 'question'>('bug')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL}/feedback/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_email: user?.email,
          category,
          message,
          page: window.location.pathname,
          timestamp: new Date().toISOString(),
        }),
      })
      
      setSubmitted(true)
      setTimeout(() => {
        setIsOpen(false)
        setSubmitted(false)
        setMessage('')
      }, 2000)
    } catch (err) {
      console.error('Failed to submit feedback:', err)
    }
  }

  return (
    <>
      {/* Floating feedback button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 p-4 bg-tre-teal text-white rounded-full shadow-lg hover:bg-tre-teal/90 transition-all z-50"
      >
        <MessageSquare className="w-6 h-6" />
      </button>

      {/* Feedback modal */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 bg-white rounded-xl shadow-2xl border border-gray-200 z-50">
          <div className="flex items-center justify-between p-4 border-b border-gray-100">
            <h3 className="font-oswald font-semibold text-lg">Send Feedback</h3>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          {submitted ? (
            <div className="p-6 text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Send className="w-6 h-6 text-green-600" />
              </div>
              <p className="font-medium text-green-900">Feedback Submitted</p>
              <p className="text-sm text-gray-600 mt-1">Thank you for your input!</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Category
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['bug', 'feature', 'question'] as const).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setCategory(cat)}
                      className={`px-3 py-2 rounded-lg text-sm capitalize transition-colors ${
                        category === cat
                          ? 'bg-tre-teal text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Message
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Describe your issue, suggestion, or question..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 resize-none"
                  rows={4}
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 font-medium"
              >
                Submit Feedback
              </button>
            </form>
          )}
        </div>
      )}
    </>
  )
}
```

**Backend endpoint:**

```python
# toolbox/backend/app/api/feedback.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class FeedbackSubmission(BaseModel):
    user_email: str
    category: str  # bug, feature, question
    message: str
    page: str
    timestamp: str

@router.post("/submit")
async def submit_feedback(feedback: FeedbackSubmission):
    """Store user feedback in Firestore."""
    try:
        from app.services import firestore_service as db
        
        await db.store_feedback({
            "user_email": feedback.user_email,
            "category": feedback.category,
            "message": feedback.message,
            "page": feedback.page,
            "timestamp": datetime.fromisoformat(feedback.timestamp),
            "status": "new",
        })
        
        # Optional: Send email notification to admin
        # await send_email(...)
        
        return {"status": "submitted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_feedback(status: str = None, limit: int = 50):
    """Get feedback submissions (admin only)."""
    from app.services import firestore_service as db
    
    query = {}
    if status:
        query["status"] = status
    
    feedback = await db.get_feedback(query=query, limit=limit)
    
    return {"feedback": feedback, "count": len(feedback)}
```

---

## Support Request Patterns

### Contextual Support Links

```tsx
// Extract.tsx - Context-specific help link
{error && (
  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
    <p className="text-red-900">{error}</p>
    <a
      href={`mailto:support@tablerockenergy.com?subject=Extract Tool Error&body=Error: ${encodeURIComponent(error)}%0A%0APage: ${window.location.href}`}
      className="mt-2 inline-flex items-center gap-1 text-sm text-red-700 hover:underline"
    >
      <Mail className="w-4 h-4" />
      Report this issue
    </a>
  </div>
)}
```

### Automatic Error Reporting

```typescript
// toolbox/frontend/src/utils/errorReporting.ts
export async function reportError(error: Error, context?: Record<string, unknown>) {
  try {
    await fetch(`${import.meta.env.VITE_API_BASE_URL}/errors/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: error.message,
        stack: error.stack,
        context: {
          ...context,
          page: window.location.pathname,
          userAgent: navigator.userAgent,
          timestamp: new Date().toISOString(),
        },
      }),
    })
  } catch (err) {
    console.error('Failed to report error:', err)
  }
}

// Usage in Extract.tsx
try {
  await fetch(`${API_BASE}/extract/upload`, { ... })
} catch (err) {
  reportError(err as Error, {
    action: 'file_upload',
    fileName: file.name,
    fileSize: file.size,
  })
  setError(err.message)
}
```

---

## Feature Request Tracking

### Voting Board

```tsx
// toolbox/frontend/src/pages/FeatureRequests.tsx
interface FeatureRequest {
  id: string
  title: string
  description: string
  votes: number
  status: 'planned' | 'in-progress' | 'completed' | 'declined'
  submitted_by: string
  created_at: string
}

export default function FeatureRequests() {
  const { user } = useAuth()
  const [requests, setRequests] = useState<FeatureRequest[]>([])
  const [userVotes, setUserVotes] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchRequests()
  }, [])

  const fetchRequests = async () => {
    const response = await fetch(`${API_BASE}/features/requests`)
    const data = await response.json()
    setRequests(data.requests)
    setUserVotes(new Set(data.user_votes))
  }

  const handleVote = async (requestId: string) => {
    await fetch(`${API_BASE}/features/requests/${requestId}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_email: user?.email }),
    })
    fetchRequests()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-oswald font-semibold text-tre-navy">
        Feature Requests
      </h1>

      <div className="space-y-3">
        {requests.map((request) => (
          <div key={request.id} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-start gap-4">
              <button
                onClick={() => handleVote(request.id)}
                disabled={userVotes.has(request.id)}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                  userVotes.has(request.id)
                    ? 'bg-tre-teal/20 text-tre-teal'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                <ChevronUp className="w-5 h-5" />
                <span className="text-sm font-semibold">{request.votes}</span>
              </button>

              <div className="flex-1">
                <h3 className="font-semibold text-lg text-gray-900">{request.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{request.description}</p>
                <div className="flex items-center gap-3 mt-3">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    request.status === 'planned' ? 'bg-blue-100 text-blue-700' :
                    request.status === 'in-progress' ? 'bg-amber-100 text-amber-700' :
                    request.status === 'completed' ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {request.status}
                  </span>
                  <span className="text-xs text-gray-500">
                    Requested by {request.submitted_by}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

---

## Usage Analytics Insights

### Admin Dashboard

```tsx
// toolbox/frontend/src/pages/AdminDashboard.tsx (admin-only page)
export default function AdminDashboard() {
  const [metrics, setMetrics] = useState({
    total_users: 0,
    active_users_7d: 0,
    total_jobs_30d: 0,
    jobs_by_tool: {},
    avg_processing_time: {},
  })

  useEffect(() => {
    fetchMetrics()
  }, [])

  const fetchMetrics = async () => {
    const response = await fetch(`${API_BASE}/admin/metrics`)
    const data = await response.json()
    setMetrics(data)
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-oswald font-semibold text-tre-navy">
        Admin Dashboard
      </h1>

      {/* Key metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Total Users</p>
          <p className="text-3xl font-oswald font-semibold text-tre-navy">
            {metrics.total_users}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Active Users (7d)</p>
          <p className="text-3xl font-oswald font-semibold text-tre-navy">
            {metrics.active_users_7d}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Jobs (30d)</p>
          <p className="text-3xl font-oswald font-semibold text-tre-navy">
            {metrics.total_jobs_30d}
          </p>
        </div>
      </div>

      {/* Tool usage breakdown */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-oswald font-semibold text-lg mb-4">
          Tool Usage (30 days)
        </h2>
        <div className="space-y-3">
          {Object.entries(metrics.jobs_by_tool).map(([tool, count]) => (
            <div key={tool} className="flex items-center justify-between">
              <span className="text-gray-700 capitalize">{tool}</span>
              <span className="font-semibold text-tre-navy">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

**Backend metrics endpoint:**

```python
# toolbox/backend/app/api/admin.py
@router.get("/metrics")
async def get_admin_metrics():
    """Get usage metrics for admin dashboard."""
    from datetime import datetime, timedelta
    from app.services import firestore_service as db
    
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Get all users
    users = await db.get_all_users()
    
    # Get jobs from last 30 days
    jobs_30d = await db.get_jobs(query={"created_at": {"$gte": month_ago}})
    
    # Get active users (at least 1 job in last 7 days)
    active_user_emails = set()
    for job in jobs_30d:
        if job["created_at"] >= week_ago:
            active_user_emails.add(job["user_email"])
    
    # Jobs by tool
    jobs_by_tool = {}
    for job in jobs_30d:
        tool = job["tool"]
        jobs_by_tool[tool] = jobs_by_tool.get(tool, 0) + 1
    
    return {
        "total_users": len(users),
        "active_users_7d": len(active_user_emails),
        "total_jobs_30d": len(jobs_30d),
        "jobs_by_tool": jobs_by_tool,
    }
```

---

## Anti-Patterns

### WARNING: NPS Surveys in Internal Tools

**The Problem:**

```tsx
// BAD - NPS survey modal
<Modal>
  <h3>How likely are you to recommend Table Rock Tools to a colleague?</h3>
  <div className="flex gap-2">
    {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(score => (
      <button onClick={() => submitNPS(score)}>{score}</button>
    ))}
  </div>
</Modal>
```

**Why This Breaks:**
1. **Nonsensical** - Internal tool, users have no choice but to use it
2. **Annoying** - Interrupts workflow with irrelevant question
3. **Misleading metric** - NPS designed for customer products, not internal tools

**The Fix:**

Use **task-specific satisfaction** instead:

```tsx
// GOOD - Task completion satisfaction
{activeJob?.result?.success && (
  <div className="bg-white rounded-xl border border-gray-200 p-4 mt-6">
    <p className="text-sm font-medium text-gray-700 mb-3">
      Did this extraction meet your needs?
    </p>
    <div className="flex gap-2">
      <button
        onClick={() => submitFeedback('satisfied')}
        className="flex-1 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200"
      >
        Yes, worked well
      </button>
      <button
        onClick={() => submitFeedback('unsatisfied')}
        className="flex-1 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200"
      >
        No, had issues
      </button>
    </div>
  </div>
)}
```

**When You Might Be Tempted:**
When you want to measure "user satisfaction" generically. Internal tools should measure **task success**, not brand loyalty.

### WARNING: Public Roadmap for Internal Tools

**The Problem:**

Creating a public Trello/GitHub Projects board for internal tool roadmap.

**Why This Breaks:**
1. **Security risk** - Exposes internal processes and priorities
2. **Unnecessary** - Small user base can communicate directly
3. **Overhead** - Maintaining public roadmap takes time

**The Fix:**

Use **email updates or Slack channel** for roadmap communication:

```markdown
# Monthly Update - January 2026

## Shipped This Month
- Energy Transfer statement support in Revenue tool
- Bulk edit for Extract tool (beta)
- Job history on Dashboard

## Coming Next Month
- Proration auto-refresh
- Extract flagged entry improvements
- Performance optimizations

Questions? Reply to this email or ping @james in #table-rock-tools