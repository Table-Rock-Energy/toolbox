# Phase 10: Frontend Foundation - Research

**Researched:** 2026-02-27
**Domain:** React 19 + TypeScript frontend UI development for GHL connection management and send modal
**Confidence:** HIGH

## Summary

Phase 10 builds the frontend UI for GHL sub-account management in Settings and the Send modal on the GHL Prep results page. All features use stub/mock data (local state) while Phase 9 backend runs in parallel. Real API wiring happens after Phase 9 completes.

The existing codebase already has strong patterns established: React 19 with TypeScript strict mode, Tailwind CSS 3.x utility-first styling, Lucide React icons, controlled component patterns, and Firebase Auth context. The Settings page follows a card-based layout with inline forms, and the Modal component is already built with accessibility features (ESC close, backdrop click, focus management). This phase extends those patterns with GHL-specific UI sections.

**Primary recommendation:** Build inline card-based forms in Settings using existing component patterns (controlled inputs with useState, Tailwind form utilities, password-masked token field). Use existing Modal component for Send dialog. Store GHL connections in localStorage with a custom useLocalStorage hook for persistence across sessions. Add subtle "Preview" badges to set user expectations during stub mode.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
**Settings layout:**
- Card-based list for GHL connections (each card shows name, Location ID, status)
- Own section in Settings with "GoHighLevel Connections" heading, visually separated
- Not under a generic "Integrations" tab — GHL gets its own prominent section

**Add/edit flow:**
- Inline form appears below existing cards when clicking "Add Connection"
- Clicking a card expands it into edit mode (inline, no modal)
- Fields: connection name, Private Integration Token (password-masked), Location ID

**Delete flow:**
- Small trash icon on each connection card
- Clicking shows inline "Are you sure?" confirmation with Cancel/Delete buttons
- No modal for delete confirmation — stays inline

