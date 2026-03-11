---
phase: 13-production-hardening
plan: 02
subsystem: ghl-frontend-hardening
tags: [daily-limit-ui, multi-owner-ui, credential-validation, sse-reconnection]
dependency_graph:
  requires: [13-01]
  provides: [daily-limit-display, multi-owner-selection-ui, credential-quick-check-ui, sse-auto-reconnect]
  affects: [ghl-send-modal, ghl-prep-page, sse-progress-hook]
tech_stack:
  added: [sse-reconnection-backoff]
  patterns: [visual-escalation, credential-preflight, multi-select-checkboxes, inline-banner-warnings]
key_files:
  created: []
  modified:
    - toolbox/frontend/src/utils/api.ts
    - toolbox/frontend/src/hooks/useSSEProgress.ts
    - toolbox/frontend/src/components/GhlSendModal.tsx
    - toolbox/frontend/src/pages/GhlPrep.tsx
decisions:
  - decision: "SSE reconnection with exponential backoff (5 attempts max)"
    rationale: "Balance between user convenience and server load — auto-recover from transient network issues"
    alternatives: ["No reconnection (manual refresh)", "Unlimited reconnection attempts"]
    trade_offs: "After 5 failed attempts user must refresh, but prevents infinite retry loops"
  - decision: "Multi-owner selection via checkboxes (max 2) instead of dropdown"
    rationale: "Clear visual indication of multi-select capability and even-split behavior"
    alternatives: ["Dropdown with multi-select", "Two separate owner dropdowns"]
    trade_offs: "Takes more vertical space but more intuitive for users unfamiliar with multi-select dropdowns"
  - decision: "Daily capacity info line below Send button (not in modal)"
    rationale: "User sees capacity before opening modal — prevents wasted clicks on full quota"
    alternatives: ["Only show in modal", "Toast notification"]
    trade_offs: "Always visible adds UI noise, but critical info for power users"
metrics:
  duration: 318
  completed_date: "2026-02-27"
  tasks_completed: 2
  files_modified: 4
  commits: 2
---

# Phase 13 Plan 02: Frontend Production Hardening Summary

**One-liner:** Daily rate limit display with visual escalation, multi-owner contact assignment UI (even split), credential validation on modal open, daily limit hit banner in progress view, and SSE auto-reconnection with exponential backoff.

## What Was Built

### SSE Reconnection with Exponential Backoff
- Added `reconnectAttemptRef` and `reconnectTimeoutRef` to `useSSEProgress` hook
- Implements exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 30s)
- Max 5 reconnection attempts before showing "Connection lost. Refresh to check progress."
- Resets reconnect counter on successful `progress` or `complete` event
- Cleanup on unmount clears both EventSource and reconnect timeout

### Daily Limit Hit Detection
- Added `dailyLimitHit?: boolean` to `CompletionData` interface
- Detects `status === 'daily_limit_hit'` in progress events
- Sets completion data immediately when daily limit is hit (treats as early completion)
- Yellow inline banner in sending/summary steps with clear messaging:
  - "{processed} of {total} contacts sent. Remaining contacts can be sent after midnight UTC."
- Button text changes to "View Remaining Contacts" (rate-limited contacts are in failed_contacts with rate_limit category)

### Multi-Owner Selection UI
- **Replaced single owner dropdown** with checkbox list (max 2 selections)
- Shows "1 owner selected" or "2 owners selected (even split)" in label
- When 2 owners selected: "Contacts will be split evenly between selected owners" info text
- Checkboxes disabled when 2 are already selected (prevents selecting more)
- Hover highlight on each user row for better UX
- Updates buildRequest to use `assigned_to_list` instead of `assigned_to`
- Confirmation step shows owner names with "(even split)" suffix when 2 selected

### Credential Quick-Check on Modal Open
- New `credentialError` state for validation errors
- useEffect runs `quickCheckConnection(selectedConnectionId)` when modal opens in idle step
- Red alert banner at top of modal:
  - Title: "GHL connection expired"
  - Error message from backend
  - Link: "Go to Settings to reconnect" (navigates to /settings)
- Validate & Send button disabled when `credentialError` is set
- Error cleared when connection selection changes

### Daily Capacity Display
- **DailyRateLimitInfo** interface added to api.ts (daily_limit, requests_today, remaining, resets_at, warning_level)
- **getDailyLimit()** API method added
- State management: `dailyLimit` fetched on mount and after send completes
- Info line positioned below "Send to GHL" button:
  - Text: "Daily capacity: {remaining.toLocaleString()} remaining"
  - Normal (>10k): `text-gray-400` (subtle)
  - Warning (1k-10k): `text-yellow-600` (escalated)
  - Critical (<1k): `text-red-600 font-medium` (alarming)
- Only shows when connections exist (avoids clutter on empty state)

