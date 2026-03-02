---
name: mapping-user-journeys
description: |
  Maps in-app journeys and identifies friction points in code
  Use when: analyzing user flows, debugging onboarding drop-offs, identifying UX inconsistencies, planning feature improvements, or auditing tool adoption
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Mapping User Journeys Skill

Maps complete user flows through the Table Rock Tools application, from authentication through tool completion. Identifies friction points by analyzing route transitions, state management, error handling, and UI feedback patterns. Grounds recommendations in actual React components, FastAPI endpoints, and Firestore data structures.

## Quick Start

### Map a Complete Journey

```bash
# Find all pages in a user flow
cd toolbox/frontend/src
grep -r "useNavigate\|navigate(" pages/Extract.tsx
grep -r "fetch.*api/extract" pages/Extract.tsx

# Check backend validation and error responses
cd toolbox/backend/app
grep -r "HTTPException" api/extract.py
```

### Identify State Gaps

```typescript
// GOOD - Clear loading/error states
const [isProcessing, setIsProcessing] = useState(false);
const [error, setError] = useState<string | null>(null);

if (error) return <ErrorBanner message={error} />;
if (isProcessing) return <LoadingSpinner />;
```

### Audit Navigation Flow

```typescript
// Extract tool journey: Login → Dashboard → Extract → Results → Export
// Check each transition has proper auth, loading, and error handling
<ProtectedRoute element={<Extract />} /> // Auth gate
→ useEffect fetch API                    // Data loading
→ error boundary                         // Error handling
→ results display                        // Success state
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Journey Map | Auth → Tool Selection → Upload → Processing → Results → Export | All 4 tools follow this pattern |
| Friction Point | Missing feedback, unclear errors, broken state transitions | No progress indicator during RRC download |
| State Coverage | Loading, error, empty, partial, success states | `isLoading`, `error`, `results.length === 0` |
| Exit Path | How users leave or retry after errors | "Try Again" button, back to dashboard link |

## Common Patterns

### Document the Happy Path

**When:** Starting journey analysis for a new feature

1. Trace route definitions in `frontend/src/App.tsx`
2. Map component hierarchy in tool pages
3. Identify API calls and their responses
4. Document state transitions at each step

### Identify Missing Feedback

**When:** Users report confusion or "nothing happening"

```typescript
// BAD - No feedback during async operation
const handleUpload = async (file: File) => {
  const result = await api.upload(file);
  setResults(result);
};

// GOOD - Clear feedback at each stage
const handleUpload = async (file: File) => {
  setIsUploading(true);
  setError(null);
  try {
    const result = await api.upload(file);
    setResults(result);
  } catch (err) {
    setError('Upload failed. Please try again.');
  } finally {
    setIsUploading(false);
  }
};
```

### Map Error Recovery Paths

**When:** High drop-off rates after errors

```python
# Backend: Provide actionable error messages
raise HTTPException(
    status_code=400,
    detail="RRC data not available. Download it from Settings → RRC Data."
)

# Frontend: Show recovery actions
{error && (
  <div>
    <p>{error}</p>
    <button onClick={() => navigate('/settings')}>Go to Settings</button>
  </div>
)}
```

## See Also

- [activation-onboarding](references/activation-onboarding.md) - First-run flows and empty states
- [engagement-adoption](references/engagement-adoption.md) - Feature discovery patterns
- [in-app-guidance](references/in-app-guidance.md) - Help text and tooltips
- [product-analytics](references/product-analytics.md) - Tracking journey metrics
- [roadmap-experiments](references/roadmap-experiments.md) - A/B testing flows
- [feedback-insights](references/feedback-insights.md) - User friction signals

## Related Skills

- **react** - Component patterns and state management
- **typescript** - Type-safe route and state definitions
- **firebase** - Auth state and session management
- **frontend-design** - UI patterns for feedback and guidance
- **fastapi** - API error responses and validation
- **designing-onboarding-paths** - First-time user flows
- **orchestrating-feature-adoption** - Driving tool usage
- **instrumenting-product-metrics** - Measuring journey success