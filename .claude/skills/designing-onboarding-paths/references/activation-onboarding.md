# Activation & Onboarding Reference

## Contents
- First-Run Experience Patterns
- Completion Checklists
- Welcome Banners & Dismissible Tips
- Account Setup Flows
- Anti-Patterns

---

## First-Run Experience Patterns

Table Rock Tools has **no traditional onboarding flow** because it's gated by Firebase Auth + allowlist. Once authorized, users land on the Dashboard and need to understand the 5 tools (Extract, Title, Proration, Revenue, GHL Prep).

### Current Dashboard Empty State (Needs Improvement)

```tsx
// frontend/src/pages/Dashboard.tsx:196-201 — actual code
{recentJobs.length === 0 ? (
  <div className="p-8 text-center text-gray-500">
    <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
    <p className="font-medium">No activity yet</p>
    <p className="text-sm mt-1">Tool usage will appear here</p>
  </div>
) : (
  <table className="w-full">...</table>
)}
```

**Problem:** No call-to-action. User knows activity will appear eventually but has no prompt for what to do right now.

### GOOD - First-Run Dashboard with CTA

```tsx
// Detect first-time user via job history
const [userStats, setUserStats] = useState({ totalJobs: 0, isLoading: true })

useEffect(() => {
  const fetchUserStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/history/jobs?limit=1`)
      const data = await response.json()
      setUserStats({ totalJobs: data.count, isLoading: false })
    } catch (err) {
      setUserStats({ totalJobs: 0, isLoading: false })
    }
  }
  fetchUserStats()
}, [])

// Show welcome for first-time users
{!userStats.isLoading && userStats.totalJobs === 0 && (
  <div className="bg-gradient-to-r from-tre-navy to-tre-brown-dark rounded-xl p-8 text-white mb-8">
    <h2 className="text-2xl font-oswald font-semibold mb-2">
      Welcome to Table Rock Tools
    </h2>
    <p className="text-tre-tan mb-6">
      Process OCC documents, title opinions, proration calculations, and revenue statements in one place.
    </p>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
      <Link
        to="/extract"
        className="px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg text-center transition-colors border border-white/20"
      >
        <FileSearch className="w-6 h-6 mx-auto mb-1" />
        <span className="text-sm">Try Extract</span>
      </Link>
      <Link to="/title" className="px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg text-center transition-colors border border-white/20">
        <FileText className="w-6 h-6 mx-auto mb-1" />
        <span className="text-sm">Try Title</span>
      </Link>
      <Link to="/proration" className="px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg text-center transition-colors border border-white/20">
        <Calculator className="w-6 h-6 mx-auto mb-1" />
        <span className="text-sm">Try Proration</span>
      </Link>
      <Link to="/help" className="px-4 py-3 bg-tre-teal hover:bg-tre-teal/90 rounded-lg text-center transition-colors text-tre-navy font-medium">
        <HelpCircle className="w-6 h-6 mx-auto mb-1" />
        <span className="text-sm">View Help</span>
      </Link>
    </div>
  </div>
)}
```

---

## Completion Checklists

Checklists work well for **multi-step setup flows** or **tool prerequisites**.

### Example: Proration Tool Checklist

Proration requires RRC data download before processing mineral holders. Show a checklist:

```tsx
interface ChecklistItem {
  id: string
  label: string
  completed: boolean
  action?: () => void
}

const [checklist, setChecklist] = useState<ChecklistItem[]>([
  { id: 'rrc-download', label: 'Download RRC proration data', completed: false },
  { id: 'upload-csv', label: 'Upload mineral holders CSV', completed: false },
  { id: 'review-results', label: 'Review NRA calculations', completed: false },
])