### Send Button Disabled State
- Button disabled when `connections.length === 0 || connections.every(c => c.validation_status !== 'valid')`
- Tooltip messages:
  - "No GHL connection. Configure in Settings." (no connections)
  - "No valid GHL connection. Configure in Settings." (all invalid)
  - "Send in progress" (active job)
- Button remains visible but grayed out (better UX than hiding)

### API Types Added
- **DailyRateLimitInfo**: daily_limit, requests_today, remaining, resets_at, warning_level
- **QuickCheckResponse**: valid, error
- **BulkSendRequest.assigned_to** → **assigned_to_list** (string array)
- **ghlApi.getDailyLimit()**: GET /ghl/daily-limit
- **ghlApi.quickCheckConnection(id)**: POST /ghl/connections/{id}/quick-check

## Deviations from Plan

None - plan executed exactly as written.

## Tasks Completed

### Task 1: Add API types and SSE reconnection with backoff
**Status:** ✅ Complete
**Commit:** f01588d
**Files Modified:**
- `toolbox/frontend/src/utils/api.ts`
- `toolbox/frontend/src/hooks/useSSEProgress.ts`

**Key Changes:**
- Added DailyRateLimitInfo and QuickCheckResponse interfaces
- Changed BulkSendRequest.assigned_to to assigned_to_list (string array)
- Added getDailyLimit() and quickCheckConnection(id) methods to ghlApi
- Added reconnectAttemptRef and reconnectTimeoutRef to useSSEProgress
- Implemented exponential backoff reconnection (1s → 2s → 4s → 8s → 16s, max 30s cap)
- Max 5 attempts before showing permanent error
- Reset reconnect counter on successful message
- Added dailyLimitHit detection for status === 'daily_limit_hit'
- Added dailyLimitHit? boolean to CompletionData interface
- Cleanup on unmount clears reconnect timeout

### Task 2: Add multi-owner picker, credential check on open, daily limit display, and rate limit banner
**Status:** ✅ Complete
**Commit:** 05ea738
**Files Modified:**
- `toolbox/frontend/src/components/GhlSendModal.tsx`
- `toolbox/frontend/src/pages/GhlPrep.tsx`

**Key Changes (GhlSendModal):**
- Replaced contactOwner state with selectedOwners: string[] (max 2)
- Multi-owner checkbox list UI with disabled state after 2 selections
- Info text: "Contacts will be split evenly between selected owners"
- Credential quick-check on modal open via useEffect
- Red alert banner with "Go to Settings to reconnect" link
- Validate & Send disabled when credentialError is set
- buildRequest uses assigned_to_list instead of assigned_to
- Confirmation step shows owner names with "(even split)" suffix
- Daily limit hit banner in sending step (yellow bg-yellow-50)
- Daily limit hit banner in summary step with "Partial Send (Daily Limit)" title
- Button text changes to "View Remaining Contacts" when dailyLimitHit

**Key Changes (GhlPrep):**
- Added dailyLimit state (DailyRateLimitInfo | null)
- Fetch daily limit on mount (when connections exist)
- Refresh daily limit after send completes (in handleModalClose)
- Daily capacity info line below Send to GHL button
- Visual escalation: gray-400 → yellow-600 → red-600 font-medium
- Send button disabled when no valid connections exist
- Tooltip shows reason for disabled state

## Technical Details

### SSE Reconnection Logic
```typescript
eventSource.onerror = () => {
  if (eventSource.readyState === EventSource.CLOSED) {
    if (reconnectAttemptRef.current < 5) {
      const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000)
      reconnectAttemptRef.current++
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectEventSource()
      }, backoffMs)
    } else {
      setError('Connection lost. Refresh to check progress.')
    }
  }
}
```

**Backoff sequence:** 1000ms, 2000ms, 4000ms, 8000ms, 16000ms (then stop)

### Multi-Owner Selection Pattern
```typescript
const isSelected = selectedOwners.includes(user.id)
const isDisabled = !isSelected && selectedOwners.length >= 2

<input
  type="checkbox"
  checked={isSelected}
  disabled={isDisabled}
  onChange={(e) => {
    if (e.target.checked) {
      setSelectedOwners([...selectedOwners, user.id])
    } else {
      setSelectedOwners(selectedOwners.filter(id => id !== user.id))
    }
  }}
/>
```

### Daily Capacity Visual Escalation
```typescript
<p className={`text-xs ${
  dailyLimit.warning_level === 'critical' ? 'text-red-600 font-medium' :
  dailyLimit.warning_level === 'warning' ? 'text-yellow-600' :
  'text-gray-400'
}`}>
  Daily capacity: {dailyLimit.remaining.toLocaleString()} remaining
</p>
```

### Send Button Disabled Logic
```typescript
disabled={
  connections.length === 0 ||
  connections.every(c => c.validation_status !== 'valid') ||
  (!!activeJobId)
}
```

## UI/UX Improvements

### Before
- Single contact owner dropdown (one user only)
- No credential validation until send attempt
- No daily limit visibility until after send starts
- SSE disconnects permanently on network hiccup
- Generic "View Failed Contacts" button even for rate limits
- Send button enabled even with invalid connections