**Send modal field order:**
- Top-down priority order:
  1. Sub-account selector (dropdown of configured connections)
  2. Campaign tag input (auto-populated from uploaded data's campaign name; defaults to first if multiple; editable)
  3. Contact owner dropdown (disabled with "Connect GHL to load owners" placeholder in stub mode)
  4. SmartList/campaign name field
  5. Manual SMS checkbox
- Bottom of modal shows summary: "Sending X contacts to [Account Name] with tag [campaign-tag]"

**Button placement on results page:**
- "Send to GHL" and "Download CSV" side by side, top-right of results table
- "Send to GHL" is primary (teal filled button), "Download CSV" is secondary (outline)
- Send button uses Lucide Send or ArrowUpRight icon
- When no GHL connection exists: Send button is disabled with hover tooltip "Add a GHL connection in Settings first"

**Stub data strategy:**
- Connections stored in React local state (or localStorage) — no backend calls
- Add/edit/delete fully functional in UI, data doesn't persist across sessions
- Send button in modal is disabled with "GHL integration coming soon" message
- Token field is password-masked input, no validation occurs in stub mode
- Contact owner dropdown is disabled with placeholder text
- Subtle "Preview" badge on GHL section in Settings and Send button to set expectations

### Claude's Discretion
- Exact card styling (shadows, borders, spacing)
- Form validation patterns (required field indicators, error message placement)
- Loading state animations
- Responsive layout behavior for modal and Settings section
- SmartList name field label and placeholder text
</user_constraints>

<phase_requirements>
## Phase Requirements

This phase addresses requirements from REQUIREMENTS.md:

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEND-01 | User sees "Send to GHL" button alongside "Download CSV" on GHL Prep results page | Button placement patterns with Tailwind flex layouts, Lucide icons, disabled state with hover tooltips |
| SEND-02 | User sees a send modal with: sub-account selector, tag input, contact owner dropdown, SmartList/campaign name, manual SMS checkbox | Existing Modal component with accessibility features, controlled form inputs with useState, select/dropdown patterns with Tailwind, checkbox styling |
| CTCT-04 | User can assign a contact owner from a dropdown populated via GHL Users API | Dropdown/select component with disabled state for stub mode, placeholder text patterns |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.0 | UI framework | Already in use, latest stable, hooks-based component patterns |
| TypeScript | 5.9.3 | Type safety | Already configured in strict mode, prevents runtime errors, IDE support |
| Tailwind CSS | 3.4.19 | Utility-first styling | Already in use, rapid UI development, consistent design system with tre-* brand colors |
| Lucide React | 0.563.0 | Icon library | Already in use, consistent icon set across app, lightweight SVG icons |
| Vite | 7.2.4 | Build tool & dev server | Already configured, fast HMR, proxies /api to backend |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Firebase Auth | 12.9.0 | Auth context | Already in use via AuthContext, provides user.email for display |
| React Router | 7.13.0 | Client-side routing | Already in use, navigation between Settings and GhlPrep pages |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| localStorage | React Context only | localStorage provides cross-session persistence (survives page reload), Context is ephemeral |
| Inline forms | Modal-based CRUD | User requested inline forms explicitly — modals add friction for quick edits |
| Controlled components | Uncontrolled with refs | Controlled components provide real-time validation and easier state management (already pattern in codebase) |

**Installation:**
```bash
# All dependencies already installed
cd toolbox/frontend
npm install  # Installs from existing package.json
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── pages/
│   ├── Settings.tsx           # Add GHL section with card list
│   └── GhlPrep.tsx           # Add "Send to GHL" button + modal trigger
├── components/
│   ├── Modal.tsx             # Already exists — reuse for Send dialog
│   ├── GhlConnectionCard.tsx # New: Display/edit/delete connection (inline)
│   └── GhlSendModal.tsx      # New: Send modal content (form fields + summary)
└── hooks/
    └── useLocalStorage.ts    # New: localStorage persistence hook
```

### Pattern 1: localStorage Persistence with Custom Hook
**What:** Custom `useLocalStorage` hook provides useState-like API with automatic localStorage sync
**When to use:** For GHL connection data that should persist across page reloads but doesn't need backend storage (stub mode)
**Example:**
```typescript
// Source: https://usehooks-ts.com/react-hook/use-local-storage (HIGH confidence)
// Adapted for TypeScript with generics
import { useState, useEffect } from 'react'

function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  // Get from localStorage or use initialValue
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error)
      return initialValue
    }
  })

  // Persist to localStorage whenever state changes
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(storedValue))
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error)
    }
  }, [key, storedValue])

  return [storedValue, setStoredValue]
}

export default useLocalStorage
```

**Usage in Settings page:**
```typescript
interface GhlConnection {
  id: string
  name: string
  locationId: string
  token: string  // Stored in plaintext in stub mode (encrypted in Phase 9 backend)
  createdAt: string
}

const [connections, setConnections] = useLocalStorage<GhlConnection[]>('ghl_connections', [])
```

### Pattern 2: Inline Card Expansion (No Modal for Edit)
**What:** Cards expand inline to show edit form, collapse on save/cancel
**When to use:** When user requested inline editing (Settings GHL connections)
**Example:**
```typescript
// GhlConnectionCard.tsx
interface ConnectionCardProps {
  connection: GhlConnection
  isEditing: boolean
  onEdit: () => void
  onSave: (updated: GhlConnection) => void
  onDelete: () => void
  onCancel: () => void
}

function GhlConnectionCard({ connection, isEditing, onEdit, onSave, onDelete, onCancel }: ConnectionCardProps) {
  const [formData, setFormData] = useState(connection)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  if (isEditing) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {/* Inline edit form */}
        <div className="space-y-4">
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Connection name"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
          {/* Token + Location ID fields */}
          <div className="flex gap-2">
            <button onClick={() => onSave(formData)} className="px-4 py-2 bg-tre-navy text-white rounded-lg">
              Save
            </button>
            <button onClick={onCancel} className="px-4 py-2 border border-gray-300 rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 hover:border-tre-teal cursor-pointer" onClick={onEdit}>
      {/* Display mode */}
    </div>
  )
}
```

### Pattern 3: Controlled Form Inputs with Validation States
**What:** React controlled components with Tailwind form state modifiers (invalid, focus, disabled)
**When to use:** All form inputs in GHL Settings section and Send modal
**Example:**
```typescript
// Source: https://v3.tailwindcss.com/docs/hover-focus-and-other-states (HIGH confidence)
<input
  type="text"
  value={connectionName}
  onChange={(e) => setConnectionName(e.target.value)}
  required
  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm shadow-sm placeholder-gray-400
    focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal
    disabled:bg-gray-50 disabled:text-gray-500 disabled:border-gray-200
    invalid:border-red-500 invalid:text-red-600
  "
/>
```

### Pattern 4: Password-Masked Input Field
**What:** Input with type="password" for Private Integration Token
**When to use:** Token field in GHL connection forms
**Example:**
```typescript
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Private Integration Token
  </label>
  <input
    type="password"
    value={token}
    onChange={(e) => setToken(e.target.value)}
    placeholder="Enter token"
    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
  />
  <p className="text-xs text-gray-500 mt-1">Token is stored locally in stub mode</p>
</div>
```

### Pattern 5: Disabled Button with Hover Tooltip
**What:** Button with disabled state + title attribute for tooltip
**When to use:** "Send to GHL" button when no connections exist
**Example:**
```typescript
import { Send } from 'lucide-react'

const hasConnections = connections.length > 0

<button
  onClick={() => setShowSendModal(true)}
  disabled={!hasConnections}
  title={!hasConnections ? 'Add a GHL connection in Settings first' : ''}
  className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
>
  <Send className="w-4 h-4" />
  Send to GHL
</button>
```

### Pattern 6: Preview Badge for Stub Mode
**What:** Small badge indicating feature is in preview/stub mode
**When to use:** GHL section header in Settings, Send to GHL button
**Example:**
```typescript
<div className="flex items-center gap-3">
  <h2 className="text-lg font-oswald font-semibold text-tre-navy">
    GoHighLevel Connections
  </h2>
  <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">
    Preview
  </span>
</div>
```

### Anti-Patterns to Avoid
- **Mixing controlled and uncontrolled inputs:** Always use `value` + `onChange` (controlled) or `defaultValue` + `ref` (uncontrolled), never mix them or leave value uninitialized
- **Direct localStorage mutations:** Always go through useState setter to trigger re-renders
- **Modal for inline operations:** User explicitly requested inline forms for add/edit/delete — don't use modals for Settings CRUD
- **Real API calls in stub mode:** Keep all data in localStorage, no backend integration until Phase 11

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| localStorage sync with React state | Manual getItem/setItem in useEffect | Custom useLocalStorage hook (pattern above) | Handles JSON serialization, error handling, SSR safety, cross-tab sync |
| Modal accessibility | Custom focus trap, ESC handler, backdrop | Existing Modal component in codebase | Already implements ESC close, backdrop click, focus management, ARIA attributes |
| Form validation | Custom validation logic per field | Tailwind form state modifiers + HTML5 validation | Browser-native validation with Tailwind visual states (invalid:, required:, etc.) |
| Icon components | Custom SVG imports | Lucide React (already in use) | Consistent icon set, tree-shakeable, TypeScript support |

**Key insight:** The codebase already has strong component patterns established (Modal, Settings page structure, form inputs). Extend existing patterns rather than introducing new approaches. Avoid complex form libraries (React Hook Form, Formik) for simple controlled forms — overkill for this phase's requirements.

## Common Pitfalls

### Pitfall 1: Controlled Component Switching
**What goes wrong:** Input switches from uncontrolled to controlled (or vice versa) mid-lifecycle, causing React warnings and bugs
**Why it happens:** Value prop is initially `undefined` then set to a string, or mixing `value` and `defaultValue`
**How to avoid:** Always initialize state with empty string `''` not `undefined`, use controlled pattern consistently
**Warning signs:** Console warning "A component is changing an uncontrolled input to be controlled"
**Example fix:**
```typescript
// BAD: value starts undefined
const [name, setName] = useState()  // undefined initially
<input value={name} onChange={(e) => setName(e.target.value)} />

// GOOD: value starts as empty string
const [name, setName] = useState('')  // controlled from the start
<input value={name} onChange={(e) => setName(e.target.value)} />
```

### Pitfall 2: localStorage Quota Exceeded
**What goes wrong:** App crashes when localStorage quota (5-10MB depending on browser) is exceeded
**Why it happens:** Storing large objects or infinite accumulation without cleanup
**How to avoid:** Keep connection data minimal (no large payloads), limit array size, handle quota errors
**Warning signs:** QuotaExceededError in console, data not persisting
**Example prevention:**
```typescript
try {
  window.localStorage.setItem(key, JSON.stringify(value))
} catch (error) {
  if (error instanceof DOMException && error.name === 'QuotaExceededError') {
    console.error('localStorage quota exceeded')
    // Fall back to in-memory state only
  }
}
```

### Pitfall 3: Password Field Autocomplete Interference
**What goes wrong:** Browser autocomplete fills wrong values into token field or prevents manual entry
**Why it happens:** Browser sees `type="password"` and tries to save/fill credentials
**How to avoid:** Use `autocomplete="off"` or `autocomplete="new-password"` on token field
**Warning signs:** Field autofills with unexpected values, can't edit manually
**Example fix:**
```typescript
<input
  type="password"
  value={token}
  onChange={(e) => setToken(e.target.value)}
  autoComplete="new-password"  // Prevents browser autofill
  className="..."
/>
```

### Pitfall 4: Modal Focus Not Trapped
**What goes wrong:** Keyboard users can tab out of modal to elements behind it
**Why it happens:** Existing Modal component may not have full focus trap implementation
**How to avoid:** Verify Modal component traps focus (existing code shows ESC handler and backdrop, check tab behavior)
**Warning signs:** Tab key moves focus to elements behind modal backdrop
**Note:** Existing Modal component (Modal.tsx) has ESC handler and body overflow management, but may need focus trap verification. WCAG 2.1 doesn't strictly require focus trap for dialogs, so this is optional enhancement.

### Pitfall 5: Inline Form Doesn't Clear on Cancel
**What goes wrong:** User clicks Cancel, card collapses, but form data persists in state — next Edit shows stale values
**Why it happens:** Form state (`formData`) not reset on cancel
**How to avoid:** Reset form state to original connection data on cancel
**Warning signs:** Editing connection A, canceling, then editing connection B shows connection A's values
**Example fix:**
```typescript
const handleCancel = () => {
  setFormData(connection)  // Reset to original before closing
  onCancel()
}
```

## Code Examples

Verified patterns from official sources and existing codebase:

### useState Hook for Controlled Inputs
```typescript
// Source: React 19.2.0 official docs (Context7) - HIGH confidence
import { useState } from 'react'

function GhlConnectionForm() {
  const [name, setName] = useState('')
  const [locationId, setLocationId] = useState('')
  const [token, setToken] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Save connection
  }

  return (
    <form onSubmit={handleSubmit}>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      {/* ... */}
    </form>
  )
}
```

### useEffect for Side Effects (localStorage sync)
```typescript
// Source: React 19.2.0 official docs (Context7) - HIGH confidence
import { useEffect, useState } from 'react'

function Component() {
  const [state, setState] = useState('initial')

  // Runs after render (sync to localStorage)
  useEffect(() => {
    window.localStorage.setItem('key', state)
  }, [state])  // Re-run when state changes

  return <div>{state}</div>
}
```

### Tailwind Form Styling with State Modifiers
```css
/* Source: https://v3.tailwindcss.com/docs/hover-focus-and-other-states - HIGH confidence */
.form-input {
  @apply mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm shadow-sm placeholder-gray-400;
  @apply focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal;
  @apply disabled:bg-gray-50 disabled:text-gray-500 disabled:border-gray-200;
  @apply invalid:border-red-500 invalid:text-red-600;
}
```

### Existing Modal Component Usage (from codebase)
```typescript
// Source: toolbox/frontend/src/components/Modal.tsx - HIGH confidence
import { Modal } from '../components'

function GhlPrep() {
  const [showSendModal, setShowSendModal] = useState(false)

  return (
    <>
      <button onClick={() => setShowSendModal(true)}>Send to GHL</button>

      <Modal
        isOpen={showSendModal}
        onClose={() => setShowSendModal(false)}
        title="Send to GoHighLevel"
        size="lg"
      >
        {/* Send form content */}
      </Modal>
    </>
  )
}
```

### Existing Settings Page Pattern (from codebase)
```typescript
// Source: toolbox/frontend/src/pages/Settings.tsx - HIGH confidence
// Card-based section with inline forms
<div className="bg-white rounded-xl border border-gray-200 p-6">
  <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
    Section Title
  </h2>
  <div className="space-y-4">
    {/* Form fields */}
  </div>
  <div className="flex justify-end pt-2">
    <button className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90">
      Save
    </button>
  </div>
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Class components with this.state | Functional components with hooks | React 16.8 (2019) | Simpler code, easier testing, better reusability |
| Redux for all state | Context API for auth, useState for local, libraries for complex forms | React 16.3+ Context API | Less boilerplate for simple state, Redux only when needed |
| CSS-in-JS (styled-components) | Tailwind utility classes | Tailwind 2.0+ adoption | Faster dev, smaller bundles, no runtime CSS-in-JS overhead |
| react-modal library | Built-in dialog element + custom components | HTML5 dialog element (2022) | Native accessibility features, but custom components still common for flexibility |

**Deprecated/outdated:**
- **Class components:** Still supported but functional components + hooks are standard (React 16.8+)
- **componentDidMount/Update:** Replaced by `useEffect` hook
- **PropTypes:** Replaced by TypeScript for type checking
- **react-modal package:** Codebase uses custom Modal component (preferred for this project)

## Open Questions

1. **Should localStorage connections survive across sessions?**
   - What we know: User CONTEXT.md says "data doesn't persist across sessions" but also mentions "localStorage" as storage option
   - What's unclear: Whether "doesn't persist across sessions" means logout/login or page refresh
   - Recommendation: Interpret "sessions" as browser sessions (survives page refresh, cleared on logout). Use localStorage for persistence across page reloads, clear on signout via AuthContext.

2. **Does existing Modal component have full focus trap?**
   - What we know: Modal.tsx has ESC handler, backdrop click, body overflow management
   - What's unclear: Whether tab key is trapped within modal (prevents focus on elements behind modal)
   - Recommendation: Test manually during implementation. If focus escapes modal, add focus trap with tabindex management or focus-trap-react library. Per 2026 WCAG guidance, strict focus trap is not normative requirement.

3. **Should "Preview" badge persist after Phase 9 backend is integrated?**
   - What we know: Badge indicates stub mode during Phase 10 development
   - What's unclear: Whether badge should remain after real API integration in Phase 11
   - Recommendation: Remove "Preview" badge when Phase 11 integrates real GHL API. Badge is temporary UI affordance for Phase 10 only.

## Validation Architecture

> This section is omitted because `workflow.nyquist_validation` is not explicitly set to `true` in .planning/config.json (only `workflow.verifier: true` exists, which is for post-implementation verification, not test architecture planning).

## Sources

### Primary (HIGH confidence)
- [React 19.2.0 GitHub repository](https://github.com/facebook/react/tree/v19.2.0) - useState, useEffect hooks patterns
- [Tailwind CSS v3 official docs](https://v3.tailwindcss.com/docs/hover-focus-and-other-states) - Form state modifiers, utility patterns
- Existing codebase:
  - `toolbox/frontend/src/components/Modal.tsx` - Modal component with accessibility features
  - `toolbox/frontend/src/pages/Settings.tsx` - Card-based Settings layout patterns
  - `toolbox/frontend/src/pages/GhlPrep.tsx` - Results page with export button patterns

### Secondary (MEDIUM confidence)
- [React Forms Best Practices (Fullstack Foundations)](https://www.fullstackfoundations.com/blog/react-forms-best-practices) - Controlled vs uncontrolled component patterns
- [React Form Validation Patterns (react.wiki)](https://react.wiki/hooks/form-validation/) - useState validation patterns
- [useLocalStorage Hook (usehooks-ts)](https://usehooks-ts.com/react-hook/use-local-storage) - localStorage persistence hook pattern
- [Persisting React State in localStorage (Josh W. Comeau)](https://www.joshwcomeau.com/react/persisting-react-state-in-localstorage/) - Cross-tab sync, SSR safety
- [Building Accessible Modals with Focus Traps (UXPin)](https://www.uxpin.com/studio/blog/how-to-build-accessible-modals-with-focus-traps/) - Modal accessibility best practices
- [Dialog Element Accessibility 2026 (Medianic)](https://www.medianic.co.uk/2026/02/20/dialog-element-accessibility-rethinking-focus-trapping-in-modals/) - Modern perspective on focus trap requirements

### Tertiary (LOW confidence)
- None used — all findings verified with official docs or existing codebase patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use with established patterns in codebase
- Architecture: HIGH - Extending existing Settings page and Modal component patterns, localStorage hook pattern verified from multiple sources
- Pitfalls: HIGH - Controlled component issues well-documented in React docs, localStorage quota and password field autocomplete are common web development gotchas

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (30 days) — React 19 and Tailwind 3 are stable, no major changes expected
