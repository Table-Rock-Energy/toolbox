# Roadmap & Experiments Reference

## Contents
- Feature Flags (Missing)
- A/B Testing Patterns (Not Implemented)
- Gradual Rollouts
- User Feedback Collection
- Beta Feature Gates

---

## Feature Flags (Missing)

### WARNING: No Feature Flag System

The application has **NO feature flag infrastructure**. All features are deployed to production immediately on `git push main`.

**Problem:** Can't:
- Test features with subset of users
- Roll back features without redeploying
- Run A/B experiments
- Gate beta features behind opt-in

**Recommendation:** Add LaunchDarkly, PostHog feature flags, or simple environment-based flags.

---

## A/B Testing Patterns (Not Implemented)

### Proposed Pattern for Testing UI Variants

**Scenario:** Test two export button placements (top vs bottom of results table).

**Implementation (if feature flags existed):**
```typescript
// pages/Extract.tsx
import { useFeatureFlag } from '../utils/featureFlags';

function Extract() {
  const exportButtonAtTop = useFeatureFlag('export-button-top', false);
  const [results, setResults] = useState<PartyEntry[]>([]);
  
  const ExportButtons = () => (
    <div className="flex gap-2">
      <button onClick={exportCSV}>Export CSV</button>
      <button onClick={exportExcel}>Export Excel</button>
    </div>
  );
  
  return (
    <div>
      {exportButtonAtTop && <ExportButtons />}
      
      <DataTable data={results} columns={columns} />
      
      {!exportButtonAtTop && <ExportButtons />}
    </div>
  );
}
```

**Track variant impact:**
```typescript
const handleExport = (format: 'csv' | 'excel') => {
  trackEvent('export_started', {
    tool_name: 'extract',
    export_format: format,
    export_button_variant: exportButtonAtTop ? 'top' : 'bottom',
  });
  
  // ... export logic
};
```

**Analysis:** Compare export rate between variants. If "top" placement increases exports by 20%, ship it to everyone.

---

## Gradual Rollouts

### Percentage-Based Rollouts

**Pattern for testing risky changes:**

```typescript
// utils/featureFlags.ts (proposed)
export function useFeatureFlag(flagName: string, defaultValue: boolean): boolean {
  const user = useAuth();
  
  // Check backend for flag state
  const [enabled, setEnabled] = useState(defaultValue);
  
  useEffect(() => {
    fetch(`/api/feature-flags/${flagName}?user=${user.email}`)
      .then(r => r.json())
      .then(data => setEnabled(data.enabled));
  }, [flagName, user.email]);
  
  return enabled;
}
```

**Backend rollout logic:**
```python
# backend/app/api/feature_flags.py (to be created)
from hashlib import md5

@router.get("/feature-flags/{flag_name}")
async def get_feature_flag(flag_name: str, user: str):
    # Percentage-based rollout
    rollout_percentage = {
        "new-pdf-parser": 10,  # 10% of users
        "batch-processing": 50,  # 50% of users
    }.get(flag_name, 0)
    
    # Deterministic hash: same user always sees same variant
    user_hash = int(md5(user.encode()).hexdigest(), 16)
    user_bucket = user_hash % 100
    
    enabled = user_bucket < rollout_percentage
    
    return {"enabled": enabled, "rollout_percentage": rollout_percentage}
```

**Why This Matters:** Roll out new PDF parser to 10% of users first. If error rate spikes, disable flag and fix before wider release.

---

## User Feedback Collection

### In-App Feedback Widget

**Current State:** No feedback mechanism in the app. Users must email `james@tablerocktx.com` for issues.

**GOOD - Contextual feedback form:**
```typescript
// components/FeedbackButton.tsx
import { useState } from 'react';
import { MessageSquare } from 'lucide-react';
import { Modal } from './Modal';

export function FeedbackButton() {
  const [showModal, setShowModal] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);
  
  const handleSubmit = async () => {
    await fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        feedback,
        page: window.location.pathname,
        user: useAuth().user?.email,
        timestamp: new Date().toISOString(),
      }),
    });
    
    setSubmitted(true);
    setTimeout(() => {
      setShowModal(false);
      setSubmitted(false);
      setFeedback('');
    }, 2000);
  };
  
  return (
    <>
      <button 
        onClick={() => setShowModal(true)}
        className="fixed bottom-4 right-4 bg-tre-teal text-white p-3 rounded-full shadow-lg hover:bg-tre-navy"
        aria-label="Send feedback"
      >
        <MessageSquare className="w-6 h-6" />
      </button>
      
      {showModal && (
        <Modal onClose={() => setShowModal(false)}>
          <h3 className="text-xl font-bold mb-4">Send Feedback</h3>
          
          {submitted ? (
            <p className="text-green-600">✅ Thank you for your feedback!</p>
          ) : (
            <>
              <textarea 
                value={feedback}
                onChange={e => setFeedback(e.target.value)}
                placeholder="What could we improve?"
                className="w-full h-32 border border-gray-300 rounded p-2"
              />
              <div className="flex gap-2 mt-4">
                <button onClick={handleSubmit} className="btn-primary">
                  Submit
                </button>
                <button onClick={() => setShowModal(false)} className="btn-secondary">
                  Cancel
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
```

