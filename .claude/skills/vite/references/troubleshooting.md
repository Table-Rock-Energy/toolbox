# Troubleshooting Reference

## Contents
- Build Failures
- Dev Server Issues
- HMR Not Working
- Production Bugs
- Performance Problems

---

## Build Failures

### "Cannot find module" during build

```bash
# Error: Could not resolve "firebase/auth"
# Cause: Missing dependency or incorrect import

# Fix: Install the package
npm install firebase

# Verify package.json has correct version
cat package.json | grep firebase
```

### TypeScript Errors Block Build

```bash
# Error: TS2322: Type 'string' is not assignable to type 'number'
# Cause: Type mismatch in code

# Option 1: Fix the type error
const count: number = parseInt(input);

# Option 2: Temporarily disable strict checks (NOT RECOMMENDED)
# tsconfig.json
{
  "compilerOptions": {
    "strict": false  // DON'T DO THIS
  }
}
```

**DO:** Fix type errors instead of disabling strict mode. See **typescript** skill.

### Out of Memory during Build

```bash
# Error: JavaScript heap out of memory
# Cause: Large codebase, insufficient Node.js memory

# Fix: Increase Node.js heap size
NODE_OPTIONS=--max-old-space-size=4096 npm run build

# Or add to package.json scripts
"build": "NODE_OPTIONS=--max-old-space-size=4096 vite build"
```

**When this happens:** Projects with 1000+ components, large SVG imports, massive Tailwind config.

---

## Dev Server Issues

### Port 5173 Already in Use

```bash
# Error: Port 5173 is already in use
# Fix 1: Kill process on port
lsof -ti:5173 | xargs kill -9

# Fix 2: Use different port
npm run dev -- --port 3000

# Fix 3: Configure in vite.config.ts
server: {
  port: 3000,
}
```

### Proxy Not Working (CORS Errors)

```bash
# Error: Access to fetch at 'http://localhost:8000/api/extract' has been blocked by CORS
# Cause: Missing or incorrect proxy config

# Verify vite.config.ts has proxy
server: {
  proxy: {
    '/api': 'http://localhost:8000',
  },
}

# Verify fetch uses relative URL
fetch('/api/extract', { method: 'POST' });  // GOOD
fetch('http://localhost:8000/api/extract'); // BAD (bypasses proxy)
```

**Debug proxy:**

```typescript
// Add logging to proxy
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      configure: (proxy) => {
        proxy.on('proxyReq', (proxyReq, req, res) => {
          console.log('Proxying:', req.method, req.url, '→', proxyReq.path);
        });
      },
    },
  },
}
```

### Backend Not Running

```bash
# Error: [vite] http proxy error: ECONNREFUSED
# Cause: FastAPI backend not started

# Fix: Start backend
cd toolbox/backend
python3 -m uvicorn app.main:app --reload --port 8000

# Or use Makefile
make dev-backend
```

---

## HMR Not Working

### Changes Not Reflecting in Browser

**Symptom:** Edit component, save, no update in browser.

**Causes:**
1. File not tracked by Vite (outside `src/` directory)
2. Syntax error in file (check console for errors)
3. Module-level side effects breaking HMR

**Fix:**

```bash
# Check Vite console for errors
# Look for: [vite] error updating module

# Hard refresh browser
Cmd+Shift+R (macOS) or Ctrl+Shift+R (Windows)

# Restart dev server
Ctrl+C, then npm run dev
```

### HMR Causes Duplicate React Instances

**Symptom:** Hooks break with "Invalid hook call" error after HMR.

**Cause:** Multiple React instances loaded (one in main bundle, one in HMR module).

**Fix:**

```typescript
// vite.config.ts - Deduplicate React
resolve: {
  dedupe: ['react', 'react-dom'],
}
```

### Full Page Reload on Every Change

**Symptom:** HMR triggers full reload instead of hot update.

**Cause:**
1. Default exports missing for components
2. Files with module-level side effects

**Fix:**

```tsx
// BAD - Named export, full reload
export function DataTable() { ... }

// GOOD - Default export, HMR works
export default function DataTable() { ... }
```

---

## Production Bugs

