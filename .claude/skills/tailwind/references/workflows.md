# Tailwind Workflows Reference

## Contents
- Adding Custom Brand Colors
- Creating Reusable Component Styles
- Debugging Utility Classes
- Theme Customization
- Performance Optimization
- Migration from Legacy Styles

---

## Adding Custom Brand Colors

**When:** Adding a new brand color or color variant to the design system.

### Workflow

Copy this checklist and track progress:
- [ ] Add color to `tailwind.config.js` theme.extend.colors
- [ ] Test color contrast for accessibility (WCAG AA minimum)
- [ ] Update documentation with color usage guidelines
- [ ] Add examples to component library
- [ ] Verify across all breakpoints

**Step 1:** Define color in Tailwind config

```javascript
// toolbox/frontend/tailwind.config.js
export default {
  theme: {
    extend: {
      colors: {
        'tre-navy': '#0e2431',
        'tre-teal': '#90c5ce',
        'tre-tan': '#cab487',
        'tre-brown-dark': '#5b4825',
        'tre-brown-medium': '#775723',
        'tre-brown-light': '#966e35',
        'tre-gold': '#d4af37', // NEW COLOR
      },
    },
  },
};
```

**Step 2:** Restart Vite dev server to register new color

```bash
# Ctrl+C to stop dev server, then:
cd toolbox
make dev
```

**Why:** Tailwind config changes require a dev server restart to regenerate utility classes.

**Step 3:** Use the new color in components

```tsx
<div className="bg-tre-gold text-white p-4">
  Premium Feature
</div>
```

**Step 4:** Validate color contrast (iterate until pass)

1. Open component in browser
2. Use Chrome DevTools → Elements → Accessibility pane
3. Check contrast ratio (minimum 4.5:1 for normal text, 3:1 for large text)
4. If contrast fails, adjust color lightness in config and repeat

---

## Creating Reusable Component Styles

**When:** Multiple components need the same visual treatment, but you want to avoid `@apply` in CSS files.

### Pattern: Tailwind Class Composition in React

```tsx
// toolbox/frontend/src/components/Button.tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}

const baseClasses = 'rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

const variantClasses = {
  primary: 'bg-tre-teal text-white hover:bg-tre-teal/90',
  secondary: 'bg-white text-tre-navy border border-tre-navy hover:bg-tre-navy/5',
  danger: 'bg-red-600 text-white hover:bg-red-700',
};

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export default function Button({ 
  variant = 'primary', 
  size = 'md', 
  children, 
  onClick, 
  disabled 
}: ButtonProps) {
  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
```

**Usage:**

```tsx
<Button variant="primary" size="lg" onClick={handleSubmit}>
  Submit
</Button>
<Button variant="secondary" size="sm" onClick={handleCancel}>
  Cancel
</Button>
```

**Why This Works:**
- **Co-located:** Styles live with the component
- **Type-safe:** TypeScript ensures valid variants
- **Composable:** Combine with additional `className` props if needed
- **No CSS files:** Stays within Tailwind's utility-first paradigm

---

## Debugging Utility Classes

### Problem: Classes Not Applying

**Step 1:** Verify class exists in Tailwind output

```bash
# Search generated CSS for the class
cd toolbox/frontend
npx tailwindcss -o - 2>/dev/null | grep "bg-tre-teal"
```

**If class is missing:**
- Check `tailwind.config.js` for typos in color name
- Ensure `content` glob includes your file: `'./src/**/*.{js,ts,jsx,tsx}'`
- Restart Vite dev server

**Step 2:** Check CSS specificity conflicts

```tsx
// BAD - Inline style overrides Tailwind
<div className="bg-tre-navy" style={{ backgroundColor: '#fff' }}>
  Content
</div>

// GOOD - Use Tailwind exclusively
<div className="bg-white">
  Content
</div>
```

**Step 3:** Inspect in DevTools

1. Right-click element → Inspect
2. Check Computed styles for actual background color
3. Look for crossed-out styles (specificity conflicts)

### Problem: Purged Classes in Production

**Symptom:** Classes work in dev but disappear in production build.

**Cause:** Dynamically constructed class names are purged:

```tsx
// BAD - Purged in production
const color = 'tre-teal';
<div className={`bg-${color}`}>Content</div>
```

**Why This Breaks:** Tailwind's static analyzer can't detect `bg-tre-teal` from string interpolation.

**The Fix:**

