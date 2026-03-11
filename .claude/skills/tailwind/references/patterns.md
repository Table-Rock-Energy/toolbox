# Tailwind Patterns Reference

## Contents
- Brand Color System
- Sidebar Patterns (Dark Background)
- Modal and Overlay Patterns
- Status and Badge Patterns
- Responsive Layout Patterns
- Typography with Oswald
- Anti-Patterns

---

## Brand Color System

Defined in `frontend/tailwind.config.js`. Use `tre-*` tokens — never hardcode hex values.

```javascript
// frontend/tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'tre-navy': '#0e2431',
        'tre-teal': '#90c5ce',
        'tre-tan': '#cab487',
        'tre-brown-dark': '#5b4825',
        'tre-brown-medium': '#775723',
        'tre-brown-light': '#966e35',
      },
      fontFamily: {
        'oswald': ['Oswald', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
```

**Opacity modifiers** are the primary tool for dark-on-dark hierarchy:

```tsx
// Borders, hover backgrounds, subtle tints — all via opacity
<div className="border-b border-tre-teal/20">     {/* 20% teal border */}
<div className="hover:bg-tre-navy/50">             {/* 50% navy hover */}
<div className="bg-tre-teal/20 text-tre-teal">    {/* active state tint */}
```

---

## Sidebar Patterns (Dark Background)

The sidebar (`Sidebar.tsx`) establishes the core dark-background patterns used throughout.

### Active Nav Link

```tsx
// GOOD — actual pattern from Sidebar.tsx
const isActive = location.pathname.startsWith(path)
return `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${
  isActive
    ? 'bg-tre-teal/20 text-tre-teal border-l-4 border-tre-teal'
    : 'text-gray-300 hover:bg-tre-navy/50 hover:text-tre-teal'
}`
```

Note: active state uses `border-l-4 border-tre-teal` left accent, not just color change.

### Collapsed Icon-Only Mode

```tsx
// Collapsed: justify-center, no gap, no text
if (isCollapsed) {
  return `flex items-center justify-center p-3 rounded-lg transition-all duration-200 group ${
    isActive ? 'bg-tre-teal/20 text-tre-teal' : 'text-gray-300 hover:bg-tre-navy/50 hover:text-tre-teal'
  }`
}
```

### Collapsible Section (height transition trick)

```tsx
// No JS height measurement needed — use max-h with opacity
<div className={`space-y-1 overflow-hidden transition-all duration-200 ${
  !isCollapsed && !expandedGroups[navGroup.id] ? 'max-h-0 opacity-0' : 'max-h-96 opacity-100'
}`}>
  {navGroup.items.map(item => <NavLink ... />)}
</div>
```

### Flyout Menu on Dark Sidebar

```tsx
// Flyout sits on top of dark sidebar — use border + shadow for definition
<div className="absolute bottom-full left-4 right-4 mb-2 bg-tre-navy border border-tre-teal/30 rounded-lg shadow-xl overflow-hidden z-50">
  <button className="w-full flex items-center gap-3 px-4 py-3 text-gray-300 hover:bg-tre-teal/10 hover:text-tre-teal transition-colors border-t border-tre-teal/20">
    Sign Out
  </button>
</div>
```

---

## Modal and Overlay Patterns

### Modal Overlay (actual Modal.tsx pattern)

```tsx
// GOOD — tre-navy/60 + backdrop-blur, NOT black/50
<div className="fixed inset-0 z-50 flex items-center justify-center">
  <div
    className="absolute inset-0 bg-tre-navy/60 backdrop-blur-sm transition-opacity"
    onClick={closeOnOverlayClick ? onClose : undefined}
  />
  <div className="relative max-w-lg w-full mx-4 bg-white rounded-xl shadow-2xl">
    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
      <h2 className="text-xl font-oswald font-semibold text-tre-navy">{title}</h2>
    </div>
    <div className="px-6 py-4 max-h-[60vh] overflow-y-auto">{children}</div>
    <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
      {footer}
    </div>
  </div>
</div>
```

### Modal Size Variants

```tsx
// Map size prop to max-width — use object, not switch/if chains
const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[90vw] max-h-[90vh]',
}
```

---

## Status and Badge Patterns

StatusBadge uses semantic colors (green/red/yellow/blue) — NOT brand colors — for universal readability.

```tsx
// GOOD — semantic colors for status, not tre-* colors
const statusConfig = {
  success:    { bgColor: 'bg-green-50',  textColor: 'text-green-700',  borderColor: 'border-green-200' },
  error:      { bgColor: 'bg-red-50',    textColor: 'text-red-700',    borderColor: 'border-red-200' },
  pending:    { bgColor: 'bg-yellow-50', textColor: 'text-yellow-700', borderColor: 'border-yellow-200' },
  processing: { bgColor: 'bg-blue-50',   textColor: 'text-blue-700',   borderColor: 'border-blue-200' },
  warning:    { bgColor: 'bg-orange-50', textColor: 'text-orange-700', borderColor: 'border-orange-200' },
}

<span className={`inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full font-medium text-sm ${config.bgColor} ${config.textColor} ${config.borderColor}`}>
  <Icon className={`w-4 h-4 ${status === 'processing' ? 'animate-spin' : ''}`} />
  {label}
</span>
```