### Works in Dev, Breaks in Production

**Symptom:** App works locally, fails after deployment.

**Common causes:**

1. **Environment variable missing:**

```bash
# .env.production not loaded in build

# Verify vars during build
npm run build | grep VITE_
# Should show VITE_API_BASE_URL, etc.
```

2. **Hardcoded localhost:**

```typescript
// BAD - Works in dev, fails in prod
const API_URL = 'http://localhost:8000/api';

// GOOD - Uses env var
const API_URL = import.meta.env.VITE_API_BASE_URL;
```

3. **Import.meta.env accessed after build:**

```typescript
// BAD - Undefined in built bundle
const config = JSON.parse(localStorage.getItem('config'));
const apiUrl = config.apiUrl || import.meta.env.VITE_API_BASE_URL;

// GOOD - Access at module load
const DEFAULT_API = import.meta.env.VITE_API_BASE_URL;
const config = JSON.parse(localStorage.getItem('config'));
const apiUrl = config.apiUrl || DEFAULT_API;
```

### Blank Page in Production

**Symptom:** `dist/index.html` loads, but page is blank.

**Causes:**

1. **Incorrect base path:**

```typescript
// vite.config.ts
base: '/', // Default, works for root domain

// If deployed to subdirectory:
base: '/tools/', // For https://example.com/tools/
```

2. **Console errors (check browser DevTools):**

```javascript
// Common error: Failed to load module "firebase/auth"
// Fix: Ensure dependencies installed before build
npm ci
npm run build
```

3. **CSP blocking scripts:**

```html
<!-- Backend response includes CSP header blocking inline scripts -->
<!-- Fix: Allow inline scripts or move to external file -->
Content-Security-Policy: script-src 'self' 'unsafe-inline'
```

---

## Performance Problems

### Slow Initial Load

**Symptom:** First page load takes 5+ seconds.

**Diagnosis:**

```bash
# Build and check bundle sizes
npm run build

# Look for large chunks (>200 kB gzipped)
dist/assets/index-abc123.js    543.21 kB │ gzip: 187.65 kB  ⚠️ TOO BIG
```

**Fix:** Code split large dependencies.

```typescript
// Before: All Firebase in main bundle
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

// After: Lazy-load Firebase per feature
const AuthProvider = lazy(() => import('./contexts/AuthContext'));
const FirestoreProvider = lazy(() => import('./contexts/FirestoreContext'));
```

**See:** [build-optimization](build-optimization.md) for code splitting strategies.

### Slow HMR (5+ seconds per change)

**Symptom:** Edit file, wait 5+ seconds for HMR update.

**Causes:**

1. **Large barrel exports:**

```typescript
// BAD - components/index.ts re-exports 50 components
export { DataTable } from './DataTable';
export { Modal } from './Modal';
// ... 48 more

// Importing one component forces Vite to process all 50
import { DataTable } from './components';

// GOOD - Direct imports
import { DataTable } from './components/DataTable';
```

2. **Circular dependencies:**

```typescript
// utils/api.ts imports utils/auth.ts
// utils/auth.ts imports utils/api.ts
// Vite rebuilds both on every change

// Fix: Extract shared code to third file
// utils/shared.ts
```

3. **Large dependencies in dev:**

```typescript
// vite.config.ts - Pre-bundle large deps
optimizeDeps: {
  include: ['firebase/app', 'firebase/auth', 'lucide-react'],
}
```

### Memory Leak in Dev Server

**Symptom:** Dev server slows down over time, eventually crashes.

**Cause:** HMR accumulating old modules in memory.

**Fix:**

```bash
# Restart dev server periodically
Ctrl+C, npm run dev

# Or use nodemon to auto-restart on file changes
npm install -D nodemon
nodemon --watch vite.config.ts --exec "npm run dev"
```

**Prevention:** Avoid module-level mutable state.

```typescript
// BAD - Leaks memory on HMR
let cache = {};
export function addToCache(key, value) {
  cache[key] = value; // Never garbage collected
}

// GOOD - Use React state or context
function useCache() {
  const [cache, setCache] = useState({});
  // Cleared on component unmount
}