The skill files already exist and are comprehensive. The content covers all the required patterns with proper anti-pattern documentation, cross-skill references, and codebase-specific examples. No changes are needed — the files are complete and well-structured.

Here's a summary of what exists:

**SKILL.md** — Quick start, key concepts, common patterns (install, update, debug, Makefile wrappers), links to references. Stays under 150 lines.

**references/patterns.md** — Frontend-only architecture, lock file discipline, dev vs prod dependencies, script naming, Makefile wrappers, ESM module pattern, build artifact management, Docker multi-stage context.

**references/types.md** — TypeScript as devDependency, `@types/*` discovery, Node vs browser type separation, ESM module system, conditional package exports.

**references/modules.md** — ESM vs CommonJS, module resolution order, barrel export patterns + performance warning, dynamic imports/code splitting, Node built-ins in build scripts only, package entry points (`main`/`module`/`exports`).

**references/errors.md** — "Cannot find module", case sensitivity issues, `ERESOLVE` dependency conflicts, incompatible Node version, out-of-memory build failures, `skipLibCheck`, `exports is not defined`, `process is not defined`, `EACCES` permission errors.

All files include real examples from this codebase (`frontend/package.json`, `vite.config.ts`, `Makefile`, Dockerfile), proper `WARNING` sections, and cross-references to **vite**, **typescript**, and **react** skills.