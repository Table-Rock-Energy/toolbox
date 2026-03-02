---
name: node
description: |
  Manages Node 20+ runtime and npm package dependencies for Vite 7 + React 19 frontend
  Use when: installing packages, updating dependencies, debugging module resolution, managing package.json scripts, or troubleshooting npm/node version issues
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Node Skill

This project uses **Node 20+** exclusively for the frontend (Vite dev server, React build toolchain). The backend is Python (FastAPI). All Node operations occur in `toolbox/frontend/`. Never mix Node package management with Python dependencies.

## Quick Start

### Install Dependencies

```bash
cd toolbox/frontend
npm install
```

### Run Dev Server (Vite)

```bash
cd toolbox/frontend
npm run dev
# OR from toolbox/ root:
make dev-frontend
```

### Add a Package

```bash
cd toolbox/frontend
npm install lucide-react
# For dev dependencies:
npm install --save-dev @types/node
```

### Build for Production

```bash
cd toolbox/frontend
npm run build  # Outputs to dist/
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| **package.json** | Dependency manifest + scripts | `"scripts": { "dev": "vite" }` |
| **package-lock.json** | Exact dependency tree (commit this) | Auto-generated, ensures reproducible installs |
| **node_modules/** | Installed packages (never commit) | `.gitignore` includes `node_modules/` |
| **npm scripts** | Task automation via `npm run [script]` | `npm run build` → runs `vite build` |
| **Peer dependencies** | Required by installed packages (auto-install in npm 7+) | React 19 required by lucide-react |

## Common Patterns

### Adding TypeScript Types for a Library

**When:** Installing a library that lacks built-in TypeScript definitions

```bash
# Install runtime package
npm install firebase

# Check if types are needed
npx tsc --noEmit  # If errors appear, install types:
npm install --save-dev @types/firebase
```

### Updating Dependencies (Security Patches)

**When:** GitHub Dependabot alerts or `npm audit` warnings

```bash
# Check for vulnerabilities
npm audit

# Auto-fix non-breaking updates
npm audit fix

# For breaking changes, update manually
npm install package@latest
npm test  # Verify nothing broke
```

### Debugging Module Resolution Issues

**When:** Import errors like "Cannot find module 'X'"

```bash
# 1. Clear cache + reinstall
rm -rf node_modules package-lock.json
npm install

# 2. Check if module exists
ls node_modules/[package-name]

# 3. Verify import path matches package exports
# Read package.json "exports" field:
cat node_modules/[package-name]/package.json | grep exports
```

### Running Scripts from Root Directory (via Makefile)

**When:** Working in `toolbox/` but need to run frontend commands

```bash
# Makefile handles directory navigation
make install-frontend  # Runs: cd frontend && npm install
make dev-frontend      # Runs: cd frontend && npm run dev
make lint              # Runs linters for both frontend + backend
```

## See Also

- [patterns](references/patterns.md) - Dependency management, script patterns
- [types](references/types.md) - TypeScript configuration, type definitions
- [modules](references/modules.md) - ESM vs CommonJS, barrel exports
- [errors](references/errors.md) - Common npm/node errors and fixes

## Related Skills

- **vite** - Dev server and build configuration
- **react** - Component library requiring Node toolchain
- **typescript** - Type checking integrated with Node build
- **frontend-design** - UI patterns built with Node-packaged tools

## Documentation Resources

> Fetch latest Node.js documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "nodejs documentation"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/websites/nodejs.org` _(prefer official documentation at nodejs.org)_

**Recommended Queries:**
- "node esm modules best practices"
- "node package json exports field"
- "npm workspace monorepo setup"