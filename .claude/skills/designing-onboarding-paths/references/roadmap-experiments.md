# Roadmap & Experiments Reference

## Contents
- Feature Flags (Not Yet Implemented)
- Rollout Strategies
- Beta Testing Patterns
- Deprecation & Sunsetting
- Anti-Patterns

---

## Feature Flags (Not Yet Implemented)

Table Rock Tools has **no feature flag system**. All features are enabled for all users immediately upon deployment.

### Simple Feature Flag Implementation

For internal tools, avoid complex platforms (LaunchDarkly, Split.io). Use **environment variables + localStorage** for user-level overrides:

```typescript
// toolbox/frontend/src/utils/featureFlags.ts
interface FeatureFlags {
  'revenue-energy-transfer-support': boolean
  'proration-auto-refresh': boolean
  'dashboard-job-history': boolean
  'extract-bulk-edit': boolean
}

const DEFAULT_FLAGS: FeatureFlags = {
  'revenue-energy-transfer-support': import.meta.env.VITE_FEATURE_REVENUE_ET === 'true',
  'proration-auto-refresh': import.meta.env.VITE_FEATURE_PRORATION_REFRESH === 'true',
  'dashboard-job-history': import.meta.env.VITE_FEATURE_DASHBOARD_HISTORY === 'true',
  'extract-bulk-edit': false, // Not yet released
}

export function isFeatureEnabled(flag: keyof FeatureFlags): boolean {
  // Check localStorage override first (for beta testers)
  const override = localStorage.getItem(`feature_${flag}`)
  if (override === 'true') return true
  if (override === 'false') return false
  
  // Fall back to default
  return DEFAULT_FLAGS[flag]
}

export function enableFeatureForUser(flag: keyof FeatureFlags) {
  localStorage.setItem(`feature_${flag}`, 'true')
}

export function disableFeatureForUser(flag: keyof FeatureFlags) {
  localStorage.setItem(`feature_${flag}`, 'false')
}
```

**Backend feature flags:**

```python
# toolbox/backend/app/core/config.py
class Settings(BaseSettings):
    # Existing settings...
    
    # Feature flags
    feature_revenue_energy_transfer: bool = Field(
        default=False,
        description="Enable Energy Transfer statement parsing in Revenue tool"
    )
    feature_proration_auto_refresh: bool = Field(
        default=False,
        description="Auto-refresh RRC data on Proration page load"
    )
    
    @property
    def is_feature_enabled(self, flag: str) -> bool:
        return getattr(self, f"feature_{flag}", False)
```

### Conditional Rendering with Feature Flags

```tsx
// Revenue.tsx - Show new feature behind flag
import { isFeatureEnabled } from '../utils/featureFlags'

export default function Revenue() {
  const showEnergyTransfer = isFeatureEnabled('revenue-energy-transfer-support')
  
  return (
    <div>
      <h1>Revenue Tool</h1>
      <p>
        Supports: EnergyLink PDFs
        {showEnergyTransfer && ', Energy Transfer PDFs'}
      </p>
      
      {showEnergyTransfer && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
          <Sparkles className="w-5 h-5 text-amber-600 inline mr-2" />
          <strong>New:</strong> Energy Transfer statement support is now available.
        </div>
      )}
    </div>
  )
}
```

---

## Rollout Strategies

### Percentage-Based Rollout

```typescript
// toolbox/frontend/src/utils/featureFlags.ts
export function isInRollout(flag: string, percentage: number): boolean {
  const userId = localStorage.getItem('user_id') || 'anonymous'
  
  // Hash user ID to get consistent assignment
  const hash = userId.split('').reduce((acc, char) => {
    return char.charCodeAt(0) + ((acc << 5) - acc)
  }, 0)
  
  const bucket = Math.abs(hash) % 100
  return bucket < percentage
}

// Usage
const showNewDashboard = isFeatureEnabled('dashboard-job-history') && isInRollout('dashboard-job-history', 50)
```

**Backend rollout:**

```python
# toolbox/backend/app/api/admin.py
@router.post("/features/{flag}/rollout")
async def set_rollout_percentage(flag: str, percentage: int):
    """Set rollout percentage for a feature flag."""
    if percentage < 0 or percentage > 100:
        raise HTTPException(status_code=400, detail="Percentage must be 0-100")
    
    from app.services import firestore_service as db
    
    await db.update_feature_flag(flag, {"rollout_percentage": percentage})
    
    return {"flag": flag, "rollout_percentage": percentage}
```

### User Allowlist Rollout

```typescript
// Enable features for specific beta testers
const BETA_TESTERS = [
  'james@tablerocktx.com',
  'john.doe@tablerocktx.com',
]

export function isBetaTester(email: string): boolean {
  return BETA_TESTERS.includes(email)
}

// Usage in component
const { user } = useAuth()
const canUseBulkEdit = isFeatureEnabled('extract-bulk-edit') || isBetaTester(user?.email || '')

{canUseBulkEdit && (
  <button onClick={handleBulkEdit}>Bulk Edit Entries</button>
)}
```

---

## Beta Testing Patterns

### Beta Badge UI

```tsx
// Show "Beta" badge on experimental features
<div className="flex items-center gap-2">
  <h2>Bulk Edit</h2>
  <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">
    Beta
  </span>
</div>
```

### Beta Feedback Widget

```tsx
// Add feedback link for beta features
{canUseBulkEdit && (
  <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
    <div className="flex items-start gap-3">
      <TestTube className="w-5 h-5 text-purple-600 flex-shrink-0" />
      <div className="flex-1">
        <p className="font-medium text-purple-900">You're testing Bulk Edit (Beta)</p>
        <p className="text-sm text-purple-700 mt-1">
          This feature is in early testing. Report issues or suggestions.
        </p>
        <a
          href="mailto:james@tablerocktx.com?subject=Bulk Edit Beta Feedback"
          className="mt-2 inline-flex items-center gap-1 text-sm text-purple-700 hover:underline"
        >
          <Mail className="w-4 h-4" />
          Send Feedback
        </a>
      </div>
    </div>
  </div>
)}
```

