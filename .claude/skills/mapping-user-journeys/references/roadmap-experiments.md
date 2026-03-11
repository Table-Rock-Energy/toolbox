# Roadmap & Experiments Reference

## Contents
- Feature Flag Strategy (Missing)
- Safe Rollout Patterns
- Phasing UX Improvements
- Journey Improvement Checklist

---

## Feature Flag Strategy (Missing)

Table Rock Tools has **no feature flag system**. All changes deploy immediately to all users via `git push → main → Cloud Run`. The user base is small (allowlist-controlled internal users), so the risk of breaking production is high relative to a staged rollout.

**Recommended minimal approach** — use Firestore to store feature flags per user:

```python
# backend/app/core/config.py — add feature flag support
async def get_feature_flags(user_email: str) -> dict:
    doc = await firestore_service.get_document("feature_flags", user_email)
    return doc or {}

# Check flag in an endpoint
flags = await get_feature_flags(current_user["email"])
if flags.get("new_extract_ui"):
    return new_extract_response()
return legacy_extract_response()
```

```typescript
// Frontend: fetch flags after auth
const [flags, setFlags] = useState<Record<string, boolean>>({});

useEffect(() => {
  if (user) {
    fetch('/api/admin/feature-flags')
      .then(r => r.json())
      .then(setFlags);
  }
}, [user]);

// Conditionally render new UI
{flags.new_extract_ui ? <NewExtractPanel /> : <ExtractPanel />}
```

For admin users in production, toggle flags directly in Firestore console before rolling out to everyone.

---

## Safe Rollout Patterns

Since the allowlist is small and known, safe rollout is simpler than public apps:

**Option 1: Admin-first rollout**

Enable for `james@tablerocktx.com` first via Firestore flag. Validate on real data before enabling for all users.

**Option 2: Environment-gated features**

```python
# backend/app/core/config.py
@property
def new_revenue_parser_enabled(self) -> bool:
    return self.environment == "development" or os.getenv("ENABLE_NEW_PARSER") == "true"
```

```bash
# Enable in Cloud Run without redeploying
gcloud run services update table-rock-tools \
  --set-env-vars ENABLE_NEW_PARSER=true \
  --region us-central1
```

**Option 3: Soft launch with fallback**

```python
# Revenue parser: try new parser, fall back to old on failure
try:
    result = new_enverus_parser.parse(text)
    if result.confidence < 0.8:
        raise ValueError("Low confidence")
except Exception:
    result = legacy_energylink_parser.parse(text)
```

---

## Phasing UX Improvements

Prioritize journey improvements by friction severity:

**Phase 1 — Critical blockers (implement immediately):**
- [ ] Proration prereq banner (RRC data missing)
- [ ] FileUpload validation error display
- [ ] `isAuthorized=false` → show "access pending" instead of redirect

**Phase 2 — High friction (next sprint):**
- [ ] Post-export next-step panel
- [ ] Long-operation progress indicators (RRC download, revenue batch)
- [ ] RRC download status polling on Settings page

**Phase 3 — Engagement improvements (backlog):**
- [ ] Cross-session job result persistence
- [ ] Dashboard "resume last job" links
- [ ] Cross-tool workflow handoff suggestions
- [ ] Tool usage success rate on Dashboard

**Phase 4 — Analytics foundation:**
- [ ] Structured event logging to Firestore
- [ ] Funnel completion tracking per tool
- [ ] Admin usage dashboard

---

## Journey Improvement Checklist

Copy this checklist when auditing a specific tool's journey:

- [ ] Auth gate: unauthorized users see clear "access pending" vs silent redirect
- [ ] Prerequisite check: any setup requirements shown before upload (not after failure)
- [ ] File upload: invalid file type shows inline error
- [ ] Loading state: all async operations show spinner + descriptive message
- [ ] Error state: backend errors have actionable detail + recovery button
- [ ] Empty state: pre-upload empty state explains what file to upload
- [ ] Zero results: post-upload empty state explains why (not just "no data")
- [ ] Success state: results load and are scannable without horizontal scrolling
- [ ] Export: download triggers correctly, post-export guidance shown
- [ ] Recovery: "Process another file" / reset flow is obvious after export

Validate each step using Playwright browser tools to navigate the actual app. See the **designing-onboarding-paths** skill for implementation patterns on items 3-5.
