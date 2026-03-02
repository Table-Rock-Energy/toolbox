# Node Errors Reference

## Contents
- Module Not Found Errors
- Version Conflicts
- Peer Dependency Errors
- Build Failures
- Runtime Errors
- Permission Errors

---

## Module Not Found Errors

### ERROR: Cannot find module 'X'

**Symptoms:**

```bash
Error: Cannot find module 'react'
Require stack:
- /toolbox/frontend/src/main.tsx
```

**Causes:**
1. Package not installed (`npm install` skipped)
2. `node_modules/` deleted or corrupted
3. Wrong directory (`package.json` not in current directory)

**Fix:**

```bash
# 1. Verify you're in the frontend directory
cd toolbox/frontend

# 2. Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# 3. Check if module exists
ls node_modules/react  # Should show react's files
```

**Prevention:** Always run `npm install` after pulling changes that update `package.json` or `package-lock.json`.

---

### ERROR: Module not found: Can't resolve './Component'

**Symptoms:**

```bash
# Vite build error
✘ [ERROR] Could not resolve "./DataTable"

    src/pages/Dashboard.tsx:5:25:
      5 │ import { DataTable } from './DataTable';
```

**Causes:**
1. File doesn't exist at that path
2. Case sensitivity mismatch (`dataTable.tsx` vs `DataTable.tsx`)
3. Missing file extension in ESM context

**Fix:**

```bash
# 1. Check if file exists
ls src/pages/DataTable.tsx

# 2. Verify case matches exactly (macOS is case-insensitive, Linux is not)
git ls-files | grep -i datatable  # Shows actual filename in git

# 3. Fix import path
# BAD
import { DataTable } from './dataTable';  // ❌ Wrong case

# GOOD
import { DataTable } from './DataTable';  // ✓ Matches filename
```

**Prevention:** Use consistent naming (PascalCase for components). Enable ESLint rule `import/no-unresolved` to catch these at lint time.

---

## Version Conflicts

### ERROR: npm ERR! code ERESOLVE (Dependency Conflict)

**Symptoms:**

```bash
npm ERR! code ERESOLVE
npm ERR! ERESOLVE could not resolve
npm ERR! peer react@"^18.0.0" from lucide-react@0.300.0
npm ERR! node_modules/lucide-react
npm ERR!   lucide-react@"*" from the root project
npm ERR! 
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^18.0.0" from lucide-react@0.300.0
npm ERR! 
npm ERR! Fix the upstream dependency conflict, or retry
npm ERR! this command with --force or --legacy-peer-deps
```

**Causes:**
1. Package requires React 18, you have React 19
2. Peer dependency version range doesn't overlap with installed version

**Fix:**

```bash
# Option 1: Use --legacy-peer-deps (ignores peer dependency checks)
npm install lucide-react --legacy-peer-deps

# Option 2: Wait for package to support React 19
# Check npm for newer version:
npm view lucide-react versions --json | tail

# Option 3: Downgrade React (NOT recommended for this project)
npm install react@18 react-dom@18
```

**Add to .npmrc to make --legacy-peer-deps permanent:**

```ini
# .npmrc
legacy-peer-deps=true
```

**When You Might Be Tempted:** When you know the package works with React 19 despite the peer dependency warning. Use `--legacy-peer-deps` cautiously—it can hide real incompatibilities.

---

### ERROR: Incompatible Node Version

**Symptoms:**

```bash
error vite@7.0.0: The engine "node" is incompatible with this module.
Expected version "^20.0.0 || ^22.0.0". Got "18.16.0"
```

**Causes:**
1. Node version too old for Vite 7
2. Using system Node instead of project-required version

**Fix:**

```bash
# 1. Check current Node version
node -v  # Should show v20.x.x or v22.x.x

# 2. Upgrade Node (macOS with Homebrew)
brew install node@20

# 3. Use nvm to manage multiple versions
nvm install 20
nvm use 20

# 4. Verify version
node -v  # Should show v20.x.x
```

**Prevention:** Document required Node version in `package.json`:

```json
{
  "engines": {
    "node": ">=20.0.0"
  }
}
```

---

## Peer Dependency Errors

### ERROR: Missing Peer Dependency

**Symptoms:**

```bash
npm WARN react-dom@19.0.0 requires a peer of react@19.0.0 but none is installed.
```

**Causes:**
1. Installed `react-dom` without `react`
2. Versions don't match (React 18 + React-DOM 19)

**Fix:**

```bash
# Install matching versions
npm install react@19.0.0 react-dom@19.0.0
```

**Prevention:** Always install peer dependencies together:

```bash
npm install react react-dom  # Installs matching versions
```

---

