# Engagement & Adoption Reference

## Contents
- Usage Stats Display
- Feature Discovery Patterns
- Retention & Re-Engagement
- Tool Switching Patterns
- Anti-Patterns

---

## Usage Stats Display

Dashboard tool cards already show **dynamic usage counts** — fetched from `/api/history/jobs?limit=50` and aggregated per-tool on the frontend (`Dashboard.tsx:104-123`). The `toolCounts` state holds counts keyed by tool name, displayed as `{toolCounts[tool.tool] || 0}` on each card.

### Current Pattern (Already Working)

```tsx
// frontend/src/pages/Dashboard.tsx:104-123 — already implemented
useEffect(() => {
  const fetchJobs = async () => {
    const response = await fetch(`${API_BASE}/history/jobs?limit=50`)
    const data = await response.json()
    const jobs: RecentJob[] = data.jobs || []
    const counts: Record<string, number> = {}
    for (const job of jobs) {
      counts[job.tool] = (counts[job.tool] || 0) + 1
    }
    setToolCounts(counts)
  }
  fetchJobs()
}, [])
```

### Enhancement - Separate Personal vs Team Stats

```tsx
// Fetch tool usage stats on mount
const [toolStats, setToolStats] = useState<Record<string, number>>({
  extract: 0,
  title: 0,
  proration: 0,
  revenue: 0,
})

useEffect(() => {
  const fetchToolStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/history/jobs?limit=1000`)
      const data = await response.json()
      
      const counts = data.jobs.reduce((acc, job) => {
        acc[job.tool] = (acc[job.tool] || 0) + 1
        return acc
      }, {} as Record<string, number>)
      
      setToolStats(counts)
    } catch (err) {
      console.error('Failed to fetch tool stats:', err)
    }
  }
  fetchToolStats()
}, [])

// Update tool cards
const tools = [
  {
    name: 'Extract',
    description: 'Extract party and stakeholder data from OCC Exhibit A PDFs',
    icon: FileSearch,
    path: '/extract',
    color: 'bg-blue-500',
    usageCount: toolStats.extract || 0,
  },
  // ... other tools with dynamic counts
]
```

### Personal vs Team Stats

Show **personal usage** vs **team-wide usage** to encourage engagement:

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
  <div className="bg-white rounded-xl border border-gray-200 p-6">
    <p className="text-sm text-gray-500 mb-1">Your Jobs This Month</p>
    <p className="text-3xl font-oswald font-semibold text-tre-navy">{userJobCount}</p>
    <p className="text-sm text-green-600 mt-2 flex items-center gap-1">
      <TrendingUp className="w-4 h-4" />
      +12% from last month
    </p>
  </div>
  <div className="bg-white rounded-xl border border-gray-200 p-6">
    <p className="text-sm text-gray-500 mb-1">Team Jobs This Month</p>
    <p className="text-3xl font-oswald font-semibold text-tre-navy">{teamJobCount}</p>
    <p className="text-sm text-gray-600 mt-2">Across {teamMemberCount} users</p>
  </div>
</div>
```

**Backend addition needed:**

```python
# toolbox/backend/app/api/history.py
@router.get("/stats/monthly")
async def get_monthly_stats(user_email: str = None):
    """Get job stats for current month, optionally filtered by user."""
    from datetime import datetime, timedelta
    
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    query = {"created_at": {"$gte": start_of_month}}
    if user_email:
        query["user_email"] = user_email
    
    jobs = await db.get_jobs(query=query)
    
    return {
        "month": start_of_month.strftime("%B %Y"),
        "total_jobs": len(jobs),
        "by_tool": {
            "extract": sum(1 for j in jobs if j["tool"] == "extract"),
            "title": sum(1 for j in jobs if j["tool"] == "title"),
            "proration": sum(1 for j in jobs if j["tool"] == "proration"),
            "revenue": sum(1 for j in jobs if j["tool"] == "revenue"),
        }
    }
```

---

## Feature Discovery Patterns

### New Feature Badge

