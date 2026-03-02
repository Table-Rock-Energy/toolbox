# Build Optimization Reference

## Contents
- Production Build Process
- Code Splitting Strategies
- Tree Shaking
- Asset Optimization
- Performance Budgets

---

## Production Build Process

### Build Command

```bash
# From toolbox/frontend/
npm run build

# Output:
# vite v7.x.x building for production...
# transforming...
# ✓ 1234 modules transformed.
# rendering chunks...
# dist/index.html                   0.45 kB
# dist/assets/index-a1b2c3d4.js    123.45 kB │ gzip: 45.67 kB
# dist/assets/vendor-e5f6g7h8.js   234.56 kB │ gzip: 78.90 kB
# ✓ built in 12.34s
```

**Deployed by:** FastAPI serves `frontend/dist/index.html` as root, static assets from `dist/assets/`.

### Build Configuration

```typescript
// toolbox/frontend/vite.config.ts
build: {
  outDir: 'dist', // Output directory
  sourcemap: false, // Disable sourcemaps in production (security)
  minify: 'esbuild', // Fast minification (default)
  target: 'es2020', // Browser target (matches tsconfig)
  cssCodeSplit: true, // Split CSS per route/chunk
  rollupOptions: {
    output: {
      manualChunks: {
        'firebase': ['firebase/app', 'firebase/auth'],
        'lucide': ['lucide-react'],
        'vendor': ['react', 'react-dom', 'react-router-dom'],
      },
    },
  },
}
```

**Why `sourcemap: false`?** Prevents source code exposure in production. Enable for debugging: `sourcemap: 'hidden'` (maps not referenced in JS).

---

## Code Splitting Strategies

### Automatic Route-Based Splitting

```tsx
// toolbox/frontend/src/App.tsx
import { lazy, Suspense } from 'react';

// Lazy-load route components
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Extract = lazy(() => import('./pages/Extract'));
const Proration = lazy(() => import('./pages/Proration'));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/extract" element={<Extract />} />
        <Route path="/proration" element={<Proration />} />
      </Routes>
    </Suspense>
  );
}
```

**Result:** Each route becomes a separate chunk, loaded on-demand.

**Bundle output:**
- `index.js` (main entry, router setup)
- `Dashboard-a1b2c3.js` (loaded when visiting `/`)
- `Extract-d4e5f6.js` (loaded when visiting `/extract`)
- `Proration-g7h8i9.js` (loaded when visiting `/proration`)

### Manual Chunk Splitting (Table Rock Tools)

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: (id) => {
        // Firebase libraries (auth, firestore)
        if (id.includes('firebase')) {
          return 'firebase';
        }
        
        // Lucide icons (400+ icons, tree-shakeable)
        if (id.includes('lucide-react')) {
          return 'lucide';
        }
        
        // Core React libraries
        if (id.includes('node_modules/react') || 
            id.includes('node_modules/react-dom') ||
            id.includes('node_modules/react-router')) {
          return 'vendor';
        }
        
        // Everything else in main bundle
      },
    },
  },
}
```

**Why split Firebase?** Large bundle (100+ kB), rarely changes → better caching.

**Why split Lucide?** Tree-shakeable, but still 50+ kB when importing many icons.

### WARNING: Over-Splitting

**The Problem:**

```typescript
// BAD - Too granular, creates 100+ chunks
manualChunks: (id) => {
  if (id.includes('node_modules')) {
    return id.split('node_modules/')[1].split('/')[0]; // One chunk per package
  }
}
```

**Why This Breaks:**
1. HTTP/2 multiplexing has limits (browser cap at ~100 concurrent requests)
2. Each chunk has overhead (module wrappers, import statements)
3. Slower initial load (100 requests vs 5)

**The Fix:**

```typescript
// GOOD - Group related packages
manualChunks: {
  'ui': ['lucide-react', '@radix-ui/react-dialog', '@headlessui/react'],
  'vendor': ['react', 'react-dom', 'react-router-dom'],
  'firebase': ['firebase/app', 'firebase/auth'],
}
```

**Rule of thumb:** 3-7 chunks total (1 main + 2-6 vendor chunks).

---

## Tree Shaking

### How Tree Shaking Works

Vite/Rollup removes unused exports during build:

```typescript
// utils/helpers.ts exports 10 functions
export { formatDate, parseCSV, validateEmail, ... };

