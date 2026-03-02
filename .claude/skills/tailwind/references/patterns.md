# Tailwind Patterns Reference

## Contents
- Custom Brand Color System
- Component Styling Patterns
- Responsive Design Patterns
- State and Interaction Patterns
- Layout Patterns
- Anti-Patterns

---

## Custom Brand Color System

Table Rock TX Tools defines custom colors in `toolbox/frontend/tailwind.config.js`:

```javascript
// toolbox/frontend/tailwind.config.js
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
    },
  },
  plugins: [],
};
```

**Use these colors exclusively for brand consistency.** NEVER use default Tailwind colors for primary UI elements.

```tsx
// GOOD - Brand-consistent navigation
<div className="bg-tre-navy text-white">
  <a className="text-tre-teal hover:text-tre-tan">Dashboard</a>
</div>

// BAD - Using default Tailwind colors for primary brand elements
<div className="bg-blue-900 text-white">
  <a className="text-cyan-400 hover:text-yellow-300">Dashboard</a>
</div>
```

**Opacity modifiers** for subtle backgrounds and borders:

```tsx
// toolbox/frontend/src/components/Sidebar.tsx
<div className="border-b border-tre-teal/20"> {/* 20% opacity */}
  <nav className="hover:bg-tre-teal/10"> {/* 10% opacity */}
    Links
  </nav>
</div>
```

---

## Component Styling Patterns

### Card Components

**Pattern:** Consistent shadow, rounded corners, padding, hover effects

```tsx
// toolbox/frontend/src/pages/Dashboard.tsx
<div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
  <h3 className="text-lg font-semibold text-tre-navy mb-2">Extract Tool</h3>
  <p className="text-gray-600 text-sm">Process OCC Exhibit A PDFs</p>
</div>
```

**Why:** Consistent card styling creates visual hierarchy and professional appearance. The `transition-shadow` provides smooth hover feedback.

### Buttons

```tsx
// toolbox/frontend/src/components/FileUpload.tsx
<button className="w-full bg-tre-teal text-white px-4 py-2 rounded-lg hover:bg-tre-teal/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
  Upload File
</button>

// Secondary button variant
<button className="px-4 py-2 border border-tre-navy text-tre-navy rounded-lg hover:bg-tre-navy/5 transition-colors">
  Cancel
</button>
```

**Key classes:**
- `transition-colors` for smooth color changes
- `disabled:opacity-50 disabled:cursor-not-allowed` for disabled state
- `hover:bg-tre-teal/90` for subtle hover darkening

### Status Badges

```tsx
// toolbox/frontend/src/components/StatusBadge.tsx
const statusColors = {
  success: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  pending: 'bg-yellow-100 text-yellow-800',
  info: 'bg-tre-teal/20 text-tre-navy',
};

<span className={`inline-block px-2 py-1 text-xs rounded ${statusColors[status]}`}>
  {label}
</span>
```

**Note:** Status badges use semantic colors (green/red/yellow) for universal understanding, while info badges use brand colors.

---

## Responsive Design Patterns

### Grid Layouts

```tsx
// toolbox/frontend/src/pages/Dashboard.tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {/* Mobile: 1 column, Tablet: 2 columns, Desktop: 4 columns */}
</div>
```

**Breakpoints:**
- Default (mobile): `grid-cols-1`
- `md:` (768px+): `md:grid-cols-2`
- `lg:` (1024px+): `lg:grid-cols-4`

### Container Widths

```tsx
// toolbox/frontend/src/pages/Extract.tsx
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  {/* Content */}
</div>
```

**Why:** `max-w-7xl` prevents content from stretching too wide on large screens. Responsive padding (`px-4 sm:px-6 lg:px-8`) ensures proper spacing on all devices.

### WARNING: Never Use Fixed Widths for Main Content

```tsx
// BAD - Fixed width breaks on small screens
<div className="w-[1200px]">
  Content
</div>

// GOOD - Responsive max-width with padding
<div className="max-w-7xl mx-auto px-4">
  Content
</div>
```

**Why This Breaks:** Fixed widths cause horizontal scrolling on smaller screens. Always use `max-w-*` with `mx-auto` for centered content and `px-*` for edge spacing.

---

## State and Interaction Patterns

### Hover States

```tsx
// toolbox/frontend/src/components/Sidebar.tsx
<a className="flex items-center gap-3 px-4 py-2 rounded text-white hover:bg-tre-teal/10 transition-colors">
  Dashboard
</a>
```

**Always pair hover effects with `transition-*`** for smooth animations.

### Focus States for Accessibility

```tsx
// toolbox/frontend/src/components/Modal.tsx
<input className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal focus:border-transparent" />
```