```tsx
// Add "New" badge to recently added features
<Link to="/revenue" className="relative group bg-white rounded-xl border...">
  {/* Badge for new features */}
  <span className="absolute -top-2 -right-2 px-2 py-1 bg-amber-500 text-white text-xs font-semibold rounded-full">
    New
  </span>
  <div className="flex items-start justify-between mb-4">
    <div className={`w-12 h-12 bg-amber-500 rounded-xl flex items-center justify-center`}>
      <DollarSign className="w-6 h-6 text-white" />
    </div>
    <div className="text-right">
      <p className="text-2xl font-oswald font-semibold text-tre-navy">0</p>
      <p className="text-xs text-gray-400">times used</p>
    </div>
  </div>
  <h3 className="font-oswald font-semibold text-tre-navy text-lg mb-1">
    Revenue
  </h3>
  <p className="text-sm text-gray-500 mb-4">
    Extract revenue statements from EnergyLink and Energy Transfer PDFs
  </p>
</Link>
```

**Persist badge dismissal:**

```tsx
const [newFeatures, setNewFeatures] = useState(() => {
  const seen = localStorage.getItem('seen-features')
  const seenSet = new Set(seen ? JSON.parse(seen) : [])
  return {
    revenue: !seenSet.has('revenue-tool'),
  }
})

// On tool page visit, mark as seen
useEffect(() => {
  const seen = JSON.parse(localStorage.getItem('seen-features') || '[]')
  if (!seen.includes('revenue-tool')) {
    localStorage.setItem('seen-features', JSON.stringify([...seen, 'revenue-tool']))
  }
}, [])
```

### Progressive Disclosure for Advanced Features

Don't show all features at once. Reveal advanced options after basic usage.

```tsx
// Extract.tsx - Show advanced filters after first upload
{jobs.length > 0 && (
  <details className="bg-gray-50 rounded-lg p-4 mb-4">
    <summary className="cursor-pointer font-medium text-gray-700 flex items-center gap-2">
      <Filter className="w-4 h-4" />
      Advanced Filters
    </summary>
    <div className="mt-4 space-y-3">
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={showIndividualsOnly}
          onChange={(e) => setShowIndividualsOnly(e.target.checked)}
        />
        <span className="text-sm">Show Individuals Only</span>
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={hideFlagged}
          onChange={(e) => setHideFlagged(e.target.checked)}
        />
        <span className="text-sm">Hide Flagged Entries</span>
      </label>
    </div>
  </details>
)}
```

---

## Retention & Re-Engagement

### Recent Files Shortcut

```tsx
// Dashboard - Show quick access to recent jobs
<div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
  <h3 className="font-oswald font-semibold text-lg mb-4">Recent Files</h3>
  <div className="space-y-2">
    {recentJobs.slice(0, 5).map((job) => (
      <button
        key={job.id}
        onClick={() => navigate(`/${job.tool}?job_id=${job.id}`)}
        className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 rounded-lg transition-colors text-left"
      >
        <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
          <File className="w-5 h-5 text-gray-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {job.metadata?.filename || 'Unknown'}
          </p>
          <p className="text-xs text-gray-500">
            {job.tool} • {new Date(job.created_at).toLocaleDateString()}
          </p>
        </div>
        <ArrowRight className="w-4 h-4 text-gray-400" />
      </button>
    ))}
  </div>
</div>
```

### Email Digest (Backend)

Send weekly summary email to active users:

```python
# toolbox/backend/app/services/email_service.py
from datetime import datetime, timedelta

async def send_weekly_digest(user_email: str):
    """Send weekly activity summary to user."""
    week_ago = datetime.now() - timedelta(days=7)
    
    jobs = await db.get_jobs(query={
        "user_email": user_email,
        "created_at": {"$gte": week_ago}
    })
    
    if len(jobs) == 0:
        return  # Don't send if no activity
    
    email_body = f"""
    <h2>Your Table Rock Tools Summary</h2>
    <p>You processed {len(jobs)} jobs this week:</p>
    <ul>
      <li>Extract: {sum(1 for j in jobs if j['tool'] == 'extract')}</li>
      <li>Title: {sum(1 for j in jobs if j['tool'] == 'title')}</li>
      <li>Proration: {sum(1 for j in jobs if j['tool'] == 'proration')}</li>
      <li>Revenue: {sum(1 for j in jobs if j['tool'] == 'revenue')}</li>
    </ul>
    <a href="https://tools.tablerocktx.com">Continue working →</a>
    """
    
    await send_email(to=user_email, subject="Your Weekly Summary", html=email_body)
```

