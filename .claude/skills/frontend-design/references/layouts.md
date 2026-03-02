# Layouts Reference

## Contents
- Page Layout Patterns
- Grid System and Spacing
- Responsive Breakpoints
- Container Constraints
- Sidebar Layout

---

## Page Layout Patterns

### Tool Page Layout

All four tools (Extract, Title, Proration, Revenue) follow the same page structure:

```tsx
function ToolPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6">
        <h1 className="text-4xl font-bold text-tre-navy">Tool Name</h1>
        <p className="text-gray-600 mt-2 leading-relaxed">
          Brief tool description
        </p>
      </div>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-8 py-8">
        <div className="space-y-8">
          {/* Upload Section */}
          <Card>
            <FileUpload onUpload={handleUpload} />
          </Card>

          {/* Results Section (hidden until data exists) */}
          {results.length > 0 && (
            <Card>
              <DataTable data={results} />
            </Card>
          )}

          {/* Export Section (hidden until data exists) */}
          {results.length > 0 && (
            <Card>
              <ExportButtons />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
```

### Dashboard Grid Layout

```tsx
function Dashboard() {
  const tools = [
    { title: 'Extract', icon: FileText, route: '/extract' },
    { title: 'Title', icon: Users, route: '/title' },
    { title: 'Proration', icon: Calculator, route: '/proration' },
    { title: 'Revenue', icon: DollarSign, route: '/revenue' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        <h1 className="text-4xl font-bold text-tre-navy mb-8">
          Table Rock Tools
        </h1>

        {/* Grid: 1 column mobile, 2 columns tablet, 3 columns desktop */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tools.map(tool => (
            <ToolCard key={tool.route} {...tool} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## Grid System and Spacing

### Responsive Grid Patterns

```tsx
// GOOD - Mobile-first responsive grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => <Card key={item.id}>{item.content}</Card>)}
</div>

// Two-column layout with asymmetric widths
<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div className="lg:col-span-2">
    {/* Main content (2/3 width on desktop) */}
  </div>
  <div className="lg:col-span-1">
    {/* Sidebar (1/3 width on desktop) */}
  </div>
</div>

// BAD - Desktop-first (breaks mobile)
<div className="grid grid-cols-3 sm:grid-cols-1">
```

### Spacing Scale Usage

```tsx
// GOOD - Consistent spacing hierarchy
<div className="space-y-12">       {/* Page sections: 48px */}
  <section className="space-y-6">  {/* Section content: 24px */}
    <div className="space-y-3">    {/* Item groups: 12px */}
      <label className="mb-2">Label</label>
      <input />
    </div>
  </section>
</div>

// BAD - Arbitrary spacing
<div style={{ marginBottom: '47px' }}>
  <div style={{ marginBottom: '19px' }}>
    <div style={{ marginBottom: '11px' }}>
```

### WARNING: Inconsistent Gap Values

**The Problem:**

```tsx
// BAD - Different gap values for similar layouts
<div className="grid grid-cols-3 gap-4">
<div className="grid grid-cols-3 gap-6">
<div className="grid grid-cols-3 gap-5">
```

**Why This Breaks:**
Users perceive inconsistent spacing as a lack of polish. Visual rhythm breaks down when gaps are unpredictable.

**The Fix:**

```tsx
// GOOD - Consistent gap-6 for card grids
<div className="grid grid-cols-3 gap-6">

// GOOD - gap-3 for tight item lists
<div className="flex flex-col gap-3">
```

---

## Responsive Breakpoints

### Tailwind Default Breakpoints

```js
// Used consistently across the project
const breakpoints = {
  sm: '640px',   // Mobile landscape
  md: '768px',   // Tablet
  lg: '1024px',  // Desktop
  xl: '1280px',  // Large desktop
  '2xl': '1536px', // Very large desktop
};
```

### Mobile-First Responsive Patterns

```tsx
// GOOD - Mobile base, progressively enhanced
<div className="px-4 md:px-8 lg:px-12">
  <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold">
    Proration Tool
  </h1>
</div>

// GOOD - Stack on mobile, side-by-side on desktop
<div className="flex flex-col md:flex-row gap-4">
  <button className="w-full md:w-auto">Export CSV</button>
  <button className="w-full md:w-auto">Export Excel</button>