**Size variants** via lookup object (same pattern as Modal.tsx):

```tsx
const sizeConfig = {
  sm: { padding: 'px-2 py-0.5',   iconSize: 'w-3 h-3', textSize: 'text-xs' },
  md: { padding: 'px-2.5 py-1',   iconSize: 'w-4 h-4', textSize: 'text-sm' },
  lg: { padding: 'px-3 py-1.5',   iconSize: 'w-5 h-5', textSize: 'text-base' },
}
```

---

## Responsive Layout Patterns

### Desktop Sidebar + Mobile Drawer (MainLayout.tsx)

```tsx
<div className="flex h-screen bg-gray-100">
  {/* Desktop: persistent sidebar */}
  <div className="hidden lg:block">
    <Sidebar />
  </div>

  <main className="flex-1 overflow-auto">
    {/* Mobile: top bar */}
    <div className="lg:hidden flex items-center gap-3 px-4 py-3 bg-tre-navy">
      <button onClick={() => setMobileOpen(true)} className="text-white p-1">
        <Menu className="w-6 h-6" />
      </button>
      <span className="text-white font-oswald font-semibold tracking-wide">{currentPage}</span>
    </div>

    <div className="p-4 lg:p-6">
      <Outlet />
    </div>
  </main>
</div>
```

### Mobile Drawer Overlay

```tsx
{mobileOpen && (
  <div className="fixed inset-0 z-50 lg:hidden">
    <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
    <div className="relative h-full w-64">
      <Sidebar mobile onClose={() => setMobileOpen(false)} />
    </div>
  </div>
)}
```

---

## Typography with Oswald

All headings, nav labels, and modal titles use `font-oswald`. Regular body text uses the default sans.

```tsx
// Headings — font-oswald with weight and tracking
<h1 className="text-white font-oswald font-semibold text-lg tracking-wide">Table Rock</h1>
<h2 className="text-xl font-oswald font-semibold text-tre-navy">{title}</h2>

// Nav labels — font-light for elegance
<span className="font-oswald font-light tracking-wide">{item.name}</span>

// Muted sub-labels — tre-tan at low opacity
<p className="text-tre-tan/60 text-xs truncate">{user?.email}</p>
<p className="text-tre-teal text-xs font-light tracking-widest uppercase">Tools</p>
```

---

## Anti-Patterns

### WARNING: Hardcoded Hex Values

**The Problem:**

```tsx
// BAD — hex values bypass the design token system
<div className="bg-[#90c5ce] text-[#0e2431]">
```

**Why This Breaks:** Color changes require grep-and-replace across the entire codebase. No autocomplete. Team members use different hex values for the same color.

**The Fix:**

```tsx
// GOOD
<div className="bg-tre-teal text-tre-navy">
```

### WARNING: Dynamic Class String Interpolation

**The Problem:**

```tsx
// BAD — Tailwind purges this in production because it can't statically analyze it
const color = 'tre-teal'
<div className={`bg-${color}`}>
```

**Why This Breaks:** Tailwind's content scanner does a regex pass over source files. `bg-tre-teal` never appears as a literal string, so it gets purged from the production CSS bundle. Works in dev (JIT compiles on demand) but breaks in production.

**The Fix:**

```tsx
// GOOD — full class names visible to the static analyzer
const colorMap = { teal: 'bg-tre-teal', navy: 'bg-tre-navy' }
<div className={colorMap[color]}>
```

### WARNING: Using black/50 Instead of tre-navy/60 for Overlays

```tsx
// BAD — doesn't match the brand feel
<div className="fixed inset-0 bg-black/50">

// GOOD — matches the dark navy sidebar aesthetic
<div className="absolute inset-0 bg-tre-navy/60 backdrop-blur-sm">
```

### WARNING: focus:outline-none Without Replacement

```tsx
// BAD — removes focus indicator entirely, breaks keyboard accessibility
<button className="focus:outline-none">

// GOOD — replace with branded focus ring
<button className="focus:outline-none focus:ring-2 focus:ring-tre-teal focus:ring-offset-2">
```

### WARNING: @apply in CSS Files

Extracting component styles to CSS files via `@apply` breaks Tailwind's utility-first model. Create a React component instead:

```tsx
// BAD
// button.css: .btn { @apply bg-tre-teal text-white px-4 py-2 rounded-lg; }

// GOOD — React component with variant props
function Button({ variant = 'primary', children, ...props }) {
  const variants = {
    primary:   'bg-tre-teal text-white hover:bg-tre-teal/90',
    secondary: 'bg-white text-tre-navy border border-gray-300 hover:bg-gray-50',
    danger:    'bg-red-600 text-white hover:bg-red-700',
  }
  return (
    <button className={`px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${variants[variant]}`} {...props}>
      {children}
    </button>
  )
}
```