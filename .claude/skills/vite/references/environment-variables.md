# Environment Variables Reference

## Contents
- Variable Naming and Access
- Development vs Production
- Security Best Practices
- Common Patterns

---

## Variable Naming and Access

### Vite Prefix Requirement

```bash
# .env (in toolbox/frontend/)

# ✅ GOOD - VITE_ prefix, accessible in client
VITE_API_BASE_URL=/api
VITE_FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# ❌ BAD - No VITE_ prefix, NOT accessible in client
API_BASE_URL=/api  # undefined in browser
NODE_ENV=production  # Use import.meta.env.MODE instead
```

**Accessing in code:**

```typescript
// toolbox/frontend/src/utils/api.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL;
const FIREBASE_KEY = import.meta.env.VITE_FIREBASE_API_KEY;

// TypeScript autocomplete (optional)
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_FIREBASE_API_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

### Built-in Variables

```typescript
// Available without VITE_ prefix
import.meta.env.MODE       // 'development' or 'production'
import.meta.env.DEV        // boolean (true in dev)
import.meta.env.PROD       // boolean (true in production)
import.meta.env.BASE_URL   // '/' (configured in vite.config.ts)
import.meta.env.SSR        // boolean (true during SSR, false for SPA)
```

**Use case:**

```typescript
// Conditional logging in dev only
if (import.meta.env.DEV) {
  console.log('Debug: API response', data);
}

// Feature flag for production
const ENABLE_ANALYTICS = import.meta.env.PROD;
```

---

## Development vs Production

### File Structure

```
toolbox/frontend/
├── .env                 # Committed defaults (non-secret)
├── .env.local           # Git-ignored local overrides
├── .env.development     # Dev-only vars (npm run dev)
├── .env.production      # Prod-only vars (npm run build)
└── .gitignore           # Ignores .env.local, .env.*.local
```

**Load order (highest priority first):**
1. `.env.[mode].local` (e.g., `.env.production.local`)
2. `.env.[mode]` (e.g., `.env.production`)
3. `.env.local`
4. `.env`

### Example Setup

```bash
# .env (committed to git, shared defaults)
VITE_API_BASE_URL=/api

# .env.development (committed, dev-specific)
VITE_API_BASE_URL=http://localhost:8000/api

# .env.production (committed, prod-specific)
VITE_API_BASE_URL=https://tools.tablerocktx.com/api

# .env.local (git-ignored, developer overrides)
VITE_API_BASE_URL=http://192.168.1.100:8000/api
```

**When building:**

```bash
# Uses .env + .env.development
npm run dev

# Uses .env + .env.production
npm run build
```

### Dynamic Backend URL

```typescript
// toolbox/frontend/src/utils/api.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiClient {
  private baseUrl: string;

  constructor() {
    // In dev: http://localhost:8000/api (from .env.development)
    // In prod: /api (relative, served from same origin)
    this.baseUrl = API_BASE;
  }

  async upload(endpoint: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      body: formData,
    });
    
    return response.json();
  }
}
```

**Production note:** FastAPI serves frontend from `dist/`, so `/api` is same-origin (no CORS).

---

## Security Best Practices

### WARNING: Secrets in Client Code

**The Problem:**

```bash
# BAD - Private API key in frontend .env
VITE_STRIPE_SECRET_KEY=sk_live_XXXXXXXXXXXXXXXXXXXXXX
```

**Why This Breaks:**
1. All `VITE_` variables are **embedded in the bundle** (visible in `dist/assets/*.js`)
2. Users can inspect source, extract secrets
3. Secrets can be used to impersonate your backend

**The Fix:**

```bash
# GOOD - Use public keys in frontend
VITE_STRIPE_PUBLIC_KEY=pk_live_XXXXXXXXXXXXXXXXXXXXXX

# Secret keys ONLY in backend .env (not VITE_ prefixed)
# toolbox/backend/.env
STRIPE_SECRET_KEY=sk_live_XXXXXXXXXXXXXXXXXXXXXX
```

**Safe for frontend:**
- Firebase API keys (public, restricted by domain)
- Google Maps API keys (restricted by domain/IP)
- Public analytics IDs (Google Analytics, Segment)

**NEVER in frontend:**
- Database credentials
- API secret keys (Stripe, Twilio)
- GCS service account keys

### Firebase Config (Public, Safe)

```typescript
// toolbox/frontend/src/lib/firebase.ts
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  // These are PUBLIC and safe to expose
  // Security rules on Firestore/Storage enforce access control
};
```

**Why this is safe:** Firebase API keys are restricted by domain in console settings.

### Environment Variable Validation

```typescript
// toolbox/frontend/src/lib/firebase.ts
const requiredEnvVars = [
  'VITE_FIREBASE_API_KEY',
  'VITE_FIREBASE_AUTH_DOMAIN',
  'VITE_FIREBASE_PROJECT_ID',
] as const;

for (const varName of requiredEnvVars) {
  if (!import.meta.env[varName]) {
    throw new Error(`Missing required environment variable: ${varName}`);
  }
}
```

**When to validate:** App initialization (before rendering).

---

## Common Patterns

### Conditional Features

```typescript
// Enable features based on environment
const FEATURES = {
  analytics: import.meta.env.PROD,
  debugTools: import.meta.env.DEV,
  mockApi: import.meta.env.VITE_USE_MOCK_API === 'true',
};

if (FEATURES.analytics) {
  initGoogleAnalytics();
}

if (FEATURES.debugTools) {
  mountReactQueryDevtools();
}
```

### API Client Factory

```typescript
// toolbox/frontend/src/utils/api.ts
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || import.meta.env.VITE_API_BASE_URL || '/api';
  }

  // ...methods
}

// Singleton instance
export const apiClient = new ApiClient();

// Test instance (override baseUrl)
export const createTestClient = (mockUrl: string) => new ApiClient(mockUrl);
```

**Use case:** Testing with different backend URLs, mocking API in Storybook.

### Mode-Specific Behavior

```typescript
// Show detailed errors in dev, generic in prod
function handleError(error: Error) {
  if (import.meta.env.DEV) {
    console.error('Detailed error:', error.stack);
    alert(`Error: ${error.message}`); // Show to developer
  } else {
    console.error('Error occurred'); // Log generic message
    alert('Something went wrong. Please try again.'); // User-friendly
  }
}
```

### TypeScript Type Safety

```typescript
// toolbox/frontend/src/vite-env.d.ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_FIREBASE_API_KEY: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN: string;
  readonly VITE_FIREBASE_PROJECT_ID: string;
  readonly MODE: 'development' | 'production';
  readonly DEV: boolean;
  readonly PROD: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

**Benefit:** TypeScript autocomplete for `import.meta.env.VITE_*`.