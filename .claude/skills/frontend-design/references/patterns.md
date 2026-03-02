# Patterns Reference

## Contents
- DO/DON'T Pairs for Visual Decisions
- Anti-Patterns and Solutions
- Project-Specific Design Patterns
- When to Break the Rules
- Visual Differentiation

---

## DO/DON'T Pairs for Visual Decisions

### Typography

```tsx
// DO - Use Oswald with appropriate weights for hierarchy
<h1 className="text-4xl font-bold text-tre-navy">Proration Tool</h1>
<h2 className="text-2xl font-semibold text-tre-navy">Section Title</h2>
<p className="text-base font-normal text-gray-700">Body text</p>

// DON'T - Introduce new fonts or use all-caps excessively
<h1 className="font-serif text-4xl">Proration Tool</h1>
<h2 className="uppercase tracking-widest">SECTION TITLE</h2>
```

**Why:** Oswald is already loaded. Adding fonts increases bundle size. All-caps reduces readability for dense data.

### Color Usage

```tsx
// DO - Use tre-* colors for brand identity, semantic colors for status
<button className="bg-tre-navy text-white">Upload</button>
<span className="bg-green-100 text-green-800">Success</span>

// DON'T - Use brand colors for status or random colors
<button className="bg-purple-600 text-white">Upload</button>
<span className="bg-tre-teal text-white">Success</span>
```

**Why:** Brand colors (tre-navy, tre-teal) should reinforce identity, not convey data status. Status needs standard semantics (green = success, red = error).

### Spacing

```tsx
// DO - Use Tailwind's spacing scale consistently
<div className="space-y-6">
  <Card className="p-8">
    <div className="mb-4">
      <label className="mb-2">Name</label>
      <input className="px-4 py-3" />
    </div>
  </Card>
</div>

// DON'T - Use arbitrary spacing values
<div style={{ marginBottom: '23px' }}>
  <Card style={{ padding: '31px' }}>
    <div style={{ marginBottom: '17px' }}>
      <input style={{ padding: '13px 19px' }} />
    </div>
  </Card>
</div>
```

**Why:** Arbitrary spacing creates visual noise. Consistent spacing (4px base unit) establishes rhythm and polish.

### Icons

```tsx
// DO - Use Lucide React icons with consistent sizing and semantic colors
<Upload className="w-5 h-5 text-gray-700" />
<CheckCircle className="w-5 h-5 text-green-600" />

// DON'T - Mix icon libraries or use inconsistent sizes
<FaUpload size={18} />  {/* FontAwesome - different visual style */}
<CheckCircle className="w-8 h-3" />  {/* Distorted aspect ratio */}
```

**Why:** Mixing icon libraries creates visual inconsistency. Lucide React's outline style matches the utilitarian tone.

---

## Anti-Patterns and Solutions

### Anti-Pattern: Purple/Blue Gradients

**The Problem:**

```tsx
// BAD - Generic AI aesthetic (purple gradients)
<div className="bg-gradient-to-r from-purple-500 to-blue-500 p-8">
  <h1 className="text-white">Table Rock Tools</h1>
</div>
```

**Why This Breaks:**
1. Purple/blue is the default AI/SaaS aesthetic (Stripe, Linear, Vercel, etc.)
2. Doesn't align with the oil/gas industry's earth-tone professionalism
3. High saturation reduces readability for data-heavy interfaces

**The Fix:**

```tsx
// GOOD - Use brand navy with subtle teal accent
<div className="bg-tre-navy p-8 border-l-4 border-tre-teal">
  <h1 className="text-white font-semibold">Table Rock Tools</h1>
</div>
```

### Anti-Pattern: Overly Playful Language

**The Problem:**

```tsx
// BAD - Consumer-facing tone for professional tools
<button className="bg-tre-teal text-white px-6 py-3 rounded-full">
  🎉 Let's Go! Export Your Data! 🚀
</button>
```

**Why This Breaks:**
1. Land and revenue teams need precision, not enthusiasm
2. Emojis distract from dense technical workflows
3. Rounded-full buttons feel like consumer apps (e.g., Duolingo)

**The Fix:**

```tsx
// GOOD - Direct, professional language with appropriate styling
<button className="bg-tre-navy text-white px-6 py-3 rounded-lg">
  Export to M1 CSV
</button>
```

### Anti-Pattern: Infinite Nested Menus

**The Problem:**

```tsx
// BAD - Complex multi-level navigation
<Sidebar>
  <Menu>
    <MenuItem label="Tools">
      <Submenu>
        <MenuItem label="Extract">
          <Submenu>
            <MenuItem label="Upload" />
            <MenuItem label="History" />
          </Submenu>
        </MenuItem>
      </Submenu>
    </MenuItem>
  </Menu>
</Sidebar>
```

**Why This Breaks:**
1. Users have to hunt through menus to find tools
2. Adds cognitive load for frequent tasks
3. The app only has 4 tools—nested menus are overkill

**The Fix:**

```tsx
// GOOD - Flat navigation with direct tool links
<Sidebar>
  <nav className="space-y-2">
    <SidebarLink to="/dashboard" icon={Home}>Dashboard</SidebarLink>
    <SidebarLink to="/extract" icon={FileText}>Extract</SidebarLink>
    <SidebarLink to="/title" icon={Users}>Title</SidebarLink>
    <SidebarLink to="/proration" icon={Calculator}>Proration</SidebarLink>
    <SidebarLink to="/revenue" icon={DollarSign}>Revenue</SidebarLink>
  </nav>
</Sidebar>
```