// Component only imports one
import { formatDate } from './utils/helpers';

// Build result: Only formatDate included in bundle
```

**Requirements:**
1. ES modules (`import/export`, not `require()`)
2. Side-effect-free code (no module-level mutations)
3. `package.json` with `"sideEffects": false`

### Ensuring Tree Shaking

```json
// toolbox/frontend/package.json
{
  "sideEffects": false,
  // Or specify files with side effects
  "sideEffects": [
    "*.css",
    "src/lib/firebase.ts"
  ]
}
```

**Files with side effects:**
- CSS imports (`import './index.css'`)
- Firebase initialization (`initializeApp()` at module level)
- Polyfills (`import 'core-js/stable'`)

### WARNING: Import Entire Library

**The Problem:**

```typescript
// BAD - Imports ALL Lucide icons (~400 icons, 200+ kB)
import * as Icons from 'lucide-react';

function Header() {
  return <Icons.Menu />;
}
```

**Why This Breaks:**
1. Tree shaking fails (wildcard import considered "used")
2. Bundle includes all icons, not just `Menu`
3. 200 kB → 50 kB wasted

**The Fix:**

```typescript
// GOOD - Named imports, tree-shakeable
import { Menu, Home, Settings } from 'lucide-react';

function Header() {
  return <Menu />;
}
```

**Verify tree shaking:**

```bash
# Build and check bundle size
npm run build

# Search for unused icons in bundle
grep -r "XCircle" dist/assets/*.js
# If not imported, should not appear
```

---

## Asset Optimization

### Image Optimization

```typescript
// Import images as URLs (Vite handles optimization)
import logoUrl from './assets/logo.png';

function Header() {
  return <img src={logoUrl} alt="Table Rock Energy" />;
}

// In production:
// - Images <10kB inlined as base64
// - Larger images hashed and copied to dist/assets/
```

**File naming in build:**
- `logo.png` → `logo-a1b2c3d4.png` (content hash for cache busting)

### CSS Optimization

```typescript
// vite.config.ts
build: {
  cssCodeSplit: true, // Each route gets own CSS file
  cssMinify: 'esbuild', // Minify CSS (default)
}
```

**Tailwind purging (automatic):**

```javascript
// tailwind.config.js
module.exports = {
  content: ['./src/**/*.{ts,tsx}'], // Scans for class names
  // Unused classes removed in production build
};
```

**Result:** Tailwind CSS 3.x base is ~3 MB, purged build is ~10-20 kB.

### Font Loading

```css
/* src/index.css - Preconnect to Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;500;700&display=swap');
```

**DO:** Use `&display=swap` to prevent FOIT (Flash of Invisible Text).
**DON'T:** Self-host Google Fonts unless you need offline support—CDN is faster.

---

## Performance Budgets

### Bundle Size Analysis

```bash
# Install rollup-plugin-visualizer
npm install -D rollup-plugin-visualizer

# Add to vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer';

plugins: [
  react(),
  visualizer({ open: true, gzipSize: true }),
]

# Build and open stats.html
npm run build
```

**What to look for:**
- Largest chunks (should be vendor code, not app code)
- Duplicate dependencies (same package in multiple chunks)
- Unexpected large modules (misconfigured tree shaking)

### Size Thresholds

| Chunk | Uncompressed | Gzipped | Action |
|-------|--------------|---------|--------|
| Main bundle | <100 kB | <30 kB | ✅ Good |
| Main bundle | 100-200 kB | 30-60 kB | ⚠️ Consider splitting |
| Main bundle | >200 kB | >60 kB | 🚨 Split immediately |
| Vendor chunk | <300 kB | <100 kB | ✅ Good |
| Individual route | <50 kB | <15 kB | ✅ Good |

**Table Rock Tools current bundle (reference):**
- Main: ~80 kB (gzip ~25 kB)
- Vendor (React): ~130 kB (gzip ~40 kB)
- Firebase: ~90 kB (gzip ~28 kB)
- Lucide: ~45 kB (gzip ~12 kB)

**Total initial load: ~350 kB (gzip ~105 kB)** ✅ Under 200 kB gzipped threshold.