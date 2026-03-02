# Feedback & Insights Reference

## Contents
- User Feedback Collection
- Error Tracking
- Support Signal Analysis
- Feature Request Prioritization

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
        user_agent: navigator.userAgent,
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
        className="fixed bottom-4 right-4 bg-tre-teal text-white p-3 rounded-full shadow-lg"
      >
        <MessageSquare className="w-5 h-5" />
      </button>
      
      {isOpen && (
        <div className="fixed bottom-20 right-4 bg-white rounded-lg shadow-xl p-4 w-80">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-oswald font-semibold">Send Feedback</h3>
            <button onClick={() => setIsOpen(false)}>
              <X className="w-4 h-4" />
            </button>
          </div>
          
          <select 
            value={category} 
            onChange={e => setCategory(e.target.value as any)}
            className="w-full mb-2 p-2 border rounded"
          >
            <option value="bug">Report Bug</option>
            <option value="feature">Feature Request</option>
            <option value="other">Other</option>
          </select>
          
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Tell us what you think..."
            className="w-full p-2 border rounded mb-2"
            rows={4}
          />
          
          <button 
            onClick={handleSubmit}
            disabled={!feedback.trim()}
            className="w-full bg-tre-teal text-white p-2 rounded disabled:opacity-50"
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
from pydantic import BaseModel
from app.services.firestore_service import get_firestore_client

FEEDBACK_COLLECTION = "feedback"

class FeedbackRequest(BaseModel):
    category: str
    feedback: str
    page: str
    user_agent: str

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest, user_id: str = Depends(get_current_user)):
    """Store user feedback in Firestore."""
    db = get_firestore_client()
    
    feedback_doc = {
        "user_id": user_id,
        "category": request.category,
        "feedback": request.feedback,
        "page": request.page,
        "user_agent": request.user_agent,
        "created_at": datetime.utcnow(),
        "status": "new",
    }
    
    await db.collection(FEEDBACK_COLLECTION).add(feedback_doc)
    
    return {"success": True}
```

**DO/DON'T:**

**BAD - Generic feedback form:**
```typescript
<textarea placeholder="Feedback..." />
```

**GOOD - Contextual feedback with metadata:**
```typescript
// Capture WHAT they were doing when feedback given
{
  feedback: "Export button doesn't work",
  context: {
    tool: "extract",
    entries_count: 45,
    filters_active: ["individuals_only"],
    last_action: "clicked_export_csv",
  }
}
```

---

## Error Tracking

### Frontend Error Boundary with Tracking

```typescript
// frontend/src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo } from 'react'

interface Props {
  children: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Track error to backend
    fetch('/api/events/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_name: 'frontend_error',
        properties: {
          error_message: error.message,
          error_stack: error.stack,
          component_stack: errorInfo.componentStack,
          page: window.location.pathname,
        },
      }),
    }).catch(console.error)
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-xl font-oswald mb-2">Something went wrong</h2>
          <p className="text-gray-600 mb-4">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      )
    }
    
    return this.props.children
  }
}
```

### Backend Error Tracking

```python
# Track API errors with context
@router.post("/extract/upload")
async def upload_extract(file: UploadFile, user_id: str = Depends(get_current_user)):
    try:
        result = await extract_service.process_pdf(file)
        return result
    except Exception as e:
        await track_event(
            "backend_error",
            user_id=user_id,
            properties={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "endpoint": "/extract/upload",
                "file_name": file.filename,
                "file_size_mb": file.size / 1024 / 1024 if file.size else 0,
            }
        )
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Support Signal Analysis

### Query Feedback by Category

```python
async def get_feedback_summary(days: int = 30) -> dict:
    """Aggregate feedback by category."""
    db = get_firestore_client()
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    feedback_docs = db.collection(FEEDBACK_COLLECTION).where(
        "created_at", ">=", cutoff
    ).stream()
    
    by_category = {"bug": 0, "feature": 0, "other": 0}
    by_page = {}
    
    async for doc in feedback_docs:
        data = doc.to_dict()
        by_category[data["category"]] = by_category.get(data["category"], 0) + 1
        by_page[data["page"]] = by_page.get(data["page"], 0) + 1
    
    return {
        "by_category": by_category,
        "by_page": sorted(by_page.items(), key=lambda x: x[1], reverse=True),
        "total": sum(by_category.values()),
    }
```

**Action:** High bug reports on `/proration` → prioritize proration UX improvements.