### Anti-Pattern: Over-Abstracting Components

**The Problem:**

```tsx
// BAD - Polymorphic button with 15+ props
<Button
  as="a"
  href="/export"
  variant="primary"
  size="lg"
  leftIcon={<Download />}
  rightIcon={<ChevronRight />}
  loading={isLoading}
  disabled={isDisabled}
  color="blue"
  rounded="full"
  shadow="xl"
  fullWidth
  uppercase
  className="custom-override"
>
  Export
</Button>
```

**Why This Breaks:**
1. Too many props make the component unpredictable
2. Custom className overrides defeat the purpose of variants
3. Harder to maintain—every new feature adds a prop

**The Fix:**

```tsx
// GOOD - Specific components with minimal props
<PrimaryButton onClick={handleExport} disabled={isLoading}>
  {isLoading && <Spinner />}
  Export to CSV
</PrimaryButton>
```

---

## Project-Specific Design Patterns

### Tool Cards with Icon Hierarchy

```tsx
// Pattern: Large icon (w-12 h-12) in tre-teal, title in tre-navy, description in gray
function ToolCard({ title, description, icon: Icon, route }: ToolCardProps) {
  return (
    <Link
      to={route}
      className="bg-white rounded-xl p-8 shadow-sm hover:shadow-md
                 transition-shadow border border-gray-100"
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

**Why This Works:** Icon draws the eye first (largest element), title establishes context, description provides detail. Clear hierarchy for scanning.

### Data Tables with Hover States

```tsx
// Pattern: Subtle hover (bg-gray-50) with smooth transition
<tr className="hover:bg-gray-50 transition-colors duration-150">
  <td className="px-6 py-4 text-sm text-gray-700">{row.name}</td>
  <td className="px-6 py-4 text-sm text-gray-700">{row.address}</td>
</tr>
```

**Why This Works:** Land/revenue teams scan hundreds of rows. Subtle hover feedback helps track position without visual overload.

### Upload Sections with Dashed Borders

```tsx
// Pattern: Dashed border + drag-over state
<div
  className={`
    border-2 border-dashed rounded-xl p-12 text-center
    ${isDragOver ? 'border-tre-teal bg-tre-teal bg-opacity-5' : 'border-gray-300'}
    transition-colors duration-200
  `}
>
  <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
  <p className="text-gray-600">Drag and drop PDF files here</p>
</div>
```

**Why This Works:** Dashed border signals interactivity (drop zone). Color change on drag-over provides immediate feedback.

---

## When to Break the Rules

### Rule: "Always use tre-* colors"

**Break it when:** Displaying status (success, error, warning) or data visualization.

```tsx
// GOOD - Use semantic colors for status badges
<span className="bg-green-100 text-green-800">Processing Complete</span>

// GOOD - Use distinct colors for chart data
<BarChart data={data} colors={['#10b981', '#ef4444', '#f59e0b']} />
```

**Why:** Status and data need universal semantics. Green = success is a learned pattern across all software.

### Rule: "Use Oswald for all text"

**Break it when:** Displaying monospace data (API keys, code snippets, file paths).

```tsx
// GOOD - Use monospace for technical content
<code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">
  /api/proration/export/pdf
</code>
```

**Why:** Monospace fonts improve readability for fixed-width data (aligns characters vertically).

### Rule: "Follow spacing scale (4px base unit)"

**Break it when:** Fine-tuning optical alignment (icons, borders, small adjustments).

```tsx
// GOOD - 1px adjustments for optical balance
<button className="flex items-center gap-2">
  <Download className="w-5 h-5 -ml-0.5" />  {/* -2px to optically center icon */}
  Download
</button>
```

**Why:** Mathematical centering doesn't always match optical centering. Trust your eyes for small tweaks.

---

## Visual Differentiation

### What Makes Interfaces Memorable

1. **Distinctive color palettes:** Table Rock uses earth tones (navy, teal, browns) instead of generic tech blues
2. **Purposeful typography:** Oswald's condensed letterforms maximize density without sacrificing readability
3. **Functional layouts:** Tool-per-module structure reflects how users actually work (one tool at a time)
4. **Data-first design:** Large tables, clear labels, minimal decoration—optimized for processing hundreds of rows

### Avoiding Generic Patterns

```tsx
// GENERIC - Could be any SaaS dashboard
<div className="bg-gradient-to-br from-blue-500 to-purple-600 rounded-3xl p-12">
  <h1 className="text-white text-5xl font-extrabold mb-4">
    Welcome to Your Dashboard
  </h1>
  <p className="text-blue-100 text-xl">
    Let's get started with your journey! 🚀
  </p>
</div>

// DISTINCTIVE - Table Rock identity
<div className="bg-white border-l-4 border-tre-teal rounded-xl p-8 shadow-sm">
  <h1 className="text-tre-navy text-3xl font-semibold mb-2">
    Table Rock Tools
  </h1>
  <p className="text-gray-600 leading-relaxed">
    Process OCC exhibits, title opinions, proration calculations, and revenue statements.
  </p>
</div>
```

**Why This Matters:** Users trust distinctive interfaces more than generic ones. Visual identity signals purpose and professionalism.