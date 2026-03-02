# Feedback & Insights Reference

## Contents
- Error Rate Analysis
- Support Request Patterns
- User Friction Signals
- Feature Request Tracking
- Qualitative Insights

---

## Error Rate Analysis

### Backend Error Logging

**Current State:**
```python
# backend/app/api/extract.py
logger = logging.getLogger(__name__)

try:
    result = await extract_service.process_pdf(file)
except Exception as e:
    logger.error(f"PDF processing failed: {str(e)}")
    raise HTTPException(status_code=500, detail="Processing failed")
```

**GOOD - Categorized error tracking:**
```python
# backend/app/utils/error_tracker.py
from enum import Enum
from collections import Counter
from datetime import datetime, timedelta

class ErrorCategory(str, Enum):
    VALIDATION = "validation_error"
    FILE_PARSE = "file_parse_error"
    RRC_DOWNLOAD = "rrc_download_error"
    STORAGE = "storage_error"
    DATABASE = "database_error"
    UNKNOWN = "unknown_error"

error_log: list[dict] = []

def log_error(category: ErrorCategory, details: str, tool: str):
    error_log.append({
        "category": category,
        "details": details,
        "tool": tool,
        "timestamp": datetime.now(),
    })
    
    # Also write to Firestore for persistence
    firestore_service.add_document("errors", {
        "category": category,
        "details": details,
        "tool": tool,
        "timestamp": datetime.now().isoformat(),
    })

def get_error_summary(days: int = 7) -> dict:
    cutoff = datetime.now() - timedelta(days=days)
    recent_errors = [e for e in error_log if e["timestamp"] > cutoff]
    
    return {
        "total_errors": len(recent_errors),
        "by_category": dict(Counter(e["category"] for e in recent_errors)),
        "by_tool": dict(Counter(e["tool"] for e in recent_errors)),
    }
```

**Usage in routes:**
```python
# backend/app/api/extract.py
from app.utils.error_tracker import log_error, ErrorCategory

try:
    result = await extract_service.process_pdf(file)
except PyMuPDFError as e:
    log_error(ErrorCategory.FILE_PARSE, str(e), "extract")
    raise HTTPException(status_code=400, detail="PDF parsing failed")
except Exception as e:
    log_error(ErrorCategory.UNKNOWN, str(e), "extract")
    raise HTTPException(status_code=500, detail="Processing failed")
```

**Admin dashboard endpoint:**
```python
# backend/app/api/admin.py
@router.get("/errors/summary")
async def get_error_summary(days: int = 7):
    return error_tracker.get_error_summary(days)
```

**Why This Matters:** Identify systemic issues. If 80% of errors are `FILE_PARSE` in Extract tool, prioritize better PDF handling.

---

## Support Request Patterns

### Tagging Common Issues

**Pattern for categorizing feedback:**

```python
# backend/app/models/feedback.py
from pydantic import BaseModel
from enum import Enum

class FeedbackCategory(str, Enum):
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    HELP_NEEDED = "help_needed"
    PERFORMANCE_ISSUE = "performance_issue"
    UI_CONFUSION = "ui_confusion"

class Feedback(BaseModel):
    user_email: str
    page: str
    message: str
    category: FeedbackCategory | None = None  # Auto-tagged or manual
    timestamp: str
    resolved: bool = False
```

**Auto-categorization (simple keyword matching):**
```python
# backend/app/api/feedback.py
def auto_categorize(message: str) -> FeedbackCategory:
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["error", "broken", "doesn't work", "crash"]):
        return FeedbackCategory.BUG_REPORT
    elif any(word in message_lower for word in ["slow", "loading", "takes too long"]):
        return FeedbackCategory.PERFORMANCE_ISSUE
    elif any(word in message_lower for word in ["how do i", "what is", "where do i"]):
        return FeedbackCategory.HELP_NEEDED
    elif any(word in message_lower for word in ["add", "feature", "would be nice"]):
        return FeedbackCategory.FEATURE_REQUEST
    else:
        return FeedbackCategory.UI_CONFUSION  # Default
```