**Backend storage:**
```python
# backend/app/api/feedback.py (to be created)
from datetime import datetime
from app.services.firestore_service import firestore_service

@router.post("/feedback")
async def submit_feedback(
    feedback: str,
    page: str,
    user: str,
    timestamp: str,
):
    await firestore_service.add_document("feedback", {
        "feedback": feedback,
        "page": page,
        "user": user,
        "timestamp": timestamp,
        "status": "new",
    })
    
    return {"status": "success"}
```

**Why This Matters:** Capture feedback at the moment of frustration. User encounters bug → clicks feedback button → describes issue → team gets context-rich report.

---

## Beta Feature Gates

### Opt-In Beta Program

**Pattern for testing experimental features:**

```typescript
// pages/Settings.tsx
const [betaOptIn, setBetaOptIn] = useState(false);

useEffect(() => {
  const currentOptIn = localStorage.getItem('beta-opt-in') === 'true';
  setBetaOptIn(currentOptIn);
}, []);

const handleBetaToggle = (enabled: boolean) => {
  setBetaOptIn(enabled);
  localStorage.setItem('beta-opt-in', enabled.toString());
  
  trackEvent('beta_program_toggled', {enabled});
};

<div className="bg-blue-50 border border-blue-200 p-4 rounded">
  <h3 className="font-bold mb-2">🧪 Beta Features</h3>
  <p className="mb-4">
    Get early access to new features before they're released to everyone.
  </p>
  
  <label className="flex items-center gap-2">
    <input 
      type="checkbox"
      checked={betaOptIn}
      onChange={e => handleBetaToggle(e.target.checked)}
    />
    <span>Enable beta features</span>
  </label>
  
  {betaOptIn && (
    <div className="mt-4 text-sm text-gray-600">
      <p>Active beta features:</p>
      <ul className="list-disc ml-6">
        <li>Batch file processing (Extract tool)</li>
        <li>Advanced filtering (all tools)</li>
        <li>Keyboard shortcuts</li>
      </ul>
    </div>
  )}
</div>
```

**Conditional rendering:**
```typescript
// pages/Extract.tsx
const betaEnabled = localStorage.getItem('beta-opt-in') === 'true';

{betaEnabled && (
  <div className="bg-blue-50 border border-blue-200 p-4 rounded mb-4">
    <span className="text-xs bg-blue-500 text-white px-2 py-1 rounded">BETA</span>
    <h4 className="font-bold mt-2">Batch Processing</h4>
    <FileUpload multiple={true} onFileSelect={handleBatchUpload} />
  </div>
)}
```

**Why This Matters:** Power users get early access to features, provide feedback before general release. Reduces risk of shipping broken features.

---

## Common Experimentation Anti-Patterns

### 1. No Control Group

**BAD - Ship new feature to 100% of users immediately:**
```typescript
// New feature live for everyone
<NewFeatureComponent />
```

**GOOD - A/B test with 50/50 split:**
```typescript
const showNewFeature = useFeatureFlag('new-feature', false);

{showNewFeature ? <NewFeatureComponent /> : <OldFeatureComponent />}
```

**Why This Breaks:** Can't measure impact. Is increased engagement due to the new feature or seasonal trends?

### 2. Changing Multiple Things at Once

**BAD - Ship 5 changes together:**
```typescript
// New layout + new colors + new copy + new workflow + new export format
```

**GOOD - Test one variable at a time:**
```typescript
// Week 1: Test new export format (CSV → Excel)
// Week 2: Test new button copy ("Export" → "Download Results")
// Week 3: Test button placement (top → bottom)
```

**Why This Breaks:** If metrics improve, don't know which change caused it. If metrics decline, don't know which change to revert.

### 3. No Exit Criteria

**BAD - Run experiment indefinitely:**
```typescript
// Feature flag enabled for 6 months, never analyzed
```

**GOOD - Define success metrics upfront:**
```markdown
Hypothesis: Moving export buttons to top will increase export rate
Metric: % of sessions that export results
Target: 10% increase
Sample size: 1000 users per variant
Duration: 2 weeks
Decision: Ship if target met, revert if declined
```

**Why This Breaks:** Technical debt accumulates. Codebase fills with `if (featureFlag)` branches that never get cleaned up.