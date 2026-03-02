---
name: frontend-design
description: |
  Designs React UI with Tailwind utilities, Lucide icons, and tre-* brand colors.
  Use when: building components, styling pages, implementing responsive layouts, adding visual hierarchy
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Frontend Design Skill

Table Rock TX Tools uses a distinct visual identity centered on earth tones (navy, teal, tan, browns) with Oswald typography and Tailwind utility classes. All design decisions prioritize readability for non-technical land/revenue team users processing dense tabular data.

## Quick Start

### Branded Button Component

```tsx
// Component using tre-* brand colors
function PrimaryButton({ children, onClick, disabled }: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="bg-tre-navy text-white px-6 py-3 rounded-lg 
                 hover:bg-opacity-90 disabled:opacity-50 
                 transition-colors font-medium"
    >
      {children}
    </button>
  );
}
```

### Tool Card Layout

```tsx
// Dashboard tool card with consistent spacing
function ToolCard({ title, description, icon: Icon, route }: ToolCardProps) {
  return (
    <Link
      to={route}
      className="bg-white rounded-xl p-8 shadow-sm 
                 hover:shadow-md transition-shadow 
                 border border-gray-100"
    >
      <Icon className="w-12 h-12 text-tre-teal mb-4" />
      <h3 className="text-2xl font-semibold text-tre-navy mb-2">
        {title}
      </h3>
      <p className="text-gray-600 leading-relaxed">{description}</p>
    </Link>
  );
}
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| tre-* colors | Brand identity via Tailwind custom colors | `bg-tre-navy`, `text-tre-teal` |
| Oswald font | Headers/UI text with weights 300-700 | `font-semibold`, `font-light` |
| Lucide React | Consistent icon set across all tools | `<FileText />`, `<Upload />` |
| Utility-first | Inline Tailwind classes, no separate CSS | `className="flex gap-4 p-6"` |
| Data-first | Design optimized for dense tables/forms | Large touch targets, clear labels |

## Common Patterns

### Status Badge Variants

**When:** Displaying job/processing status with semantic colors

```tsx
// StatusBadge.tsx color mapping
const variants = {
  success: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  info: 'bg-blue-100 text-blue-800',
  pending: 'bg-gray-100 text-gray-800',
};

// GOOD - Clear semantic meaning
<StatusBadge variant="success">Completed</StatusBadge>

// BAD - Using brand colors for status (confusing)
<span className="bg-tre-teal text-white">Completed</span>
```

### Responsive Grid Layouts

**When:** Building tool pages with multiple sections

```tsx
// GOOD - Mobile-first with consistent breakpoints
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {tools.map(tool => <ToolCard key={tool.id} {...tool} />)}
</div>

// BAD - Desktop-first with arbitrary breakpoints
<div className="grid grid-cols-3 sm:grid-cols-1 gap-4">
```

### Modal Backdrop Pattern

**When:** Creating dialogs that require focus

```tsx
// GOOD - Backdrop blur with ESC handling
<div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm 
               flex items-center justify-center z-50">
  <div className="bg-white rounded-xl p-8 max-w-lg w-full shadow-2xl">
    {children}
  </div>
</div>

// BAD - No backdrop, poor visual hierarchy
<div className="fixed top-20 left-20 bg-white p-4">
```

## WARNING: Generic AI Aesthetics

**The Problem:**
AI often suggests bland, overused design patterns that make applications indistinguishable.

**Why This Breaks:**
1. Users lose visual identity and trust
2. Generic fonts/colors don't reinforce brand
3. Cookie-cutter layouts lack purpose

**The Fix:**
- **Font:** Use Oswald (already configured), NOT Inter/Roboto
- **Colors:** Use tre-navy (#0e2431) for primary, NOT generic blues
- **Icons:** Use Lucide React's outline style, NOT filled FontAwesome
- **Layout:** Follow existing tool-per-module grid patterns

## See Also

- [aesthetics](references/aesthetics.md) - Typography, color system, visual identity
- [components](references/components.md) - UI component styling patterns
- [layouts](references/layouts.md) - Page structure and responsive grids
- [motion](references/motion.md) - Transitions and micro-interactions
- [patterns](references/patterns.md) - Design anti-patterns and solutions

## Related Skills

- **react** - Component architecture and hooks
- **typescript** - Interface definitions for component props
- **tailwind** - Utility class configuration and custom colors
- **vite** - Asset handling and CSS processing