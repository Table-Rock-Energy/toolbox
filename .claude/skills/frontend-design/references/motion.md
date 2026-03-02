# Motion Reference

## Contents
- Transition Patterns
- Hover States and Micro-Interactions
- Loading States
- Animation Timing and Easing
- Performance Considerations

---

## Transition Patterns

### CSS Transitions (Primary Method)

The project uses Tailwind's `transition-*` utilities for simple state changes.

```tsx
// GOOD - Button hover transition
<button className="bg-tre-navy text-white px-6 py-3 rounded-lg
                   hover:bg-opacity-90 transition-colors duration-200">
  Upload PDF
</button>

// GOOD - Shadow elevation on card hover
<div className="bg-white rounded-xl shadow-sm
               hover:shadow-md transition-shadow duration-300">
  <ToolCard />
</div>

// GOOD - Sidebar link active state
<a className="text-gray-300 hover:text-white
              transition-colors duration-150">
  Dashboard
</a>
```

### Transition Properties

```tsx
// GOOD - Specific transition properties for performance
transition-colors    // Only animates color properties
transition-opacity   // Only animates opacity
transition-transform // Only animates transforms (scale, rotate, translate)
transition-shadow    // Only animates box-shadow
transition-all       // Animates all properties (use sparingly)

// BAD - Transitioning all properties on complex elements
<div className="transition-all duration-500">
  {/* Expensive: transitions width, height, padding, margin, etc. */}
</div>
```

### WARNING: Overusing transition-all

**The Problem:**

```tsx
// BAD - transition-all on every element
<div className="transition-all duration-300">
  <Card className="transition-all duration-300">
    <button className="transition-all duration-300">
      Click
    </button>
  </Card>
</div>
```

**Why This Breaks:**
1. Performance: Animating all properties (width, height, padding, margin, color, etc.) causes layout thrashing
2. Unexpected animations: Properties you didn't intend to animate will transition (e.g., layout shifts)
3. Slower rendering: Browser must recalculate all styles on every frame

**The Fix:**

```tsx
// GOOD - Only transition specific properties
<div className="transition-colors duration-200">
  <Card className="transition-shadow duration-300">
    <button className="transition-opacity duration-150">
      Click
    </button>
  </Card>
</div>
```

---

## Hover States and Micro-Interactions

### Button Interactions

```tsx
// Primary button - subtle opacity change
<button className="bg-tre-navy text-white px-6 py-3 rounded-lg
                   hover:bg-opacity-90 active:scale-95
                   transition-all duration-150">
  Upload
</button>

// Secondary button - background fill on hover
<button className="border-2 border-tre-teal text-tre-teal px-6 py-3 rounded-lg
                   hover:bg-tre-teal hover:text-white
                   transition-colors duration-200">
  Cancel
</button>

// Icon button - background fade in
<button className="p-2 rounded-lg hover:bg-gray-100
                   transition-colors duration-150"
        aria-label="Download">
  <Download className="w-5 h-5 text-gray-700" />
</button>
```

### Link Interactions

```tsx
// GOOD - Underline on hover for text links
<a href="/help" className="text-tre-teal hover:underline
                          transition-all duration-150">
  Learn more
</a>

// GOOD - Sidebar link with background and border
<a className="flex items-center gap-3 px-4 py-3 rounded-lg
              text-gray-300 hover:bg-white hover:bg-opacity-10 hover:text-white
              transition-colors duration-200">
  <Home className="w-5 h-5" />
  Dashboard
</a>

// BAD - No visual feedback on hover
<a href="/help" className="text-tre-teal">
  Learn more
</a>
```

### Table Row Interactions

```tsx
// GOOD - Subtle background change on hover
<tr className="hover:bg-gray-50 transition-colors duration-150">
  <td className="px-6 py-4">John Doe</td>
  <td className="px-6 py-4">123 Main St</td>
</tr>

// GOOD - Clickable row with cursor pointer
<tr className="hover:bg-tre-teal hover:bg-opacity-5 cursor-pointer
              transition-colors duration-200"
    onClick={() => handleRowClick(row.id)}>
  <td className="px-6 py-4">{row.name}</td>
</tr>
```

---

## Loading States

### Button Loading State

```tsx
function LoadingButton({ isLoading, children, onClick }: LoadingButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={isLoading}
      className="bg-tre-navy text-white px-6 py-3 rounded-lg
                 hover:bg-opacity-90 disabled:opacity-50
                 transition-colors flex items-center gap-2"
    >
      {isLoading && (
        <div className="w-5 h-5 border-2 border-white border-t-transparent
                       rounded-full animate-spin" />
      )}
      {children}
    </button>
  );
}
```

