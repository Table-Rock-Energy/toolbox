# Roadmap & Experiments Reference

## Contents
- Feature Flags via Config
- Gradual Rollouts
- A/B Test Patterns
- Release Notes Integration
- Rollback Safety

---

## Feature Flags via Config

**No need for LaunchDarkly/Flagsmith for internal tools.** Use Pydantic Settings with environment variables.

### Backend: Feature Flags

```python
# core/config.py - Add feature flags
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Feature flags
    enable_bulk_upload: bool = Field(default=False, description="Allow uploading multiple files at once")
    enable_ai_entity_detection: bool = Field(default=False, description="Use AI for entity type classification")
    enable_export_templates: bool = Field(default=False, description="Allow users to save custom export formats")
    max_concurrent_jobs: int = Field(default=5, description="Max parallel processing jobs per user")
    
    class Config:
        env_file = ".env"

settings = Settings()
```

**Usage in API routes:**

```python
# api/extract.py
from app.core.config import settings

@router.post("/bulk-upload")
async def bulk_upload(files: list[UploadFile] = File(...)):
    if not settings.enable_bulk_upload:
        raise HTTPException(
            status_code=403,
            detail="Bulk upload is not enabled. Contact admin to enable this feature."
        )
    
    # ... process files ...
```

### Frontend: Feature Flag Endpoint

```python
# api/config.py - New file
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/feature-flags")
async def get_feature_flags():
    """Return enabled feature flags for frontend."""
    return {
        "bulk_upload": settings.enable_bulk_upload,
        "ai_entity_detection": settings.enable_ai_entity_detection,
        "export_templates": settings.enable_export_templates,
    }
```

**Frontend consumption:**

```tsx
// Extract.tsx - Conditionally show bulk upload
const [features, setFeatures] = useState({ bulk_upload: false });

useEffect(() => {
  const fetchFeatures = async () => {
    const response = await fetch('/api/config/feature-flags');
    const data = await response.json();
    setFeatures(data);
  };
  
  fetchFeatures();
}, []);

// Render:
{features.bulk_upload && (
  <button className="...">
    Upload Multiple Files
  </button>
)}
```

---

## Gradual Rollouts

**Pattern: Email-based rollout** (no complex user segmentation needed for small teams)

```python
# core/config.py
class Settings(BaseSettings):
    # ... existing ...
    
    # Gradual rollout: comma-separated emails
    ai_entity_detection_users: str = Field(
        default="",
        description="Comma-separated emails with access to AI entity detection (or 'all')"
    )
    
    @property
    def ai_entity_detection_enabled_for_user(self, email: str) -> bool:
        """Check if AI entity detection is enabled for this user."""
        if not self.enable_ai_entity_detection:
            return False
        
        if self.ai_entity_detection_users == "all":
            return True
        
        allowed = [e.strip() for e in self.ai_entity_detection_users.split(",")]
        return email in allowed
```

**Usage:**

```python
# api/title.py
from app.core.auth import get_current_user_email

@router.post("/upload")
async def upload_title(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_email)
):
    # ... process file ...
    
    # Use AI entity detection if enabled for this user
    if settings.ai_entity_detection_enabled_for_user(current_user):
        entities = await ai_service.detect_entities(entries)
    else:
        entities = rule_based_entity_detection(entries)
    
    return result
```

**Set in production:**

```bash
# .env or Cloud Run env vars
ENABLE_AI_ENTITY_DETECTION=true
AI_ENTITY_DETECTION_USERS=james@tablerocktx.com,admin@tablerocktx.com
```

**After testing, roll out to all:**

```bash
AI_ENTITY_DETECTION_USERS=all
```

---

## A/B Test Patterns

**For internal tools, A/B tests are rare** (not enough users for statistical significance). Use **user preference toggles** instead.

### Pattern: User-Controlled Experiments

```tsx
// Settings.tsx - Let users opt into beta features
const [preferences, setPreferences] = useState({
  use_ai_entity_detection: false,
  enable_keyboard_shortcuts: false,
});

useEffect(() => {
  const saved = localStorage.getItem('user_preferences');
  if (saved) setPreferences(JSON.parse(saved));
}, []);

const togglePreference = (key: string) => {
  const updated = { ...preferences, [key]: !preferences[key] };
  setPreferences(updated);
  localStorage.setItem('user_preferences', JSON.stringify(updated));
};

// UI:
<div className="space-y-4">
  <h2 className="text-lg font-oswald font-semibold text-tre-navy">
    Beta Features
  </h2>
  
  <label className="flex items-center justify-between p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
    <div>
      <p className="font-medium text-tre-navy">AI Entity Detection</p>
      <p className="text-sm text-gray-500">
        Use machine learning to classify entity types (experimental)
      </p>
    </div>
    <input
      type="checkbox"
      checked={preferences.use_ai_entity_detection}
      onChange={() => togglePreference('use_ai_entity_detection')}
      className="w-5 h-5 text-tre-teal"
    />
  </label>
</div>
```