**Aggregate insights:**
```python
@router.get("/feedback/insights")
async def get_feedback_insights():
    all_feedback = await firestore_service.get_collection("feedback")
    
    categories = Counter(f["category"] for f in all_feedback)
    pages = Counter(f["page"] for f in all_feedback)
    
    return {
        "total_feedback": len(all_feedback),
        "by_category": dict(categories),
        "top_problem_pages": dict(pages.most_common(5)),
    }
```

**Why This Matters:** If 50% of feedback is "Help needed" on Proration page, add better in-app guidance there.

---

## User Friction Signals

### Implicit Signals (No Explicit Feedback Required)

**Patterns that indicate friction:**

1. **Rapid back-and-forth navigation** (user lost)
2. **Multiple failed uploads** (validation unclear)
3. **Long time on page without action** (confusion)
4. **Refresh/reload spamming** (expecting update that didn't happen)

**Track navigation churn:**
```typescript
// utils/analytics.ts
let navigationHistory: string[] = [];

export function trackNavigation(from: string, to: string) {
  navigationHistory.push(to);
  
  // Detect thrashing (visiting same page 3+ times in 2 minutes)
  const recentPages = navigationHistory.slice(-10);
  const pageVisits = recentPages.filter(p => p === to).length;
  
  if (pageVisits >= 3) {
    trackEvent('navigation_thrashing', {
      page: to,
      visit_count: pageVisits,
    });
  }
}

// Usage in router
useEffect(() => {
  const currentPath = window.location.pathname;
  trackNavigation(previousPath, currentPath);
  setPreviousPath(currentPath);
}, [window.location.pathname]);
```

**Track failed uploads:**
```typescript
// pages/Extract.tsx
let uploadAttempts = 0;

const handleUpload = async (files: File[]) => {
  uploadAttempts++;
  
  try {
    const result = await api.upload(files[0]);
    uploadAttempts = 0; // Reset on success
    setResults(result);
  } catch (err) {
    if (uploadAttempts >= 3) {
      trackEvent('repeated_upload_failure', {
        tool_name: 'extract',
        attempt_count: uploadAttempts,
        error_type: err.message,
      });
      
      // Show help modal after 3 failures
      setShowHelpModal(true);
    }
    
    setError(err.message);
  }
};
```

**Why This Matters:** Users won't always click "Feedback" when stuck. Detect patterns algorithmically and intervene proactively.

---

## Feature Request Tracking

### Upvoting System (Proposed)

**Backend model:**
```python
# backend/app/models/feature_request.py
from pydantic import BaseModel

class FeatureRequest(BaseModel):
    id: str
    title: str
    description: str
    requested_by: str  # User email
    upvotes: list[str] = []  # List of user emails who upvoted
    status: str = "submitted"  # submitted | planned | in_progress | shipped
    created_at: str
```

**API endpoints:**
```python
# backend/app/api/feature_requests.py
@router.post("/feature-requests")
async def create_feature_request(
    title: str,
    description: str,
    user_email: str,
):
    request_id = generate_uid()
    request = FeatureRequest(
        id=request_id,
        title=title,
        description=description,
        requested_by=user_email,
        created_at=datetime.now().isoformat(),
    )
    
    await firestore_service.add_document("feature_requests", request.dict())
    return request

@router.post("/feature-requests/{request_id}/upvote")
async def upvote_feature_request(request_id: str, user_email: str):
    request = await firestore_service.get_document("feature_requests", request_id)
    
    if user_email not in request["upvotes"]:
        request["upvotes"].append(user_email)
        await firestore_service.update_document("feature_requests", request_id, {
            "upvotes": request["upvotes"]
        })
    
    return {"upvote_count": len(request["upvotes"])}

@router.get("/feature-requests")
async def get_feature_requests(sort_by: str = "upvotes"):
    requests = await firestore_service.get_collection("feature_requests")
    
    if sort_by == "upvotes":
        requests.sort(key=lambda r: len(r["upvotes"]), reverse=True)
    
    return requests
```

**Frontend feature request board:**
```typescript
// pages/FeatureRequests.tsx (new page)
function FeatureRequests() {
  const [requests, setRequests] = useState<FeatureRequest[]>([]);
  const user = useAuth().user;
  
  useEffect(() => {
    fetch('/api/feature-requests?sort_by=upvotes')
      .then(r => r.json())
      .then(setRequests);
  }, []);
  
  const handleUpvote = async (requestId: string) => {
    await fetch(`/api/feature-requests/${requestId}/upvote`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_email: user.email}),
    });
    
    // Refresh list
    const updated = await fetch('/api/feature-requests?sort_by=upvotes').then(r => r.json());
    setRequests(updated);
  };
  
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Feature Requests</h2>
      
      <button 
        onClick={() => setShowNewRequestModal(true)}
        className="btn-primary mb-6"
      >
        + Request a Feature
      </button>
      
      <div className="space-y-4">
        {requests.map(req => (
          <div key={req.id} className="border border-gray-200 rounded p-4">
            <div className="flex items-start gap-4">
              <button 
                onClick={() => handleUpvote(req.id)}
                className={`flex flex-col items-center ${
                  req.upvotes.includes(user.email) ? 'text-tre-teal' : 'text-gray-400'
                }`}
              >
                <ChevronUp className="w-6 h-6" />
                <span className="font-bold">{req.upvotes.length}</span>
              </button>
              
              <div className="flex-1">
                <h3 className="font-bold text-lg">{req.title}</h3>
                <p className="text-gray-600 mt-1">{req.description}</p>
                <div className="flex gap-4 mt-2 text-sm text-gray-500">
                  <span>Requested by {req.requested_by}</span>
                  <span className="bg-gray-200 px-2 py-1 rounded">{req.status}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Why This Matters:** Democratic prioritization. Build features that 20 users want, not features that 1 loud user wants.

---

## Qualitative Insights

### User Interview Notes (Manual Process)

**Recommendation:** Create a simple notes collection in Firestore for qualitative insights.

```python
# backend/app/api/insights.py
from pydantic import BaseModel

class UserInsight(BaseModel):
    user_email: str
    insight_type: str  # "interview" | "observation" | "support_call"
    summary: str
    detailed_notes: str
    tags: list[str]  # ["extract", "performance", "ux"]
    recorded_by: str  # Admin/support email
    date: str

@router.post("/insights")
async def record_insight(insight: UserInsight):
    insight_id = generate_uid()
    await firestore_service.add_document("insights", {
        "id": insight_id,
        **insight.dict(),
    })
    return {"id": insight_id}

@router.get("/insights")
async def get_insights(tag: str | None = None):
    insights = await firestore_service.get_collection("insights")
    
    if tag:
        insights = [i for i in insights if tag in i.get("tags", [])]
    
    return insights
```

**Frontend admin view:**
```typescript
// pages/admin/Insights.tsx
function InsightsAdmin() {
  const [insights, setInsights] = useState<UserInsight[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  
  useEffect(() => {
    const url = selectedTag 
      ? `/api/insights?tag=${selectedTag}`
      : '/api/insights';
    
    fetch(url)
      .then(r => r.json())
      .then(setInsights);
  }, [selectedTag]);
  
  const allTags = [...new Set(insights.flatMap(i => i.tags))];
  
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">User Insights</h2>
      
      <div className="flex gap-2 mb-6">
        <button 
          onClick={() => setSelectedTag(null)}
          className={selectedTag === null ? 'btn-primary' : 'btn-secondary'}
        >
          All
        </button>
        {allTags.map(tag => (
          <button 
            key={tag}
            onClick={() => setSelectedTag(tag)}
            className={selectedTag === tag ? 'btn-primary' : 'btn-secondary'}
          >
            {tag}
          </button>
        ))}
      </div>
      
      <div className="space-y-4">
        {insights.map(insight => (
          <div key={insight.id} className="border border-gray-200 rounded p-4">
            <div className="flex justify-between items-start mb-2">
              <h3 className="font-bold">{insight.summary}</h3>
              <span className="text-sm text-gray-500">{insight.date}</span>
            </div>
            
            <p className="text-gray-700 mb-2">{insight.detailed_notes}</p>
            
            <div className="flex gap-2">
              {insight.tags.map(tag => (
                <span key={tag} className="bg-gray-200 px-2 py-1 rounded text-sm">
                  {tag}
                </span>
              ))}
            </div>
            
            <p className="text-sm text-gray-500 mt-2">
              Recorded by {insight.recorded_by}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Why This Matters:** Quantitative metrics (error rates, funnel drop-offs) tell WHAT is happening. Qualitative insights tell WHY.