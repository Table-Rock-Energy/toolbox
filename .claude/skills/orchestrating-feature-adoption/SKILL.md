---
name: orchestrating-feature-adoption
description: |
  Plans feature discovery, nudges, and adoption flows for Table Rock Tools internal application.
  Use when: adding new tool capabilities, improving first-run experience, tracking tool usage, or guiding users to underutilized features
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Orchestrating-feature-adoption Skill

For Table Rock Tools, a B2B internal app with four document-processing tools (Extract, Title, Proration, Revenue). This skill addresses the unique challenges of driving adoption in **small internal teams** where you can't rely on mass onboarding flows or email campaigns—instead, you need lightweight in-app guidance and usage instrumentation.

## Quick Start

### Empty State → First Success

```tsx
// Dashboard.tsx - Turn empty state into actionable first step
{recentActivity.length === 0 ? (
  <div className="p-8 text-center">
    <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
    <p className="font-medium text-tre-navy mb-2">No activity yet</p>
    <p className="text-sm text-gray-500 mb-4">
      Get started by uploading your first document
    </p>
    <Link
      to="/extract"
      className="inline-flex items-center gap-2 px-4 py-2 bg-tre-teal text-tre-navy rounded-lg font-medium hover:bg-tre-teal/90"
    >
      Try Extract Tool <ArrowRight className="w-4 h-4" />
    </Link>
  </div>
) : (
  // Activity table
)}
```

### Usage Instrumentation (Backend)

```python
# firestore_service.py - Track tool usage events
async def track_tool_usage(
    user_email: str,
    tool: str,  # "extract" | "title" | "proration" | "revenue"
    action: str,  # "upload" | "export" | "view"
    metadata: dict | None = None
):
    """Log usage event for analytics and adoption tracking."""
    if not settings.firestore_enabled:
        return

    db = get_firestore_client()
    event = {
        "user_email": user_email,
        "tool": tool,
        "action": action,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
    }

    await db.collection("usage_events").add(event)
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Empty states | Convert "no data" into CTA | Dashboard activity feed → "Try Extract" button |
| Tool cards | Show usage stats to create social proof | `{tool.usageCount} times used` |
| Contextual help | Link to Help page from error states | Upload failure → "See troubleshooting guide" |
| Feature flags | Control rollout of new capabilities | `if (settings.enable_bulk_upload)` in backend config |
| Usage events | Track what users actually do | `track_tool_usage("james@...", "extract", "upload")` |

## Common Patterns

### Pattern: First-Run Checklist

**When:** User hasn't used any tools yet (all `usageCount === 0`)

```tsx
// Dashboard.tsx - Show checklist overlay for new users
const [showOnboarding, setShowOnboarding] = useState(false);

useEffect(() => {
  const hasUsedAnyTool = tools.some(t => t.usageCount > 0);
  const hasSeenOnboarding = localStorage.getItem('onboarding_complete');
  
  if (!hasUsedAnyTool && !hasSeenOnboarding) {
    setShowOnboarding(true);
  }
}, []);

// Modal with checklist:
// ☐ Upload your first OCC Exhibit A (Extract)
// ☐ Process a title opinion (Title)
// ☐ Calculate NRA with RRC data (Proration)
```

### Pattern: Usage Analytics Dashboard (Admin)

**When:** You need visibility into which tools are adopted

```python
# api/admin.py - Add analytics endpoint
@router.get("/analytics/tool-usage")
async def get_tool_usage_stats(
    days: int = Query(30, ge=1, le=90)
):
    """Get tool usage breakdown by user and tool."""
    from datetime import datetime, timedelta
    from app.services import firestore_service as db
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    events = await db.get_usage_events_since(cutoff)
    
    # Aggregate by tool
    stats = {}
    for event in events:
        tool = event["tool"]
        stats[tool] = stats.get(tool, 0) + 1
    
    return {
        "period_days": days,
        "total_events": len(events),
        "by_tool": stats,
        "unique_users": len(set(e["user_email"] for e in events)),
    }
```

### Pattern: Feature Announcement Banner

**When:** You ship a new capability and need to notify users

```tsx
// MainLayout.tsx - Dismissible banner at top
const [showBanner, setShowBanner] = useState(true);

useEffect(() => {
  const dismissed = localStorage.getItem('banner_rrc_auto_download_dismissed');
  if (dismissed) setShowBanner(false);
}, []);

const handleDismiss = () => {
  localStorage.setItem('banner_rrc_auto_download_dismissed', 'true');
  setShowBanner(false);
};

{showBanner && (
  <div className="bg-tre-teal/10 border-b border-tre-teal/20 px-4 py-2">
    <div className="flex items-center justify-between max-w-7xl mx-auto">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-tre-teal" />
        <p className="text-sm text-tre-navy">
          <strong>New:</strong> RRC data now auto-downloads monthly.{' '}
          <Link to="/proration" className="underline">Learn more</Link>
        </p>
      </div>
      <button onClick={handleDismiss} className="text-tre-teal hover:text-tre-navy">
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
)}
```

## See Also

- [activation-onboarding](references/activation-onboarding.md) - First-run flows, empty states, setup wizards
- [engagement-adoption](references/engagement-adoption.md) - Usage tracking, retention patterns, re-engagement
- [in-app-guidance](references/in-app-guidance.md) - Tooltips, tours, contextual help, progressive disclosure
- [product-analytics](references/product-analytics.md) - Event tracking, funnel analysis, usage dashboards
- [roadmap-experiments](references/roadmap-experiments.md) - Feature flags, A/B tests, gradual rollouts
- [feedback-insights](references/feedback-insights.md) - Support signals, feature requests, user interviews

## Related Skills

For UI implementation, see the **react**, **typescript**, **tailwind**, and **frontend-design** skills.
For backend instrumentation, see the **fastapi**, **pydantic**, **firestore**, and **python** skills.