```tsx
// GOOD - Full class names visible to Tailwind
const colorClasses = {
  'tre-teal': 'bg-tre-teal',
  'tre-navy': 'bg-tre-navy',
};
<div className={colorClasses[color]}>Content</div>
```

**Or use safelist in config:**

```javascript
// tailwind.config.js
export default {
  safelist: [
    'bg-tre-teal',
    'bg-tre-navy',
    'text-tre-tan',
  ],
};
```

---

## Theme Customization

### Extending Spacing Scale

```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      spacing: {
        '128': '32rem',  // 512px
        '144': '36rem',  // 576px
      },
    },
  },
};
```

**Use case:** Large container widths or custom padding values.

### Custom Font Family

```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Oswald', 'sans-serif'],
      },
    },
  },
};
```

```html
<!-- toolbox/frontend/index.html -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

**Why:** Table Rock TX Tools uses Oswald (weights 300-700) for all UI text.

### Custom Scrollbar Styling

```css
/* toolbox/frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer utilities {
  .scrollbar-tre {
    scrollbar-width: thin;
    scrollbar-color: #90c5ce #0e2431;
  }
  
  .scrollbar-tre::-webkit-scrollbar {
    width: 8px;
  }
  
  .scrollbar-tre::-webkit-scrollbar-track {
    background: #0e2431;
  }
  
  .scrollbar-tre::-webkit-scrollbar-thumb {
    background: #90c5ce;
    border-radius: 4px;
  }
}
```

**Usage:**

```tsx
<div className="overflow-y-auto scrollbar-tre h-96">
  Long content...
</div>
```

**When to use `@layer utilities`:** For browser-specific features not supported by Tailwind utilities (like scrollbar styling).

---

## Performance Optimization

### Minimize Bundle Size

**Step 1:** Audit unused utilities

```bash
cd toolbox/frontend
npm run build
# Check dist/assets/*.css file size
```

**Step 2:** Ensure content paths are specific

```javascript
// BAD - Scans unnecessary files
content: ['**/*.tsx']

// GOOD - Only scans source files
content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}']
```

**Step 3:** Use PurgeCSS-safe class names (no dynamic construction)

See "Debugging Utility Classes" section above.

### Enable JIT Mode (Default in Tailwind 3.x)

JIT (Just-In-Time) mode is enabled by default in Tailwind 3.x. No configuration needed.

**Benefits:**
- Faster build times
- Smaller CSS output
- Arbitrary values supported: `w-[137px]`

---

## Migration from Legacy Styles

**Scenario:** Converting existing inline styles or CSS modules to Tailwind.

### Workflow

Copy this checklist and track progress:
- [ ] Identify component with legacy styles
- [ ] Map CSS properties to Tailwind utilities
- [ ] Replace inline styles/classes with Tailwind
- [ ] Test responsiveness at all breakpoints
- [ ] Remove legacy CSS file if empty

**Step 1:** Identify legacy styles

```tsx
// BEFORE - Inline styles
<div style={{
  backgroundColor: '#0e2431',
  padding: '24px',
  borderRadius: '8px',
  boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
}}>
  Content
</div>
```

**Step 2:** Map to Tailwind utilities

| CSS Property | CSS Value | Tailwind Class |
|--------------|-----------|----------------|
| `background-color` | `#0e2431` | `bg-tre-navy` |
| `padding` | `24px` | `p-6` (24px = 1.5rem = spacing 6) |
| `border-radius` | `8px` | `rounded-lg` |
| `box-shadow` | `0 4px 6px rgba(0,0,0,0.1)` | `shadow-md` |

**Step 3:** Replace with Tailwind

```tsx
// AFTER - Tailwind utilities
<div className="bg-tre-navy p-6 rounded-lg shadow-md">
  Content
</div>
```

**Step 4:** Validate at breakpoints (iterate until pass)

1. Open component in browser
2. Use Chrome DevTools responsive mode
3. Test at 375px (mobile), 768px (tablet), 1024px (desktop)
4. If layout breaks, add responsive modifiers: `p-4 md:p-6 lg:p-8`
5. Repeat until all breakpoints look correct

### WARNING: Don't Mix Tailwind with CSS Modules

```tsx
// BAD - Mixing paradigms
import styles from './Component.module.css';
<div className={`${styles.card} bg-tre-navy p-4`}>
  Content
</div>
```

**Why This Breaks:** Increases cognitive load, makes debugging harder, and defeats Tailwind's utility-first philosophy.

**The Fix:** Fully migrate to Tailwind or use CSS modules exclusively. For Table Rock TX Tools, **use Tailwind exclusively**.