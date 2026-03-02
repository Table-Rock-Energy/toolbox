---
name: tailwind
description: |
  Applies Tailwind CSS with custom tre-* brand colors and utility classes for Table Rock TX Tools.
  Use when: styling React components, implementing brand-consistent UI, creating responsive layouts, or needing utility-first CSS
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Tailwind Skill

Table Rock TX Tools uses Tailwind CSS 3.x with custom brand colors (`tre-navy`, `tre-teal`, `tre-tan`, `tre-brown-*`) defined in `toolbox/frontend/tailwind.config.js`. All styling is inline utility classes—NO separate CSS files per component. Components use Tailwind for responsive layouts, branded color schemes, and consistent spacing/typography.

## Quick Start

### Custom Brand Colors

```tsx
// toolbox/frontend/src/components/Sidebar.tsx
<div className="h-screen w-64 bg-tre-navy text-white flex flex-col">
  <div className="p-6 border-b border-tre-teal/20">
    <h1 className="text-2xl font-bold text-tre-teal">Table Rock Tools</h1>
  </div>
  <nav className="flex-1 p-4">
    <a className="flex items-center gap-3 px-4 py-2 rounded hover:bg-tre-teal/10 text-tre-tan">
      Dashboard
    </a>
  </nav>
</div>
```

### Responsive Grid with Status Badges

```tsx
// toolbox/frontend/src/pages/Dashboard.tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {tools.map(tool => (
    <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
      <h3 className="text-lg font-semibold text-tre-navy mb-2">{tool.name}</h3>
      <span className="inline-block px-2 py-1 text-xs rounded bg-tre-teal/20 text-tre-navy">
        {tool.status}
      </span>
    </div>
  ))}
</div>
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Custom Colors | `tre-*` prefix for brand colors | `bg-tre-navy text-tre-teal` |
| Inline Utilities | All styling via class names, no CSS files | `className="flex items-center gap-4"` |
| Responsive Breakpoints | `md:`, `lg:` prefixes | `grid-cols-1 md:grid-cols-2` |
| Opacity Modifiers | `/10`, `/20` for transparency | `bg-tre-teal/10` |
| State Variants | `hover:`, `focus:`, `disabled:` | `hover:bg-tre-teal/10` |

## Common Patterns

### Navigation with Active States

**When:** Sidebar navigation with visual feedback for active routes

```tsx
// toolbox/frontend/src/components/Sidebar.tsx
const isActive = location.pathname === '/extract';
<a className={`flex items-center gap-3 px-4 py-2 rounded transition-colors ${
  isActive 
    ? 'bg-tre-teal/20 text-tre-teal' 
    : 'text-white hover:bg-tre-teal/10'
}`}>
  <FileText className="w-5 h-5" />
  Extract
</a>
```

### Modal Overlays

**When:** Dialogs with backdrop blur and focus trapping

```tsx
// toolbox/frontend/src/components/Modal.tsx
<div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
  <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
    <h2 className="text-xl font-semibold text-tre-navy mb-4">{title}</h2>
    {children}
  </div>
</div>
```

### Form Inputs with Brand Colors

**When:** Consistent form styling across tools

```tsx
<input
  type="text"
  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal focus:border-transparent"
  placeholder="Enter value..."
/>
```

## See Also

- [patterns](references/patterns.md) - Component styling patterns, color usage, responsive design
- [workflows](references/workflows.md) - Adding custom colors, theme customization, debugging utilities

## Related Skills

- **react** - For component structure and state management
- **typescript** - For component prop types and interfaces
- **frontend-design** - For layout and UX patterns
- **vite** - For Tailwind integration via PostCSS

## Documentation Resources

> Fetch latest Tailwind CSS documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "tailwind css"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/websites/tailwindcss.com` _(prefer website docs for Tailwind)_

**Recommended Queries:**
- "tailwind css utility classes reference"
- "tailwind css custom colors configuration"
- "tailwind css responsive design breakpoints"
- "tailwind css hover focus states"