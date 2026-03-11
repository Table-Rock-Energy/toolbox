# In-App Guidance Reference

## Contents
- Tooltip Tracking
- Contextual Onboarding
- Feature Announcement Tracking
- Help Page Usage

---

## WARNING: No In-App Guidance Exists

Table Rock Tools has **zero in-app guidance**:
- No tooltips
- No feature announcements
- No contextual help banners
- No progress indicators for multi-step workflows

The only help is a `/help` page with static FAQs. Every guidance element below must be built from scratch.

---

## Tooltip Tracking

### TrackedTooltip Component

```typescript
// frontend/src/components/TrackedTooltip.tsx
import { useRef } from 'react'
import { useAnalytics } from '../hooks/useAnalytics'

interface TrackedTooltipProps {
  content: string
  children: React.ReactNode
  trackingId: string
}

export function TrackedTooltip({ content, children, trackingId }: TrackedTooltipProps) {
  const hasTracked = useRef(false)
  const { track } = useAnalytics()

  const handleShow = () => {
    if (!hasTracked.current) {
      track('tooltip_viewed', { tooltip_id: trackingId })
      hasTracked.current = true
    }
  }

  return (
    <div onMouseEnter={handleShow} className="relative group inline-block">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block
                      bg-gray-900 text-white text-xs p-2 rounded whitespace-nowrap z-10">
        {content}
      </div>
    </div>
  )
}
```

### Use on Prerequisite-Gated Elements

```typescript
// frontend/src/pages/Proration.tsx
// Wrap the disabled Calculate button to explain WHY it's disabled
<TrackedTooltip
  content="RRC lease data is required for NRA calculations. Download it above."
  trackingId="proration_rrc_requirement"
>
  <button
    disabled={!hasRRCData}
    className="disabled:opacity-50 disabled:cursor-not-allowed"
  >
    Calculate NRA
  </button>
</TrackedTooltip>
```

**WHY:** High `tooltip_viewed` counts on `proration_rrc_requirement` → users are confused by the disabled state. Threshold: >5 views per user = improve the empty state instead.

---

## Contextual Onboarding

### Progressive Disclosure After Extraction

Show tips AFTER users have context to understand their value:

```typescript
// frontend/src/pages/Extract.tsx
const [showFilterTip, setShowFilterTip] = useState(false)
const { track } = useAnalytics()

useEffect(() => {
  // Only surface filter tip when results are large enough to benefit
  if (entries.length > 20 && !showFilterTip) {
    track('filter_tip_triggered', { entry_count: entries.length, tool: 'extract' })
    setShowFilterTip(true)
  }
}, [entries.length])

{showFilterTip && (
  <div className="bg-tre-teal/10 border-l-4 border-tre-teal p-3 mb-4 flex justify-between">
    <p className="text-sm text-gray-700">
      Tip: Use filters above to narrow down your {entries.length} entries by entity type.
    </p>
    <button
      onClick={() => {
        track('filter_tip_dismissed', { tool: 'extract' })
        setShowFilterTip(false)
      }}
      className="text-xs text-gray-500 ml-4"
    >
      Got it
    </button>
  </div>
)}
```

**DON'T** show guidance tips on empty state — users need context (actual entries) to understand why the tip is useful.

---

## Feature Announcement Tracking

### Announcement Modal

```typescript
// frontend/src/components/FeatureAnnouncement.tsx
import { useEffect, useRef, useState } from 'react'
import { useAnalytics } from '../hooks/useAnalytics'
import { Modal } from './Modal'

interface Props {
  featureId: string
  title: string
  description: string
  ctaLabel: string
  onCTA: () => void
}

export function FeatureAnnouncement({ featureId, title, description, ctaLabel, onCTA }: Props) {
  const { track } = useAnalytics()
  const shownAt = useRef(Date.now())
  const isDismissed = localStorage.getItem(`feature_${featureId}_dismissed`) === 'true'
  const isShownThisSession = sessionStorage.getItem(`feature_${featureId}_shown`) === 'true'
  const [visible, setVisible] = useState(!isDismissed && !isShownThisSession)

  useEffect(() => {
    if (visible) {
      sessionStorage.setItem(`feature_${featureId}_shown`, 'true')
      track('feature_announcement_shown', { feature_id: featureId })
    }
  }, [])

  const handleDismiss = () => {
    track('feature_announcement_dismissed', {
      feature_id: featureId,
      time_to_dismiss_seconds: Math.floor((Date.now() - shownAt.current) / 1000),
    })
    localStorage.setItem(`feature_${featureId}_dismissed`, 'true')
    setVisible(false)
  }

  const handleCTA = () => {
    track('feature_announcement_cta_clicked', { feature_id: featureId })
    onCTA()
    handleDismiss()
  }

  if (!visible) return null

  return (
    <Modal onClose={handleDismiss}>
      <h2 className="font-oswald text-xl mb-2">{title}</h2>
      <p className="text-gray-600 mb-4">{description}</p>
      <div className="flex gap-2">
        <button onClick={handleCTA} className="bg-tre-teal text-white px-4 py-2 rounded">
          {ctaLabel}
        </button>
        <button onClick={handleDismiss} className="text-gray-500">
          Dismiss
        </button>
      </div>
    </Modal>
  )
}
```

**DO:** Show once per session (`sessionStorage`) — dismissed forever in `localStorage`.
**DON'T:** Show on every page load. Repeated announcements train users to dismiss without reading.

---

## Help Page Usage Tracking

Track FAQ expansion to identify which topics need in-context help:

```typescript
// frontend/src/pages/Help.tsx
const faqs = [
  { id: 'proration_rrc_data', question: 'How do I download RRC data?', answer: '...' },
  { id: 'extract_pdf_format', question: 'What PDF format is supported?', answer: '...' },
]

const [expanded, setExpanded] = useState<string | null>(null)

const handleToggle = (faqId: string) => {
  const isExpanding = expanded !== faqId

  if (isExpanding) {
    track('faq_expanded', {
      faq_id: faqId,
      // Infer referrer tool from document.referrer
      source_tool: document.referrer.match(/\/(extract|title|proration|revenue|ghl-prep)/)?.[1] ?? 'unknown',
    })
  }

  setExpanded(isExpanding ? faqId : null)
}
```

**Action rule:** If `faq_expanded[faq_id='proration_rrc_data']` exceeds 10 views, add an inline explanation directly to the Proration page instead of relying on users navigating to Help.

See the **react** skill for Modal usage patterns and the **frontend-design** skill for Tailwind styling conventions.
