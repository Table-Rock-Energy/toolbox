# Feedback & Insights Reference

## Contents
- Support Signal Collection
- Feature Request Tracking
- User Interviews (Internal)
- Error Reporting
- Usage-Based Prioritization

---

## Support Signal Collection

**For internal tools:** Users will Slack you or walk over to your desk. Capture these interactions systematically.

### Pattern: Feedback Button in App

```tsx
// MainLayout.tsx - Add feedback button in header
import { MessageCircle } from 'lucide-react';

const [showFeedbackModal, setShowFeedbackModal] = useState(false);

// Header:
<header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
  <h1 className="text-xl font-oswald font-semibold text-tre-navy">
    {pageTitle}
  </h1>
  
  <button
    onClick={() => setShowFeedbackModal(true)}
    className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-tre-teal transition-colors"
  >
    <MessageCircle className="w-4 h-4" />
    Send Feedback
  </button>
</header>
```

**Feedback modal:**

```tsx
// components/FeedbackModal.tsx
import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export default function FeedbackModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const [type, setType] = useState<'bug' | 'feature' | 'question'>('bug');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    
    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type,
        message,
        url: window.location.pathname,
      }),
    });
    
    setSubmitting(false);
    setMessage('');
    onClose();
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-md w-full">
        <h2 className="text-xl font-oswald font-semibold text-tre-navy mb-4">
          Send Feedback
        </h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Type
            </label>
            <div className="flex gap-2">
              {(['bug', 'feature', 'question'] as const).map(t => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    type === t
                      ? 'bg-tre-teal text-tre-navy'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {t === 'bug' ? 'Bug Report' : t === 'feature' ? 'Feature Request' : 'Question'}
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
              onChange={e => setMessage(e.target.value)}
              required
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
              placeholder="Describe the issue or request..."
            />
          </div>
          
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-tre-teal text-tre-navy rounded-lg font-medium hover:bg-tre-teal/90 disabled:opacity-50"
            >
              {submitting ? 'Sending...' : 'Send Feedback'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

### Backend: Store Feedback in Firestore

```python
# api/feedback.py - New file
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.auth import get_current_user_email
from app.services import firestore_service as db

router = APIRouter()

class FeedbackSubmission(BaseModel):
    type: str = Field(..., description="bug, feature, or question")
    message: str = Field(..., min_length=10, description="Feedback text")
    url: str = Field(..., description="Page URL where feedback was submitted")

@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackSubmission,
    current_user: str = Depends(get_current_user_email)
):
    """Store user feedback in Firestore."""
    feedback_doc = {
        "user_email": current_user,
        "type": feedback.type,
        "message": feedback.message,
        "url": feedback.url,
        "timestamp": datetime.utcnow(),
        "status": "new",  # new, reviewed, addressed
    }
    
    db_client = db.get_firestore_client()
    await db_client.collection("feedback").add(feedback_doc)
    
    return {"success": True}
```

**Register router in main.py:**

```python
# main.py
from app.api import feedback

app.include_router(feedback.router, prefix="/api", tags=["feedback"])
```

---

## Feature Request Tracking

**Pattern: Lightweight voting system**

```python
# api/feedback.py
@router.get("/feedback/feature-requests")
async def get_feature_requests():
    """List all feature requests with vote counts."""
    db_client = db.get_firestore_client()
    
    # Get all feature requests
    requests = db_client.collection("feedback").where("type", "==", "feature").stream()
    
    features = []
    for req in requests:
        data = req.to_dict()
        features.append({
            "id": req.id,
            "message": data["message"],
            "user_email": data["user_email"],
            "votes": data.get("votes", []),
            "vote_count": len(data.get("votes", [])),
            "status": data.get("status", "new"),
            "created_at": data["timestamp"].isoformat(),
        })
    
    # Sort by vote count
    features.sort(key=lambda x: x["vote_count"], reverse=True)
    
    return {"feature_requests": features}


@router.post("/feedback/{request_id}/vote")
async def vote_for_feature(
    request_id: str,
    current_user: str = Depends(get_current_user_email)
):
    """Upvote a feature request."""
    db_client = db.get_firestore_client()
    doc_ref = db_client.collection("feedback").document(request_id)
    
    doc = await doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Feature request not found")
    
    data = doc.to_dict()
    votes = data.get("votes", [])
    
    if current_user in votes:
        # Remove vote (toggle)
        votes.remove(current_user)
    else:
        # Add vote
        votes.append(current_user)
    
    await doc_ref.update({"votes": votes})
    
    return {"voted": current_user in votes, "vote_count": len(votes)}
```

**Frontend: Feature Request Board**

```tsx
// pages/FeatureRequests.tsx
import { useEffect, useState } from 'react';
import { ThumbsUp } from 'lucide-react';

interface FeatureRequest {
  id: string;
  message: string;
  vote_count: number;
  votes: string[];
  status: string;
}