---

## Tool Switching Patterns

### Cross-Tool Suggestions

After completing a job in one tool, suggest related tools:

```tsx
// Extract.tsx - After successful extraction
{activeJob?.result?.success && (
  <div className="bg-green-50 border border-green-200 rounded-xl p-4 mt-6">
    <div className="flex items-start gap-3">
      <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
      <div className="flex-1">
        <p className="font-medium text-green-900">Extraction Complete</p>
        <p className="text-sm text-green-700 mt-1">
          Next: Create a title opinion from this data?
        </p>
        <Link
          to="/title"
          className="mt-3 inline-flex items-center gap-1 text-sm text-green-700 hover:text-green-900 font-medium"
        >
          Open Title Tool
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  </div>
)}
```

### Breadcrumb Navigation

```tsx
// Show context when viewing job details
<div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
  <Link to="/" className="hover:text-tre-teal">Dashboard</Link>
  <ChevronRight className="w-4 h-4" />
  <Link to="/extract" className="hover:text-tre-teal">Extract</Link>
  <ChevronRight className="w-4 h-4" />
  <span className="text-gray-900">{activeJob?.documentName}</span>
</div>
```

---

## Anti-Patterns

### WARNING: Gamification in Internal Tools

**The Problem:**

```tsx
// BAD - Points/badges for internal work tool
<div className="flex items-center gap-2">
  <Trophy className="w-5 h-5 text-yellow-500" />
  <span>You earned 50 points! Level up to Bronze tier.</span>
</div>
```

**Why This Breaks:**
1. **Patronizing** - Internal users are professionals, not game players
2. **Meaningless** - Points don't reflect actual productivity or quality
3. **Distracting** - Shifts focus from work outcomes to arbitrary metrics

**The Fix:**

Use **real productivity metrics** instead:

```tsx
// GOOD - Actual work metrics
<div className="bg-white rounded-xl border border-gray-200 p-6">
  <h3 className="font-semibold mb-4">This Month</h3>
  <div className="space-y-3">
    <div className="flex justify-between">
      <span className="text-gray-600">Documents Processed</span>
      <span className="font-semibold text-tre-navy">{monthlyJobCount}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-600">Avg. Processing Time</span>
      <span className="font-semibold text-tre-navy">2.3 min</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-600">Success Rate</span>
      <span className="font-semibold text-green-600">98.5%</span>
    </div>
  </div>
</div>
```

**When You Might Be Tempted:**
When trying to "motivate" users to adopt new features. Internal users adopt features when they solve real problems, not when they earn badges.

### WARNING: Infinite Scroll for Job History

**The Problem:**

```tsx
// BAD - Infinite scroll on Dashboard
<InfiniteScroll
  dataLength={jobs.length}
  next={loadMoreJobs}
  hasMore={true}
  loader={<LoadingSpinner />}
>
  {jobs.map(job => <JobCard key={job.id} job={job} />)}
</InfiniteScroll>
```

**Why This Breaks:**
1. **No end state** - Users can't tell how much history exists
2. **Performance** - DOM grows unbounded
3. **Lost position** - Can't easily return to specific jobs

**The Fix:**

```tsx
// GOOD - Paginated job history
<div>
  <div className="space-y-3">
    {jobs.slice(page * pageSize, (page + 1) * pageSize).map(job => (
      <JobCard key={job.id} job={job} />
    ))}
  </div>
  <div className="flex items-center justify-between mt-6">
    <p className="text-sm text-gray-600">
      Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, totalJobs)} of {totalJobs}
    </p>
    <div className="flex gap-2">
      <button
        onClick={() => setPage(page - 1)}
        disabled={page === 0}
        className="px-4 py-2 border rounded-lg disabled:opacity-50"
      >
        Previous
      </button>
      <button
        onClick={() => setPage(page + 1)}
        disabled={(page + 1) * pageSize >= totalJobs}
        className="px-4 py-2 border rounded-lg disabled:opacity-50"
      >
        Next
      </button>
    </div>
  </div>
</div>