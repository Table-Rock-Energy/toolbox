# Aesthetics Reference

## Contents
- Typography System
- Color Palette and Semantic Usage
- Visual Identity and Tone
- Dark Mode Handling
- Design Tokens

---

## Typography System

### Font Stack

The project uses **Oswald** (Google Fonts) exclusively for all UI text.

```css
/* tailwind.config.js */
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Oswald', 'sans-serif'],
      },
    },
  },
};
```

**Weights Available:** 300 (light), 400 (normal), 500 (medium), 600 (semibold), 700 (bold)

### Typographic Scale

```tsx
// Page Titles (Dashboard, tool pages)
<h1 className="text-4xl font-bold text-tre-navy mb-6">
  Proration Tool
</h1>

// Section Headers
<h2 className="text-2xl font-semibold text-tre-navy mb-4">
  Mineral Holders
</h2>

// Card Titles
<h3 className="text-xl font-medium text-gray-900">
  Upload Status
</h3>

// Body Text (readable for dense data)
<p className="text-base leading-relaxed text-gray-700">
  Process CSV files with RRC data lookups.
</p>

// Small Text (metadata, timestamps)
<span className="text-sm text-gray-500 font-light">
  Last updated: 2 hours ago
</span>
```

### WARNING: Font Substitution

**The Problem:**

```tsx
// BAD - Introducing a new font breaks visual consistency
<h1 className="font-serif text-3xl">Title Opinion Tool</h1>
```

**Why This Breaks:**
1. Oswald is already loaded, adding fonts increases bundle size
2. Serif fonts clash with the utilitarian, data-first aesthetic
3. Users expect consistent typography across all four tools

**The Fix:**

```tsx
// GOOD - Use Oswald with appropriate weight
<h1 className="font-semibold text-3xl text-tre-navy">
  Title Opinion Tool
</h1>
```

---

## Color Palette and Semantic Usage

### Brand Colors (tre-* Prefix)

```js
// tailwind.config.js - Custom colors
colors: {
  'tre-navy': '#0e2431',      // Primary: sidebar, headers, backgrounds
  'tre-teal': '#90c5ce',      // Accent: links, active states, scrollbars
  'tre-tan': '#cab487',       // Highlight: accents, badges
  'tre-brown-dark': '#5b4825',   // Dark brown accents
  'tre-brown-medium': '#775723', // Medium brown accents
  'tre-brown-light': '#966e35',  // Light brown accents
}
```

### Semantic Color Usage

```tsx
// Primary Actions - tre-navy
<button className="bg-tre-navy text-white hover:bg-opacity-90">
  Upload PDF
</button>

// Links and Interactive Elements - tre-teal
<a href="/help" className="text-tre-teal hover:underline">
  Learn more
</a>

// Sidebar Active State - tre-teal
<nav className="bg-tre-navy">
  <a className="text-tre-teal border-l-4 border-tre-teal">
    Dashboard
  </a>
</nav>

// Accent Highlights - tre-tan
<span className="bg-tre-tan bg-opacity-20 text-tre-brown-dark px-3 py-1 rounded">
  New Feature
</span>
```

### Status Colors (NOT Brand Colors)

```tsx
// GOOD - Use standard semantic colors for status
const statusColors = {
  success: 'bg-green-100 text-green-800 border-green-200',
  error: 'bg-red-100 text-red-800 border-red-200',
  warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  pending: 'bg-gray-100 text-gray-800 border-gray-200',
};

// BAD - Using brand colors for status (confusing)
<span className="bg-tre-teal text-white">Processing</span>
```

**Why This Matters:** Users must distinguish between **brand identity** (navy/teal) and **data status** (green/red/yellow). Mixing these creates cognitive overload.

---

## Visual Identity and Tone

### What Makes This Design Distinctive

1. **Earth Tones Over Tech Blues:** Navy + teal + browns evoke oil/gas industry professionalism
2. **Condensed Typography:** Oswald's narrow letterforms maximize information density
3. **Data-First Layouts:** Large tables, clear labels, minimal ornamentation
4. **Tool-Based Navigation:** Sidebar with 4 distinct tools, not infinite nested menus

### Voice and Tone Through Design

```tsx
// Professional, utilitarian - NOT playful or consumer-facing
// GOOD - Clear, direct labels
<button>Export to M1 CSV</button>

// BAD - Overly casual or playful
<button>🎉 Get Your CSV!</button>

// GOOD - Technical terminology retained
<label>RRC Lease Number</label>

// BAD - Over-simplified for non-technical users
<label>Property ID</label>
```

**Rationale:** Land and revenue teams are technical professionals who need precision, not hand-holding.

---

## Dark Mode Handling

**Current State:** The project does NOT implement dark mode.

**Why:** 
- Users work in bright office environments during business hours
- Dense tabular data requires maximum contrast (black text on white)
- PDF exports must match on-screen appearance

**If Dark Mode is Requested:**

```tsx
// DO NOT implement automatic dark mode
// Users must explicitly toggle it for specific use cases (late-night work)

// Proposed toggle (not yet implemented)
const [darkMode, setDarkMode] = useState(false);

// Update tre-navy to lighter variant in dark mode
<div className={darkMode ? 'bg-gray-900 text-gray-100' : 'bg-white text-gray-900'}>
```

**WARNING:** Dark mode changes contrast ratios. Test all tre-* colors for WCAG AA compliance on dark backgrounds before enabling.

---

## Design Tokens

### Spacing Scale (Tailwind Default)

```tsx
// Consistent spacing using Tailwind's 4px base unit
const spacing = {
  1: '0.25rem',  // 4px
  2: '0.5rem',   // 8px
  3: '0.75rem',  // 12px
  4: '1rem',     // 16px - most common
  6: '1.5rem',   // 24px - section gaps
  8: '2rem',     // 32px - card padding
  12: '3rem',    // 48px - page margins
};

// GOOD - Consistent spacing
<div className="p-8 mb-6">
  <h2 className="mb-4">Section Title</h2>
  <div className="space-y-3">
    {items.map(item => <div key={item.id} className="p-4">{item.name}</div>)}
  </div>
</div>

// BAD - Arbitrary pixel values
<div style={{ padding: '27px', marginBottom: '19px' }}>
```

### Border Radius

```tsx
// Standard rounded corners
const radius = {
  'rounded-lg': '0.5rem',   // Buttons, inputs
  'rounded-xl': '0.75rem',  // Cards, modals
  'rounded-full': '9999px', // Pills, avatars
};

// GOOD - Cards use rounded-xl
<div className="bg-white rounded-xl shadow-sm p-8">

// BAD - Inconsistent radii
<div className="rounded-[13px]">
```

### Shadow Elevation

```tsx
// Tailwind shadow scale - use sparingly
<div className="shadow-sm">    {/* Subtle card borders */}
<div className="shadow-md">    {/* Elevated cards on hover */}
<div className="shadow-lg">    {/* Dropdowns, popovers */}
<div className="shadow-2xl">   {/* Modals */}

// GOOD - Progressive disclosure through shadow
<button className="shadow-sm hover:shadow-md transition-shadow">

// BAD - Heavy shadows everywhere (cluttered)
<div className="shadow-2xl">
  <div className="shadow-2xl">
    <button className="shadow-2xl">Click</button>
  </div>
</div>