</div>

// BAD - Desktop-first (harder to override)
<div className="flex-row md:flex-col">
```

### Hiding Elements Responsively

```tsx
// GOOD - Hide sidebar on mobile, show on desktop
<aside className="hidden lg:block w-64 bg-tre-navy">
  <Sidebar />
</aside>

// GOOD - Mobile menu button (hidden on desktop)
<button className="lg:hidden p-2">
  <Menu className="w-6 h-6" />
</button>

// BAD - Using display: none in inline styles
<div style={{ display: window.innerWidth < 768 ? 'none' : 'block' }}>
```

---

## Container Constraints

### Max-Width Containers

```tsx
// GOOD - Consistent max-width for readability
<div className="max-w-7xl mx-auto px-8">
  {/* Page content stays within 1280px */}
</div>

// GOOD - Narrower container for forms/reading
<div className="max-w-2xl mx-auto px-8">
  <form className="space-y-6">
    {/* Form inputs max out at 672px for better UX */}
  </form>
</div>

// BAD - Full-width content (hard to read)
<div className="w-full px-8">
  <p className="text-base">
    This line of text stretches 3000px on ultra-wide monitors...
  </p>
</div>
```

### Vertical Spacing Constraints

```tsx
// GOOD - min-h-screen for full-page layouts
<div className="min-h-screen bg-gray-50">
  <MainLayout />
</div>

// GOOD - max-h with overflow for scrollable sections
<div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg">
  <DataTable data={longList} />
</div>

// BAD - Fixed height (breaks on content overflow)
<div className="h-64">
  {/* Content might get cut off */}
</div>
```

---

## Sidebar Layout

### MainLayout Component

The entire app uses a fixed sidebar with scrollable content area:

```tsx
function MainLayout() {
  return (
    <div className="flex min-h-screen">
      {/* Fixed Sidebar (hidden on mobile) */}
      <aside className="hidden lg:flex lg:flex-col w-64 bg-tre-navy fixed h-screen">
        <div className="p-6 border-b border-tre-teal border-opacity-20">
          <h1 className="text-2xl font-bold text-white">Table Rock Tools</h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <SidebarLink to="/dashboard" icon={Home}>Dashboard</SidebarLink>
          <SidebarLink to="/extract" icon={FileText}>Extract</SidebarLink>
          <SidebarLink to="/title" icon={Users}>Title</SidebarLink>
          <SidebarLink to="/proration" icon={Calculator}>Proration</SidebarLink>
          <SidebarLink to="/revenue" icon={DollarSign}>Revenue</SidebarLink>
        </nav>
      </aside>

      {/* Main Content Area (scrollable) */}
      <main className="flex-1 lg:ml-64 overflow-y-auto">
        <Outlet /> {/* React Router renders tool pages here */}
      </main>
    </div>
  );
}
```

### Active Sidebar Link Styling

```tsx
function SidebarLink({ to, icon: Icon, children }: SidebarLinkProps) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      className={`
        flex items-center gap-3 px-4 py-3 rounded-lg transition-colors
        ${isActive
          ? 'bg-tre-teal bg-opacity-20 text-tre-teal border-l-4 border-tre-teal'
          : 'text-gray-300 hover:bg-white hover:bg-opacity-10 hover:text-white'
        }
      `}
    >
      <Icon className="w-5 h-5" />
      <span className="font-medium">{children}</span>
    </Link>
  );
}
```

### WARNING: Sidebar Overlapping Content

**The Problem:**

```tsx
// BAD - Sidebar overlaps content on small screens
<div className="flex">
  <aside className="w-64 fixed">Sidebar</aside>
  <main className="flex-1">Content</main>
</div>
```

**Why This Breaks:**
1. On mobile, fixed sidebar covers the content
2. No way for users to access the main content

**The Fix:**

```tsx
// GOOD - Hide sidebar on mobile, add margin-left on desktop
<div className="flex">
  <aside className="hidden lg:flex w-64 fixed">Sidebar</aside>
  <main className="flex-1 lg:ml-64">Content</main>
</div>