### Beta Opt-In/Out

```tsx
// Settings.tsx - Allow users to opt in/out of beta features
<div className="bg-white rounded-xl border border-gray-200 p-6">
  <h3 className="font-semibold text-lg mb-4">Beta Features</h3>
  <p className="text-sm text-gray-600 mb-4">
    Enable experimental features to try new functionality before general release.
  </p>
  
  <div className="space-y-3">
    <label className="flex items-center justify-between">
      <span className="text-sm">Bulk Edit (Extract Tool)</span>
      <input
        type="checkbox"
        checked={isFeatureEnabled('extract-bulk-edit')}
        onChange={(e) => {
          if (e.target.checked) {
            enableFeatureForUser('extract-bulk-edit')
          } else {
            disableFeatureForUser('extract-bulk-edit')
          }
        }}
        className="form-checkbox text-tre-teal"
      />
    </label>
    <label className="flex items-center justify-between">
      <span className="text-sm">Auto-Refresh RRC Data (Proration)</span>
      <input
        type="checkbox"
        checked={isFeatureEnabled('proration-auto-refresh')}
        onChange={(e) => {
          if (e.target.checked) {
            enableFeatureForUser('proration-auto-refresh')
          } else {
            disableFeatureForUser('proration-auto-refresh')
          }
        }}
        className="form-checkbox text-tre-teal"
      />
    </label>
  </div>
</div>
```

---

## Deprecation & Sunsetting

### Deprecation Warning Banner

```tsx
// Show warning when feature will be removed
<div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6">
  <div className="flex items-start gap-3">
    <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0" />
    <div>
      <p className="font-medium text-orange-900">Deprecation Notice</p>
      <p className="text-sm text-orange-700 mt-1">
        The old CSV export format will be removed on March 1, 2026. 
        Please switch to the new format before then.
      </p>
      <Link
        to="/help#new-export-format"
        className="mt-2 inline-flex items-center gap-1 text-sm text-orange-700 hover:underline"
      >
        Learn about the new format
        <ExternalLink className="w-3 h-3" />
      </Link>
    </div>
  </div>
</div>
```

### Migration Path

```tsx
// Title.tsx - Show migration prompt for old format
{useOldFormat && (
  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
    <p className="font-medium text-yellow-900">Using Legacy Export Format</p>
    <p className="text-sm text-yellow-700 mt-1 mb-3">
      The new format includes additional fields and better compatibility with downstream systems.
    </p>
    <button
      onClick={() => {
        setUseOldFormat(false)
        localStorage.setItem('export-format', 'v2')
      }}
      className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700"
    >
      Switch to New Format
    </button>
  </div>
)}
```

---

## Anti-Patterns

### WARNING: Feature Flags for Configuration

**The Problem:**

```typescript
// BAD - Using feature flags for config values
const maxUploadSize = isFeatureEnabled('large-file-support') ? 100 : 50
```

**Why This Breaks:**
1. **Not a feature** - Config values aren't features
2. **Type mismatch** - Flags are booleans, config is numbers/strings
3. **Confusing** - "large-file-support" doesn't convey the actual limit

**The Fix:**

```typescript
// GOOD - Use environment variables for config
const maxUploadSize = parseInt(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB || '50', 10)
```

### WARNING: Too Many Feature Flags

**The Problem:**

```typescript
// BAD - Flag for every small UI change
if (isFeatureEnabled('button-color-blue')) { ... }
if (isFeatureEnabled('sidebar-width-250')) { ... }
if (isFeatureEnabled('table-row-hover')) { ... }
```

**Why This Breaks:**
1. **Maintenance burden** - Flags accumulate over time
2. **Decision paralysis** - Engineers flag everything instead of shipping
3. **Dead code** - Flags never get cleaned up

**The Fix:**

Only use feature flags for:
- **Risky changes** that might need rollback
- **Large features** that need gradual rollout
- **Beta features** that need user opt-in

```typescript
// GOOD - Flags for substantial features only
if (isFeatureEnabled('revenue-energy-transfer-support')) {
  // Major new feature with new parsing logic
}
```

**Clean up flags after rollout:**

```bash
# After feature is stable and rolled out to 100%
git grep 'revenue-energy-transfer-support'
# Remove all references and the flag definition
```

### WARNING: Client-Side Only Feature Flags

**The Problem:**

```typescript
// BAD - Feature flag only checked on frontend
if (isFeatureEnabled('bulk-delete')) {
  await fetch('/api/extract/delete-all', { method: 'DELETE' })
}
```

**Why This Breaks:**
1. **Security risk** - Users can enable flags via localStorage
2. **Inconsistent state** - Backend might not support the feature
3. **Data loss** - Dangerous operations need backend validation

**The Fix:**

```typescript
// GOOD - Backend validates feature access
if (isFeatureEnabled('bulk-delete')) {
  try {
    await fetch('/api/extract/delete-all', { method: 'DELETE' })
  } catch (err) {
    if (err.status === 403) {
      alert('Bulk delete is not enabled on the server')
    }
  }
}
```

**Backend guard:**

```python
# toolbox/backend/app/api/extract.py
from app.core.config import settings

@router.delete("/delete-all")
async def delete_all_entries():
    if not settings.feature_bulk_delete:
        raise HTTPException(status_code=403, detail="Bulk delete not enabled")
    
    # ... delete logic