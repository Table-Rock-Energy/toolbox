# Feedback & Insights Reference

## Contents
- User Feedback Collection
- Error Tracking
- Support Signal Analysis

---

## User Feedback Collection

### In-App Feedback Widget

```typescript
// frontend/src/components/FeedbackWidget.tsx
import { useState } from 'react'
import { MessageSquare, X } from 'lucide-react'
import { useAnalytics } from '../hooks/useAnalytics'

export function FeedbackWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [category, setCategory] = useState<'bug' | 'feature' | 'other'>('other')
  const { track } = useAnalytics()

  const handleSubmit = async () => {
    track('feedback_submitted', {
      category,
      feedback_length: feedback.length,
      current_page: window.location.pathname,
    })

    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category,
        feedback,
        page: window.location.pathname,
        // Include what user was doing for context
        context: {
          tool: window.location.pathname.replace('/', '') || 'dashboard',
        },
      }),
    })

    setFeedback('')
    setIsOpen(false)
  }

  return (
    <>
      <button
        onClick={() => {
          track('feedback_widget_opened')
          setIsOpen(true)
        }}
        className="fixed bottom-4 right-4 bg-tre-teal text-white p-3 rounded-full shadow-lg z-50"
      >
        <MessageSquare className="w-5 h-5" />
      </button>

      {isOpen && (
        <div className="fixed bottom-20 right-4 bg-white rounded-lg shadow-xl p-4 w-80 z-50">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-oswald font-semibold text-tre-navy">Send Feedback</h3>
            <button onClick={() => setIsOpen(false)}>
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          <select
            value={category}
            onChange={e => setCategory(e.target.value as typeof category)}
            className="w-full mb-2 p-2 border rounded text-sm"
          >
            <option value="bug">Report Bug</option>
            <option value="feature">Feature Request</option>
            <option value="other">Other</option>
          </select>

          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Tell us what you think..."
            className="w-full p-2 border rounded mb-2 text-sm"
            rows={4}
          />

          <button
            onClick={handleSubmit}
            disabled={!feedback.trim()}
            className="w-full bg-tre-teal text-white p-2 rounded text-sm disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      )}
    </>
  )
}
```

### Backend Feedback Storage

```python
# backend/app/api/feedback.py
from pydantic import BaseModel, Field
from app.services.firestore_service import get_firestore_client

FEEDBACK_COLLECTION = "feedback"

class FeedbackRequest(BaseModel):
    category: str = Field(..., pattern="^(bug|feature|other)$")
    feedback: str = Field(..., min_length=1, max_length=2000)
    page: str
    context: dict = Field(default_factory=dict)

@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user=Depends(get_current_user),
):
    db = get_firestore_client()
    await db.collection(FEEDBACK_COLLECTION).add({
        "user_id": user.uid,
        "category": request.category,
        "feedback": request.feedback,
        "page": request.page,
        "context": request.context,
        "created_at": datetime.now(tz=timezone.utc),
        "status": "new",
    })
    return {"success": True}
```

**DO/DON'T:**

**BAD - Generic context:**
```typescript
{ feedback: "Export button doesn't work" }
```

**GOOD - Rich context:**
```typescript
{
  feedback: "Export button doesn't work",
  context: {
    tool: "extract",
    entries_count: 45,
    filters_active: ["individuals_only"],
  }
}
```

**WHY:** Without context, you can't reproduce the bug. With it, you know exactly what state the user was in.

---

## Error Tracking

### WARNING: NEVER Expose Raw Exceptions to Clients

**BAD - Security risk, information leak:**
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
    # Exposes: "OSError: [Errno 13] Permission denied: '/data/rrc-data/oil.csv'"
    # Reveals internal paths, system info, and implementation details
```

**GOOD - Log internally, return sanitized message:**
```python
except Exception as e:
    logger.exception("Extract upload failed for user %s", user.uid)
    await track_event(
        "backend_error",
        user_id=user.uid,
        properties={
            "error_type": type(e).__name__,
            "endpoint": "/extract/upload",
            "file_name": file.filename,
        }
    )
    raise HTTPException(
        status_code=500,
        detail="PDF processing failed. Try a different file or contact support."
    )
```

### Frontend Error Boundary

```typescript
// frontend/src/components/ErrorBoundary.tsx
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State { hasError: boolean; error: Error | null }

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Track to backend — don't expose to user
    fetch('/api/events/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_name: 'frontend_error',
        properties: {
          error_message: error.message,
          page: window.location.pathname,
          component_stack: info.componentStack?.slice(0, 500),  // Truncate
        },
      }),
    }).catch(() => {/* don't crash error handler */})
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="font-oswald text-xl text-tre-navy mb-2">Something went wrong</h2>
          <p className="text-gray-600 mb-4">Please reload the page and try again.</p>
          <button
            onClick={() => window.location.reload()}
            className="bg-tre-teal text-white px-4 py-2 rounded"
          >
            Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
```

---

## Support Signal Analysis

```python
# Query feedback by category and page to prioritize fixes
async def get_feedback_summary(days: int = 30) -> dict:
    db = get_firestore_client()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    by_category: dict[str, int] = {}
    by_page: dict[str, int] = {}

    async for doc in db.collection(FEEDBACK_COLLECTION).where(
        "created_at", ">=", cutoff
    ).stream():
        data = doc.to_dict()
        cat = data.get("category", "other")
        page = data.get("page", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        by_page[page] = by_page.get(page, 0) + 1

    return {
        "by_category": by_category,
        "top_pages": sorted(by_page.items(), key=lambda x: x[1], reverse=True)[:5],
        "total": sum(by_category.values()),
    }
```

**Action rule:** High `bug` count on `/proration` → prioritize proration UX improvements in next sprint. High `feature` count → review for common themes before adding to roadmap.

See the **fastapi** skill for router setup and the **firestore** skill for Firestore client patterns.