// Proration.tsx
<div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
  <h3 className="font-oswald font-semibold text-lg mb-4">Getting Started</h3>
  <div className="space-y-3">
    {checklist.map((item) => (
      <div key={item.id} className="flex items-center gap-3">
        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
          item.completed
            ? 'bg-green-500 border-green-500'
            : 'border-gray-300'
        }`}>
          {item.completed && <Check className="w-3 h-3 text-white" />}
        </div>
        <span className={item.completed ? 'text-gray-400 line-through' : 'text-gray-900'}>
          {item.label}
        </span>
        {!item.completed && item.action && (
          <button
            onClick={item.action}
            className="ml-auto text-sm text-tre-teal hover:underline"
          >
            Start
          </button>
        )}
      </div>
    ))}
  </div>
</div>
```

**When to update checklist:**
- After RRC data download completes: `setChecklist(prev => prev.map(item => item.id === 'rrc-download' ? {...item, completed: true} : item))`
- After CSV upload: `setChecklist(prev => prev.map(item => item.id === 'upload-csv' ? {...item, completed: true} : item))`

---

## Welcome Banners & Dismissible Tips

Use **localStorage** to persist dismissal state across sessions.

### Dismissible Tip Pattern

```tsx
const [showTip, setShowTip] = useState(() => {
  const dismissed = localStorage.getItem('extract-tip-dismissed')
  return dismissed !== 'true'
})

const dismissTip = () => {
  localStorage.setItem('extract-tip-dismissed', 'true')
  setShowTip(false)
}

// Extract.tsx - Show tip on first visit
{showTip && (
  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
    <div className="flex items-start gap-3">
      <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="font-medium text-blue-900">Pro Tip: Review Flagged Entries</p>
        <p className="text-sm text-blue-700 mt-1">
          Entries with incomplete addresses are flagged for manual review. Click the flag icon to add notes.
        </p>
      </div>
      <button
        onClick={dismissTip}
        className="text-blue-400 hover:text-blue-600"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
)}
```

### Feature Announcement Banner

```tsx
// Show new feature announcement
const [showAnnouncement, setShowAnnouncement] = useState(() => {
  const dismissed = localStorage.getItem('announcement-revenue-v2-dismissed')
  return dismissed !== 'true'
})

{showAnnouncement && (
  <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-xl p-4 mb-6">
    <div className="flex items-start gap-3">
      <Sparkles className="w-5 h-5 flex-shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">New: Energy Transfer Statement Support</p>
        <p className="text-sm text-white/90 mt-1">
          The Revenue tool now supports Energy Transfer PDF statements in addition to EnergyLink.
        </p>
      </div>
      <button
        onClick={() => {
          localStorage.setItem('announcement-revenue-v2-dismissed', 'true')
          setShowAnnouncement(false)
        }}
        className="text-white/80 hover:text-white"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
)}
```

---

## Account Setup Flows

Table Rock Tools uses **Firebase Auth with allowlist** (backend/app/core/auth.py). No traditional account setup flow exists.

### Unauthorized User Flow (Already Implemented)

```tsx
// toolbox/frontend/src/pages/Login.tsx:60-68
{authError && (
  <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg">
    <p className="text-red-300 text-sm">{authError}</p>
    <p className="text-red-400 text-xs mt-2">
      Signed in as: {user?.email}
    </p>
  </div>
)}
```

**This is GOOD** - Shows clear error message with contact info (james@tablerocktx.com).

### Post-Authorization Welcome (Missing)

After a user is added to allowlist and logs in for the first time, show a welcome modal:

```tsx
// Add to AuthContext or App.tsx
const [showWelcomeModal, setShowWelcomeModal] = useState(() => {
  const hasSeenWelcome = localStorage.getItem('has-seen-welcome')
  return !hasSeenWelcome && user && isAuthorized
})

useEffect(() => {
  if (showWelcomeModal && user && isAuthorized) {
    localStorage.setItem('has-seen-welcome', 'true')
  }
}, [showWelcomeModal, user, isAuthorized])

// Modal component
{showWelcomeModal && (
  <Modal onClose={() => setShowWelcomeModal(false)}>
    <div className="text-center">
      <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
      <h2 className="text-2xl font-oswald font-semibold text-tre-navy mb-2">
        Welcome to Table Rock Tools!
      </h2>
      <p className="text-gray-600 mb-6">
        You now have access to all four document processing tools. Start by uploading a file to any tool.
      </p>
      <button
        onClick={() => setShowWelcomeModal(false)}
        className="px-6 py-3 bg-tre-teal text-white rounded-lg font-medium hover:bg-tre-teal/90"
      >
        Get Started
      </button>
    </div>
  </Modal>
)}
```

---

## Anti-Patterns

### WARNING: Modal Onboarding Tours

**The Problem:**

```tsx
// BAD - Multi-step modal tour blocking the UI
{showTour && (
  <Modal>
    <div>
      <h3>Step {tourStep} of 5</h3>
      <p>Click here to upload a file...</p>
      <button onClick={() => setTourStep(tourStep + 1)}>Next</button>
    </div>
  </Modal>
)}
```

**Why This Breaks:**
1. **Blocks UI** - User can't explore naturally
2. **High abandonment** - Users skip tours to get to actual work
3. **Not contextual** - Generic tour doesn't match user's current goal

**The Fix:**

Use **inline, contextual help** that appears when relevant:

```tsx
// GOOD - Contextual tip on first upload attempt
{uploadAttempts === 0 && (
  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
    <p className="text-sm text-yellow-800">
      <strong>Tip:</strong> For best results, upload PDF files. Multiple files can be processed at once.
    </p>
  </div>
)}
```

**When You Might Be Tempted:**
When you want to show users "everything the tool can do" on first login. Resist. Show help **when users need it**, not before.

### WARNING: Forcing User Profiles Before Tool Access

**The Problem:**

```tsx
// BAD - Force profile completion before allowing tool access
if (!user.phone || !user.department) {
  return <ProfileSetupForm onComplete={() => setProfileComplete(true)} />
}
```

**Why This Breaks:**
1. **Friction** - Delays time-to-value for internal tools
2. **Unnecessary** - Profile data often not critical for core workflows
3. **Abandonment risk** - Users close tab instead of filling forms

**The Fix:**

Use **optional profile completion** with benefits:

```tsx
// GOOD - Optional profile link in Settings
<div className="bg-white rounded-xl border border-gray-200 p-6">
  <h3 className="font-semibold mb-2">Complete Your Profile</h3>
  <p className="text-sm text-gray-600 mb-4">
    Add your department and phone number to enable team collaboration features.
  </p>
  <Link to="/settings/profile" className="text-tre-teal hover:underline">
    Update Profile
  </Link>
</div>
```

**When You Might Be Tempted:**
When legal or compliance requires certain data. In that case, collect it during Firebase Auth sign-up, not post-login.

### WARNING: Auto-Playing Videos

**The Problem:**

```tsx
// BAD - Auto-play video on Dashboard
<video autoPlay muted loop>
  <source src="/tutorial.mp4" />
</video>
```

**Why This Breaks:**
1. **Bandwidth** - Large video files slow page load
2. **Distraction** - Motion draws attention away from task
3. **Accessibility** - Auto-play violates WCAG guidelines

**The Fix:**

```tsx
// GOOD - Optional video link
<a href="/help#video-tutorials" className="flex items-center gap-2 text-tre-teal">
  <Play className="w-4 h-4" />
  Watch Tutorial (2 min)
</a>