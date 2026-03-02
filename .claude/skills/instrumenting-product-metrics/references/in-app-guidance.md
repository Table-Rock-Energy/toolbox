# In-App Guidance Reference

## Contents
- Tooltip Tracking
- Help Modal Instrumentation
- Feature Announcement Metrics
- Contextual Onboarding

---

## WARNING: No In-App Guidance Exists

Table Rock Tools has **ZERO in-app guidance**:
- No tooltips
- No feature announcements
- No contextual help
- No progress indicators for multi-step workflows

The only help is a `/help` page with static FAQs.

---

## Adding Tooltip Tracking

### Create Tracked Tooltip Component

```typescript
// frontend/src/components/TrackedTooltip.tsx
import { useState } from 'react'
import { useAnalytics } from '../hooks/useAnalytics'

interface TrackedTooltipProps {
  content: string
  children: React.ReactNode
  trackingId: string
}

export function TrackedTooltip({ content, children, trackingId }: TrackedTooltipProps) {
  const [hasShown, setHasShown] = useState(false)
  const { track } = useAnalytics()
  
  const handleShow = () => {
    if (!hasShown) {
      track('tooltip_viewed', {
        tooltip_id: trackingId,
        content_preview: content.slice(0, 50),
      })
      setHasShown(true)
    }
  }
  
  return (
    <div onMouseEnter={handleShow} className="relative group">
      {children}
      <div className="absolute hidden group-hover:block bg-gray-900 text-white text-xs p-2 rounded">
        {content}
      </div>
    </div>
  )
}
```

### Use in Complex UI Elements

```typescript
// frontend/src/pages/Proration.tsx
<TrackedTooltip 
  content="RRC lease data is required for NRA calculations"
  trackingId="proration_rrc_requirement"
>
  <button disabled={!hasRRCData}>Calculate NRA</button>
</TrackedTooltip>
```

**WHY:** Tooltip views indicate feature confusion. High view counts = poor UX clarity.

---

## Feature Announcement Tracking

### Modal for New Features

```typescript
// frontend/src/components/FeatureAnnouncement.tsx
export function FeatureAnnouncement({ featureId, title, description }: Props) {
  const { track } = useAnalytics()
  const [dismissed, setDismissed] = useState(
    localStorage.getItem(`feature_${featureId}_dismissed`) === 'true'
  )
  
  useEffect(() => {
    if (!dismissed) {
      track('feature_announcement_shown', { feature_id: featureId })
    }
  }, [dismissed, featureId])
  
  const handleDismiss = () => {
    track('feature_announcement_dismissed', { 
      feature_id: featureId,
      time_to_dismiss_seconds: (Date.now() - shownAt) / 1000,
    })
    localStorage.setItem(`feature_${featureId}_dismissed`, 'true')
    setDismissed(true)
  }
  
  const handleCTA = () => {
    track('feature_announcement_cta_clicked', { feature_id: featureId })
    // Navigate to feature
  }
  
  if (dismissed) return null
  
  return <Modal onClose={handleDismiss}>...</Modal>
}
```

**DO/DON'T:**

**BAD - Show on every page load:**
```typescript
if (!dismissed) {
  return <FeatureAnnouncement />
}
```

**GOOD - Show once per session:**
```typescript
const shownThisSession = sessionStorage.getItem(`feature_${featureId}_shown`)
if (!dismissed && !shownThisSession) {
  sessionStorage.setItem(`feature_${featureId}_shown`, 'true')
  return <FeatureAnnouncement />
}
```

**WHY:** Repeated announcements train users to dismiss without reading.

---

## Contextual Onboarding

### Progressive Disclosure for Extract Tool

```typescript
// Show filter explanation AFTER first successful extraction
const [hasExtracted, setHasExtracted] = useState(false)
const [showFilterTip, setShowFilterTip] = useState(false)

useEffect(() => {
  if (hasExtracted && !showFilterTip && entries.length > 20) {
    track('filter_tip_triggered', { entry_count: entries.length })
    setShowFilterTip(true)
  }
}, [hasExtracted, entries.length])

{showFilterTip && (
  <div className="bg-blue-50 border-l-4 border-blue-500 p-4">
    <p className="text-sm">
      Tip: Use filters to narrow down {entries.length} entries
    </p>
    <button onClick={() => {
      track('filter_tip_dismissed')
      setShowFilterTip(false)
    }}>Got it</button>
  </div>
)}
```

**WHY:** Show tips AFTER users have context (extracted entries) to understand value.

---

## Help Page Usage Tracking

### Track FAQ Views

```typescript
// frontend/src/pages/Help.tsx
const faqs = [
  { id: 'extract_pdf_format', question: 'What PDF format is supported?', answer: '...' },
  { id: 'proration_rrc_data', question: 'How do I download RRC data?', answer: '...' },
]

const [expandedFAQ, setExpandedFAQ] = useState<string | null>(null)

const handleFAQClick = (faqId: string) => {
  const isExpanding = expandedFAQ !== faqId
  
  if (isExpanding) {
    track('faq_expanded', { 
      faq_id: faqId,
      source_page: document.referrer.includes('/extract') ? 'extract' : 'unknown',
    })
  }
  
  setExpandedFAQ(isExpanding ? faqId : null)
}
```

**WHY:** High FAQ view counts indicate missing in-context help.

**Action:** If `faq_expanded[faq_id='proration_rrc_data']` > 100 views, add tooltip to Proration page.