### Full-Page Loading Spinner

```tsx
function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="relative">
        {/* Outer ring */}
        <div className="w-16 h-16 border-4 border-gray-200 rounded-full"></div>
        {/* Spinning ring */}
        <div className="w-16 h-16 border-4 border-tre-teal border-t-transparent
                       rounded-full animate-spin absolute top-0 left-0"></div>
      </div>
    </div>
  );
}
```

### Skeleton Loading (Data Tables)

```tsx
// GOOD - Skeleton rows while fetching data
function SkeletonRow() {
  return (
    <tr>
      <td className="px-6 py-4">
        <div className="h-4 bg-gray-200 rounded animate-pulse w-32"></div>
      </td>
      <td className="px-6 py-4">
        <div className="h-4 bg-gray-200 rounded animate-pulse w-48"></div>
      </td>
      <td className="px-6 py-4">
        <div className="h-4 bg-gray-200 rounded animate-pulse w-24"></div>
      </td>
    </tr>
  );
}

// Usage
<tbody>
  {isLoading
    ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
    : data.map(row => <DataRow key={row.id} data={row} />)
  }
</tbody>
```

---

## Animation Timing and Easing

### Duration Standards

```tsx
// GOOD - Consistent timing for similar interactions
duration-100   // 100ms - Instant feedback (active states)
duration-150   // 150ms - Fast interactions (button hover, link hover)
duration-200   // 200ms - Standard transitions (color, opacity)
duration-300   // 300ms - Moderate transitions (shadow, transform)
duration-500   // 500ms - Slower transitions (layout shifts, page transitions)

// BAD - Arbitrary durations
duration-[273ms]
duration-[1337ms]
```

### Easing Curves (Tailwind Defaults)

```tsx
// Tailwind's default easing is ease-in-out (cubic-bezier(0.4, 0, 0.2, 1))
// This is appropriate for most UI transitions

// GOOD - Use defaults unless you have a specific reason
<button className="transition-colors duration-200">
  {/* Implicitly uses ease-in-out */}
</button>

// GOOD - Override easing for specific effects
<div className="transition-transform duration-300 ease-out
               hover:scale-105">
  {/* Ease-out feels more natural for scale-up */}
</div>

// BAD - Custom easing without design rationale
<div className="transition-all duration-500 ease-[cubic-bezier(0.87,0.13,0.42,0.97)]">
```

---

## Performance Considerations

### Animating Performance-Friendly Properties

**Fast (GPU-accelerated):**
- `opacity`
- `transform` (translate, scale, rotate)

**Slow (triggers layout/paint):**
- `width`, `height`
- `top`, `left`, `right`, `bottom`
- `padding`, `margin`
- `border-width`

```tsx
// GOOD - Animate transform instead of width
<div className="w-0 scale-x-0 hover:scale-x-100
               transition-transform duration-300 origin-left">
  Expandable panel
</div>

// BAD - Animating width (causes reflow)
<div className="w-0 hover:w-64 transition-all duration-300">
  Expandable panel
</div>
```

### Reducing Motion for Accessibility

```tsx
// GOOD - Respect prefers-reduced-motion
<button className="bg-tre-navy text-white px-6 py-3 rounded-lg
                   hover:bg-opacity-90
                   transition-colors duration-200
                   motion-reduce:transition-none">
  Upload
</button>

// GOOD - Disable animations for users with motion sensitivity
<div className="animate-spin motion-reduce:animate-none">
  <LoadingSpinner />
</div>
```

### WARNING: Animating on Every Scroll Event

**The Problem:**

```tsx
// BAD - Running expensive transitions on scroll
window.addEventListener('scroll', () => {
  element.style.transform = `translateY(${window.scrollY}px)`;
  element.style.opacity = `${1 - window.scrollY / 1000}`;
});
```

**Why This Breaks:**
1. Scroll events fire at 60+ times per second
2. Inline style updates force synchronous reflow
3. Battery drain on mobile devices

**The Fix:**

```tsx
// GOOD - Use CSS for scroll-based effects (if needed)
<div className="sticky top-0 bg-white bg-opacity-95 backdrop-blur-sm
               transition-shadow duration-200">
  {/* Browser optimizes this automatically */}
</div>

// GOOD - Debounce scroll handlers if JS is required
const handleScroll = debounce(() => {
  // Update state infrequently (e.g., every 100ms)
}, 100);
```

**Current Project Usage:** The project does NOT implement scroll-based animations. All motion is user-triggered (hover, click, focus).