## Build Failures

### ERROR: Vite Build Out of Memory

**Symptoms:**

```bash
<--- Last few GCs --->
[1:0x103800000]   234567 ms: Mark-sweep 2048.3 (2082.5) -> 2048.2 (2083.5) MB
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
```

**Causes:**
1. Large dependencies (e.g., entire Firebase SDK)
2. Circular imports
3. Memory leak in build plugin

**Fix:**

```bash
# Option 1: Increase Node memory limit
NODE_OPTIONS="--max-old-space-size=4096" npm run build

# Option 2: Use tree-shaking to reduce bundle size
# Import only what you need:
# BAD
import * as firebase from 'firebase';  // ❌ Loads entire SDK

# GOOD
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
```

**Add to package.json:**

```json
{
  "scripts": {
    "build": "NODE_OPTIONS='--max-old-space-size=4096' vite build"
  }
}
```

---

### ERROR: TypeScript Errors in node_modules

**Symptoms:**

```bash
node_modules/some-package/dist/index.d.ts:45:12 - error TS2304:
Cannot find name 'RequestInit'.
```

**Causes:**
1. Package has broken TypeScript definitions
2. Missing `@types/node` for Node.js globals

**Fix:**

```bash
# Install Node types
npm install --save-dev @types/node

# If error persists, exclude node_modules from type checking
# tsconfig.json
{
  "compilerOptions": {
    "skipLibCheck": true  // Skip type checking in node_modules
  }
}
```

**Why `skipLibCheck: true` is safe:** It skips type checking third-party `.d.ts` files but still checks your own code. This prevents broken types in dependencies from failing your build.

---

## Runtime Errors

### ERROR: exports is not defined in ES module scope

**Symptoms:**

```bash
ReferenceError: exports is not defined in ES module scope
This file is being treated as an ES module because it has a .js file extension
and 'package.json' contains "type": "module".
```

**Causes:**
1. CommonJS syntax (`module.exports`) in an ESM file
2. Bundler didn't transpile a CommonJS dependency

**Fix:**

```typescript
// BAD - CommonJS syntax
module.exports = { foo: 'bar' };  // ❌ In ESM mode

// GOOD - ESM syntax
export default { foo: 'bar' };
```

**If the error is in a dependency:**

```bash
# Check if package has an ESM version
npm view some-package exports

# If not, use Vite plugin to pre-bundle it
# vite.config.ts
export default defineConfig({
  optimizeDeps: {
    include: ['some-package']  // Forces Vite to pre-bundle as ESM
  }
});
```

---

### ERROR: process is not defined

**Symptoms:**

```bash
Uncaught ReferenceError: process is not defined
    at node_modules/some-package/index.js:12
```

**Causes:**
1. Package expects Node.js global `process` in browser
2. Missing Vite env variable replacement

**Fix:**

```typescript
// vite.config.ts - Define globals for browser
export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV)
  }
});
```

**Or use Vite's built-in env variables:**

```typescript
// BAD - process.env in browser code
if (process.env.NODE_ENV === 'production') {  // ❌ process undefined

// GOOD - Use Vite's import.meta.env
if (import.meta.env.PROD) {  // ✓ Replaced at build time
```

---

## Permission Errors

### ERROR: EACCES: permission denied

**Symptoms:**

```bash
npm ERR! code EACCES
npm ERR! syscall mkdir
npm ERR! path /usr/local/lib/node_modules
npm ERR! errno -13
npm ERR! Error: EACCES: permission denied, mkdir '/usr/local/lib/node_modules'
```

**Causes:**
1. Trying to install global packages without sudo
2. npm prefix owned by root

**Fix:**

```bash
# Option 1: Use sudo (quick fix, not recommended)
sudo npm install -g vite

# Option 2: Change npm prefix to user directory (better)
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'

# Add to PATH in ~/.zshrc or ~/.bashrc
export PATH=~/.npm-global/bin:$PATH

# Reload shell
source ~/.zshrc

# Now install without sudo
npm install -g vite
```

**Prevention:** Never run `npm install` with `sudo` for project dependencies. Only global packages (`-g`) should use sudo, and only if you haven't changed the npm prefix.

---

## Cross-Skill Integration

### With Vite Skill

Vite build errors often originate from module resolution or bundler config. See the **vite** skill for `optimizeDeps` and `resolve.alias` troubleshooting.

### With TypeScript Skill

TypeScript errors in `node_modules/` can be silenced with `skipLibCheck`. See the **typescript** skill for `tsconfig.json` compiler options.

### With React Skill

React runtime errors (hooks, state) often appear as Node errors when SSR is involved. See the **react** skill for debugging patterns.