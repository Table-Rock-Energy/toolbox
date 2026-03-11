# Integration Reference

## Contents
- Vite + React 19
- Vite + TypeScript Strict Mode
- Vite + Tailwind CSS
- Vite + Firebase Auth
- Vite + FastAPI (Production Static Serving)
- Plugin Compatibility

---

## Vite + React 19

`@vitejs/plugin-react` v5 supports React 19 + Fast Refresh out of the box. No configuration changes needed for React 19 upgrade.

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(), // Enables Fast Refresh + JSX transform
  ],
});
```

**DO:** Use `react-jsx` transform (configured in `tsconfig.app.json` via `"jsx": "react-jsx"`). This means NO `import React from 'react'` at the top of every file.

**DON'T:**
```tsx
// BAD - Unnecessary with react-jsx transform
import React from 'react';
export default function Component() { ... }
```

See the **react** skill for component patterns.

---

## Vite + TypeScript Strict Mode

`tsconfig.app.json` uses `"moduleResolution": "bundler"` — this is Vite-specific and differs from Node's `"node16"` resolution. It allows importing `.ts` files without extensions in source but NOT in runtime Node scripts.

```json
// frontend/tsconfig.app.json (current config)
{
  "compilerOptions": {
    "moduleResolution": "bundler",  // Vite-aware resolution
    "verbatimModuleSyntax": true,   // Enforces `import type` for type-only imports
    "noEmit": true,                 // Vite handles emit, not tsc
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

**Build validation:** The build script `tsc -b && vite build` runs TypeScript check BEFORE bundling. If `tsc` fails, the Vite build never runs.

```bash
# TypeScript errors block production builds
npm run build
# Error: src/pages/Extract.tsx(42,5): TS2322 ...
# → Fix TypeScript errors before deploying
```

See the **typescript** skill for strict mode patterns.

---

## Vite + Tailwind CSS

Tailwind 3.x uses PostCSS. Vite handles PostCSS automatically when `postcss.config.js` exists.

```javascript
// frontend/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**How Vite handles it:** In dev, PostCSS transforms run on each CSS file change via HMR. In production builds, Tailwind purges unused classes based on `content` paths in `tailwind.config.js`.

**WARNING:** If `content` paths miss a file, production build will strip styles that worked in dev.

```javascript
// frontend/tailwind.config.js — ensure all source files are included
export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}', // Must match ALL files using Tailwind classes
  ],
};
```

See the **tailwind** skill for `tre-*` brand color usage.

---

## Vite + Firebase Auth

Firebase's modular SDK (`firebase/app`, `firebase/auth`) is tree-shaken by Vite's Rollup bundler. Only imported Firebase modules are included in the bundle.

```typescript
// frontend/src/lib/firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

**Bundle optimization:** Firebase adds ~150KB to the bundle. Split it into its own chunk:

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        firebase: ['firebase/app', 'firebase/auth'],
      },
    },
  },
},
```

See the **firebase** skill for auth flow and token verification.

---

## Vite + FastAPI (Production Static Serving)

In production, FastAPI serves the Vite-built `dist/` as static files. The Docker container handles this in a single process (no separate Vite server).

```python
# backend/app/main.py — production static file serving
from fastapi.staticfiles import StaticFiles
import os

dist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist')
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
```

**Flow:**
- Dev: Browser → Vite (5173) → Proxy `/api` → FastAPI (8000)
- Production: Browser → FastAPI (8080) → Serves `dist/index.html` for all non-API routes

**IMPORTANT:** All React Router routes (`/extract`, `/title`, etc.) must be handled by `index.html` (SPA fallback). The `html=True` parameter in `StaticFiles` enables this.

---

## Plugin Compatibility

| Plugin | Version | Purpose | Notes |
|--------|---------|---------|-------|
| `@vitejs/plugin-react` | ^5.1.1 | React Fast Refresh + JSX | No `@babel/core` needed (uses SWC) |
| `autoprefixer` | ^10.4 | CSS vendor prefixes | Via PostCSS |
| `tailwindcss` | ^3.4 | CSS framework | PostCSS plugin, not Vite plugin |

**AVOID:** `@vitejs/plugin-react-swc` — it's a separate package and conflicts with `@vitejs/plugin-react`. The current `@vitejs/plugin-react` v5 already uses SWC by default.