### After
- Multi-owner checkboxes with max 2 selection and even-split info
- Credential quick-check on modal open with actionable Settings link
- Daily capacity visible before opening modal with visual escalation
- SSE auto-reconnects up to 5 times with exponential backoff
- "View Remaining Contacts" button when daily limit hit (clearer intent)
- Send button disabled with tooltip when no valid connections exist

## Testing Notes

### Manual Testing Checklist
- [ ] Daily capacity info line shows near Send to GHL button
- [ ] Capacity line changes color based on warning level (gray → yellow → red)
- [ ] Send button disabled when no connections or all invalid
- [ ] Tooltip shows correct disabled reason
- [ ] Multi-owner checkboxes allow selecting 1-2 users
- [ ] Checkboxes disable after 2 selections
- [ ] Even-split info text appears with 2 owners
- [ ] Credential quick-check runs on modal open
- [ ] Red alert banner shows with Settings link on invalid credentials
- [ ] Validate & Send disabled when credential error exists
- [ ] Daily limit hit shows yellow banner in progress view
- [ ] Summary step shows "Partial Send (Daily Limit)" title
- [ ] "View Remaining Contacts" button appears when daily limit hit
- [ ] SSE reconnects automatically on network interruption
- [ ] Error shows after 5 failed reconnection attempts

### Edge Cases to Verify
1. **No connections:** Send button disabled, no daily capacity line
2. **All connections invalid:** Send button disabled, daily capacity line hidden
3. **Connection becomes invalid while modal open:** Credential error appears
4. **Daily limit hit mid-batch:** Yellow banner appears immediately in progress view
5. **Network interruption during send:** SSE reconnects transparently
6. **5+ network failures:** Shows permanent error, user must refresh
7. **1 owner selected:** No even-split text
8. **2 owners selected:** Even-split text visible, no more checkboxes available
9. **Zero daily capacity remaining:** Send button still enabled (backend enforces limit)

## Production Readiness

### What's Production-Safe
✅ SSE auto-reconnection prevents frustration from transient network issues
✅ Daily capacity visibility prevents wasted attempts on full quota
✅ Credential quick-check prevents invalid send attempts
✅ Multi-owner UI supports team workflows with clear even-split messaging
✅ Daily limit hit banner provides clear next steps (wait until midnight UTC)
✅ Send button disabled state prevents user confusion with broken connections

### What Still Needs Attention
⚠️ **Daily limit not enforced in UI** - User can still click Send even at zero capacity (backend handles enforcement, but UI could warn proactively)
⚠️ **No retry mechanism for rate-limited contacts** - Users must manually export failed contacts and retry after midnight
⚠️ **SSE reconnection only handles network errors** - Server-side errors (500, 502) still show permanent error

## Next Steps

**Phase 13 Complete** - All production hardening tasks done:
- ✅ 13-01: Backend Production Hardening (daily limit tracking, multi-owner distribution)
- ✅ 13-02: Frontend Daily Limit UI (this plan)
- ✅ 13-03: GHL Integration Help Documentation

**v1.2 GHL API Integration Milestone Complete** - Ready for user testing.

## Self-Check

### Verification Commands
```bash
# TypeScript compiles without errors
cd toolbox/frontend && npx tsc --noEmit

# Verify API types exist
grep -n "DailyRateLimitInfo" toolbox/frontend/src/utils/api.ts
grep -n "QuickCheckResponse" toolbox/frontend/src/utils/api.ts
grep -n "assigned_to_list" toolbox/frontend/src/utils/api.ts

# Verify hook changes
grep -n "reconnectAttempt" toolbox/frontend/src/hooks/useSSEProgress.ts
grep -n "dailyLimitHit" toolbox/frontend/src/hooks/useSSEProgress.ts

# Verify modal changes
grep -n "selectedOwners" toolbox/frontend/src/components/GhlSendModal.tsx
grep -n "credentialError" toolbox/frontend/src/components/GhlSendModal.tsx

# Verify page changes
grep -n "dailyLimit" toolbox/frontend/src/pages/GhlPrep.tsx
```

### Files Exist
✅ `toolbox/frontend/src/utils/api.ts` - Modified with new types and methods
✅ `toolbox/frontend/src/hooks/useSSEProgress.ts` - Modified with reconnection logic
✅ `toolbox/frontend/src/components/GhlSendModal.tsx` - Modified with multi-owner UI
✅ `toolbox/frontend/src/pages/GhlPrep.tsx` - Modified with daily limit display

### Commits Exist
✅ f01588d - feat(13-02): add API types and SSE reconnection with backoff
✅ 05ea738 - feat(13-02): add multi-owner picker, credential check, daily limit display, and rate limit banner

## Self-Check: PASSED

All files modified as expected. All commits created successfully. TypeScript compilation passes without errors.