**Why:** `focus:ring-2 focus:ring-tre-teal` provides visible focus indication for keyboard navigation. NEVER use `focus:outline-none` without a replacement focus indicator.

### Active Navigation States

```tsx
// toolbox/frontend/src/components/Sidebar.tsx
const isActive = location.pathname === '/proration';
<a className={`flex items-center gap-3 px-4 py-2 rounded transition-colors ${
  isActive 
    ? 'bg-tre-teal/20 text-tre-teal font-semibold' 
    : 'text-white hover:bg-tre-teal/10'
}`}>
  Proration
</a>
```

**Pattern:** Active state has background color + text color change + font weight, while inactive has hover state only.

---

## Layout Patterns

### Flexbox Centering

```tsx
// toolbox/frontend/src/components/Modal.tsx
<div className="fixed inset-0 flex items-center justify-center z-50">
  <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
    Content
  </div>
</div>
```

**Why:** `flex items-center justify-center` centers both vertically and horizontally. `mx-4` prevents modal from touching screen edges on mobile.

### Sticky Headers

```tsx
<header className="sticky top-0 bg-white border-b border-gray-200 z-10 px-6 py-4">
  <h1 className="text-2xl font-bold text-tre-navy">Extract Tool</h1>
</header>
```

**Key classes:** `sticky top-0 z-10` keeps header visible on scroll.

### Scrollable Containers

```tsx
// toolbox/frontend/src/components/DataTable.tsx
<div className="overflow-x-auto">
  <table className="min-w-full divide-y divide-gray-200">
    {/* Table content */}
  </table>
</div>
```

**Why:** `overflow-x-auto` enables horizontal scrolling for wide tables on mobile. `min-w-full` ensures table doesn't collapse.

---

## Anti-Patterns

### WARNING: Inline Styles

**The Problem:**

```tsx
// BAD - Inline styles bypass Tailwind's design system
<div style={{ backgroundColor: '#90c5ce', padding: '16px' }}>
  Content
</div>
```

**Why This Breaks:**
1. **No responsive design:** Can't use breakpoint modifiers
2. **Inconsistent spacing:** `16px` doesn't align with Tailwind's spacing scale
3. **No state variants:** Can't use `hover:`, `focus:`, etc.

**The Fix:**

```tsx
// GOOD - Use Tailwind utilities
<div className="bg-tre-teal p-4">
  Content
</div>
```

### WARNING: Arbitrary Values Instead of Config

**The Problem:**

```tsx
// BAD - Hardcoded brand color
<div className="bg-[#90c5ce] text-[#0e2431]">
  Content
</div>
```

**Why This Breaks:**
1. **No central configuration:** Color changes require find-and-replace
2. **No autocomplete:** Editor can't suggest brand colors
3. **Inconsistent naming:** Team members use different hex values

**The Fix:**

```tsx
// GOOD - Use configured colors
<div className="bg-tre-teal text-tre-navy">
  Content
</div>
```

**When You Might Be Tempted:** Prototyping a new color scheme before committing to config changes. Resist this—add colors to `tailwind.config.js` immediately.

### WARNING: @apply in Separate CSS Files

**The Problem:**

```css
/* BAD - Separate CSS file defeats utility-first approach */
.custom-button {
  @apply bg-tre-teal text-white px-4 py-2 rounded-lg;
}
```

**Why This Breaks:**
1. **Context switching:** Developers must look in multiple files
2. **No component co-location:** Styles separated from markup
3. **Harder to customize:** Can't easily override with props

**The Fix:**

```tsx
// GOOD - Inline utilities with optional prop-based variants
<button className={`bg-tre-teal text-white px-4 py-2 rounded-lg ${variant === 'secondary' ? 'bg-white text-tre-navy border border-tre-navy' : ''}`}>
  Submit
</button>
```

**When You Might Be Tempted:** "Reusing" button styles across components. Instead, create a React component with `className` props for variants.

### WARNING: Missing Responsive Breakpoints

**The Problem:**

```tsx
// BAD - Fixed layout breaks on mobile
<div className="grid grid-cols-4 gap-6">
  {tools.map(tool => <Card key={tool.id} {...tool} />)}
</div>
```

**Why This Breaks:**
1. **Poor mobile UX:** 4 columns on a 375px screen are unreadable
2. **Horizontal overflow:** Content extends beyond viewport

**The Fix:**

```tsx
// GOOD - Mobile-first responsive grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {tools.map(tool => <Card key={tool.id} {...tool} />)}
</div>
```

**When You Might Be Tempted:** Desktop-first development. Always start mobile (`grid-cols-1`) and add breakpoints upward.