**Backend: Respect user preference**

```python
# api/title.py
@router.post("/upload")
async def upload_title(
    file: UploadFile = File(...),
    use_ai: bool = Query(False, description="Use AI entity detection (beta)"),
    current_user: str = Depends(get_current_user_email)
):
    # ... process file ...
    
    if use_ai and settings.enable_ai_entity_detection:
        entities = await ai_service.detect_entities(entries)
    else:
        entities = rule_based_entity_detection(entries)
    
    return result
```

**Frontend sends preference:**

```tsx
// Title.tsx
const { preferences } = useUserPreferences(); // Custom hook

const handleUpload = async (file: File) => {
  const response = await fetch(
    `/api/title/upload?use_ai=${preferences.use_ai_entity_detection}`,
    {
      method: 'POST',
      body: formData,
    }
  );
  // ...
};
```

---

## Release Notes Integration

**Pattern: In-app changelog modal**

```tsx
// pages/Changelog.tsx - New page
const releases = [
  {
    version: '1.2.0',
    date: '2026-02-01',
    changes: [
      { type: 'feature', text: 'RRC data now downloads automatically on the 1st of each month' },
      { type: 'feature', text: 'Added PDF export for proration results' },
      { type: 'fix', text: 'Fixed entity detection for trusts with multiple trustees' },
    ],
  },
  {
    version: '1.1.0',
    date: '2026-01-15',
    changes: [
      { type: 'feature', text: 'Multi-file upload for Revenue tool' },
      { type: 'improvement', text: 'Faster CSV export (2x speedup)' },
    ],
  },
];

export default function Changelog() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
        Release Notes
      </h1>
      
      <div className="space-y-6">
        {releases.map(release => (
          <div key={release.version} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-baseline gap-3 mb-4">
              <h2 className="text-lg font-oswald font-semibold text-tre-navy">
                Version {release.version}
              </h2>
              <span className="text-sm text-gray-500">{release.date}</span>
            </div>
            
            <ul className="space-y-2">
              {release.changes.map((change, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className={`
                    inline-block px-2 py-0.5 rounded text-xs font-medium uppercase
                    ${change.type === 'feature' ? 'bg-green-100 text-green-800' : ''}
                    ${change.type === 'fix' ? 'bg-red-100 text-red-800' : ''}
                    ${change.type === 'improvement' ? 'bg-blue-100 text-blue-800' : ''}
                  `}>
                    {change.type}
                  </span>
                  <span className="text-gray-700 text-sm">{change.text}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Link from Help page:**

```tsx
// Help.tsx - Add to resources
{
  title: 'Release Notes',
  description: 'See what\'s new in Table Rock Tools',
  icon: Newspaper,
  link: '/changelog',
}
```

---

## Rollback Safety

**For internal tools, rollback is simple:** Just redeploy previous commit.

### Pattern: Feature Kill Switch

```python
# core/config.py
class Settings(BaseSettings):
    # Emergency kill switches
    disable_ai_features: bool = Field(default=False, description="Emergency: disable all AI features")
    disable_rrc_auto_download: bool = Field(default=False, description="Emergency: stop RRC scheduler")
    
    # ... rest of settings ...
```

**Usage in scheduler:**

```python
# main.py
@app.on_event("startup")
async def startup_event():
    scheduler = AsyncIOScheduler()
    
    async def download_rrc_if_enabled():
        if settings.disable_rrc_auto_download:
            logger.warning("RRC auto-download is disabled via kill switch")
            return
        
        await rrc_service.download_and_sync()
    
    scheduler.add_job(
        download_rrc_if_enabled,
        trigger="cron",
        day=1,
        hour=2,
        minute=0,
    )
    
    scheduler.start()
```

**Emergency rollback procedure:**

1. Set environment variable: `DISABLE_AI_FEATURES=true`
2. Restart Cloud Run service (no redeployment needed)
3. Feature is immediately disabled for all users
4. Investigate issue, fix, then re-enable