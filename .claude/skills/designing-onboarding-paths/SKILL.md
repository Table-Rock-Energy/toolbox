---
name: designing-onboarding-paths
description: |
  Designs onboarding paths, empty states, and first-run experiences for Table Rock Tools internal application.
  Use when: implementing first-time user flows, designing empty states, adding job history displays, creating tool-specific walkthroughs, or improving activation patterns for internal users
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Designing Onboarding Paths

Table Rock Tools is an internal B2B application with Firebase Auth gating and tool-specific workflows. Unlike consumer apps, onboarding here means **getting authorized users productive fast** on Extract, Title, Proration, and Revenue tools.

## Current State

The app has:
- Login screen with Google Sign-In + email/password (toolbox/frontend/src/pages/Login.tsx)
- Dashboard with tool cards and empty state for recent activity (toolbox/frontend/src/pages/Dashboard.tsx)
- Help page with FAQs and search (toolbox/frontend/src/pages/Help.tsx)
- Job history API (toolbox/backend/app/api/history.py) NOT yet displayed in UI

**Missing:** First-run guidance, job history UI, progressive disclosure, tool-specific onboarding.

## Quick Start Patterns

### Empty State with Call-to-Action

```tsx
// toolbox/frontend/src/pages/Dashboard.tsx (current pattern)
{recentActivity.length === 0 ? (
  <div className="p-8 text-center text-gray-500">
    <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
    <p className="font-medium">No activity yet</p>
    <p className="text-sm mt-1">Tool usage will appear here</p>
  </div>
) : (
  // Table rendering
)}
```

**Problem:** Static message with no action. User has no next step.

**Fix:**
```tsx
// GOOD - Actionable empty state
{recentActivity.length === 0 ? (
  <div className="p-8 text-center text-gray-500">
    <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
    <p className="font-medium">No activity yet</p>
    <p className="text-sm mt-1 mb-4">Upload a file to get started</p>
    <div className="flex gap-3 justify-center">
      <Link to="/extract" className="px-4 py-2 bg-tre-teal text-white rounded-lg">
        Try Extract Tool
      </Link>
      <Link to="/help" className="px-4 py-2 border border-gray-300 rounded-lg">
        View Help
      </Link>
    </div>
  </div>
) : (
  // Recent jobs table
)}
```

### Job History Integration

```tsx
// Fetch job history on Dashboard mount
useEffect(() => {
  const fetchRecentJobs = async () => {
    const response = await fetch(`${API_BASE}/history/jobs?limit=10`)
    const data = await response.json()
    setRecentActivity(data.jobs.map(job => ({
      id: job.id,
      tool: job.tool,
      fileName: job.metadata?.filename || 'Unknown',
      user: job.user_email,
      timestamp: new Date(job.created_at).toLocaleString()
    })))
  }
  fetchRecentJobs()
}, [])
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Empty State | First-run or no-data screens with clear next action | Dashboard "No activity yet" → CTA to first tool |
| Tool Card | Primary navigation on Dashboard | 4 tool cards (Extract, Title, Proration, Revenue) with usage counts |
| FileUpload Pattern | Drag-drop UI used by all 4 tools | `<FileUpload onFilesSelected={handleFiles} />` |
| Job History | Firestore-tracked jobs displayed on Dashboard | `/api/history/jobs` endpoint NOT yet connected to UI |
| Help/FAQ | Searchable accordion for common questions | Help.tsx with expandable FAQs |

## Common Patterns

### Progressive Disclosure for Complex Tools

**When:** Tool has multi-step workflow (e.g., Proration requires RRC data download first)

```tsx
// toolbox/frontend/src/pages/Proration.tsx pattern
// Step 1: Show RRC data status banner if not ready
{!rrcDataReady && (
  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
    <div className="flex gap-3">
      <AlertCircle className="w-5 h-5 text-amber-600" />
      <div>
        <p className="font-medium text-amber-900">RRC Data Required</p>
        <p className="text-sm text-amber-700 mt-1">
          Download RRC proration data before uploading mineral holders.
        </p>
        <button
          onClick={handleDownloadRRC}
          className="mt-3 px-4 py-2 bg-amber-600 text-white rounded-lg"
        >
          Download RRC Data
        </button>
      </div>
    </div>
  </div>
)}

// Step 2: Show FileUpload only when ready
{rrcDataReady && (
  <FileUpload onFilesSelected={handleUpload} />
)}
```

### First-Time User Detection

```tsx
// Check if user has any job history
const [isFirstTimeUser, setIsFirstTimeUser] = useState(false)

useEffect(() => {
  const checkUserHistory = async () => {
    const response = await fetch(`${API_BASE}/history/jobs?limit=1`)
    const data = await response.json()
    setIsFirstTimeUser(data.count === 0)
  }
  checkUserHistory()
}, [])

// Show different UI for first-time users
{isFirstTimeUser ? (
  <FirstRunWelcome />
) : (
  <Dashboard />
)}
```

### Tool-Specific Contextual Help

```tsx
// Extract.tsx - Show inline help for flagged entries
<div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
  <div className="flex gap-2">
    <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />
    <div className="text-sm text-blue-900">
      <strong>What are flagged entries?</strong> Entries with incomplete addresses or ambiguous entity types are flagged for manual review.
      <Link to="/help#flagged-entries" className="text-blue-600 underline ml-1">
        Learn more
      </Link>
    </div>
  </div>
</div>
```

## See Also

- [activation-onboarding](references/activation-onboarding.md) - Checklist patterns, first-run banners, completion tracking
- [engagement-adoption](references/engagement-adoption.md) - Usage stats, feature discovery, retention patterns
- [in-app-guidance](references/in-app-guidance.md) - Tooltips, inline help, contextual documentation
- [product-analytics](references/product-analytics.md) - Event tracking, funnel analysis (not yet implemented)
- [roadmap-experiments](references/roadmap-experiments.md) - Feature flags, A/B tests (not yet implemented)
- [feedback-insights](references/feedback-insights.md) - Support patterns, user feedback collection

## Related Skills

- **react** - Component patterns, hooks, Context API for user state
- **typescript** - Type-safe props for onboarding components
- **tailwind** - Styling empty states, banners, CTAs with tre-* brand colors
- **frontend-design** - UI patterns for internal tools
- **firebase** - Auth state for first-time user detection
- **firestore** - Job history storage and retrieval