export default function FeatureRequests() {
  const [requests, setRequests] = useState<FeatureRequest[]>([]);
  const { user } = useAuth();
  
  useEffect(() => {
    const fetchRequests = async () => {
      const response = await fetch('/api/feedback/feature-requests');
      const data = await response.json();
      setRequests(data.feature_requests);
    };
    
    fetchRequests();
  }, []);
  
  const handleVote = async (requestId: string) => {
    await fetch(`/api/feedback/${requestId}/vote`, { method: 'POST' });
    
    // Refresh list
    const response = await fetch('/api/feedback/feature-requests');
    const data = await response.json();
    setRequests(data.feature_requests);
  };
  
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
        Feature Requests
      </h1>
      
      {requests.map(req => (
        <div key={req.id} className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <p className="text-gray-900">{req.message}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`
                  inline-block px-2 py-0.5 rounded text-xs font-medium uppercase
                  ${req.status === 'new' ? 'bg-gray-100 text-gray-700' : ''}
                  ${req.status === 'planned' ? 'bg-blue-100 text-blue-800' : ''}
                  ${req.status === 'in-progress' ? 'bg-amber-100 text-amber-800' : ''}
                  ${req.status === 'shipped' ? 'bg-green-100 text-green-800' : ''}
                `}>
                  {req.status}
                </span>
              </div>
            </div>
            
            <button
              onClick={() => handleVote(req.id)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition-colors
                ${req.votes.includes(user?.email || '') 
                  ? 'bg-tre-teal text-tre-navy' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }
              `}
            >
              <ThumbsUp className="w-4 h-4" />
              {req.vote_count}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## User Interviews (Internal)

**For B2B internal tools:** Schedule 15-minute Zoom calls with heavy users quarterly.

**Questions to ask:**
1. Which tool do you use most? Why?
2. What's the most frustrating part of [tool name]?
3. If you could add one feature, what would it be?
4. How do you work around current limitations?
5. What would make you use [underutilized tool]?

**Capture notes in Firestore:**

```python
# Manual script: scripts/record_interview.py
from google.cloud import firestore
from datetime import datetime

db = firestore.Client()

interview = {
    "user_email": "emily@tablerocktx.com",
    "date": datetime(2026, 2, 9),
    "interviewer": "james@tablerocktx.com",
    "notes": """
    - Uses Extract daily, Title weekly
    - Frustrated by manual RRC data downloads (now fixed)
    - Requested: bulk export across multiple jobs
    - Would use Revenue tool more if it supported Occidental PDFs
    """,
    "key_requests": ["bulk_export", "occidental_revenue_support"],
}

db.collection("user_interviews").add(interview)
print("Interview recorded")
```

---

## Error Reporting

**Pattern: Automatic error capture to Firestore**

```python
# main.py - Global exception handler
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.services import firestore_service as db

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled errors and log to Firestore."""
    logger.exception(f"Unhandled error: {exc}")
    
    # Log error to Firestore for analysis
    error_doc = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "url": str(request.url),
        "method": request.method,
        "user_email": getattr(request.state, "user_email", None),
        "timestamp": datetime.utcnow(),
        "stack_trace": traceback.format_exc(),
    }
    
    try:
        db_client = db.get_firestore_client()
        await db_client.collection("errors").add(error_doc)
    except:
        pass  # Don't fail on error logging failure
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Our team has been notified."}
    )
```

**Admin view of errors:**

```tsx
// pages/Errors.tsx - Admin-only error log
import { useEffect, useState } from 'react';

interface ErrorLog {
  id: string;
  error_type: string;
  error_message: string;
  url: string;
  user_email: string;
  timestamp: string;
}

export default function Errors() {
  const [errors, setErrors] = useState<ErrorLog[]>([]);
  
  useEffect(() => {
    const fetchErrors = async () => {
      const response = await fetch('/api/admin/errors?limit=50');
      const data = await response.json();
      setErrors(data.errors);
    };
    
    fetchErrors();
  }, []);
  
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
        Error Log
      </h1>
      
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {errors.map(error => (
              <tr key={error.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-mono text-red-600">{error.error_type}</td>
                <td className="px-4 py-3 text-sm text-gray-900">{error.error_message}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{error.user_email}</td>
                <td className="px-4 py-3 text-sm text-gray-500">
                  {new Date(error.timestamp).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## Usage-Based Prioritization

**Pattern: Sort feature requests by user activity**

```python
# api/feedback.py
@router.get("/feedback/prioritized")
async def get_prioritized_features():
    """Feature requests sorted by votes + requester activity."""
    from app.services import firestore_service as db
    
    # Get feature requests
    db_client = db.get_firestore_client()
    requests = db_client.collection("feedback").where("type", "==", "feature").stream()
    
    features = []
    for req in requests:
        data = req.to_dict()
        user_email = data["user_email"]
        
        # Get user's activity level (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        user_events = await db.get_usage_events_since(cutoff, user_email=user_email)
        
        features.append({
            "id": req.id,
            "message": data["message"],
            "vote_count": len(data.get("votes", [])),
            "requester_activity_score": len(user_events),  # Weight by power user
            "priority_score": len(data.get("votes", [])) + (len(user_events) / 10),
        })
    
    # Sort by priority score
    features.sort(key=lambda x: x["priority_score"], reverse=True)
    
    return {"features": features}
```

**Principle:** Requests from daily users (power users) should be weighted higher than one-off feature requests from inactive users.