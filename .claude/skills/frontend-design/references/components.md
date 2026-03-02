# Components Reference

## Contents
- Component Styling Patterns
- Visual Hierarchy in Components
- Consistent Visual Treatments
- Integration with Lucide Icons
- Component Composition

---

## Component Styling Patterns

### Button Variants

The project uses explicit button variants instead of a polymorphic Button component.

```tsx
// Primary Button - tre-navy background
function PrimaryButton({ children, onClick, disabled, type = 'button' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="bg-tre-navy text-white px-6 py-3 rounded-lg 
                 hover:bg-opacity-90 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors font-medium text-base"
    >
      {children}
    </button>
  );
}

// Secondary Button - outlined tre-teal
function SecondaryButton({ children, onClick, disabled, type = 'button' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="border-2 border-tre-teal text-tre-teal px-6 py-3 rounded-lg
                 hover:bg-tre-teal hover:text-white disabled:opacity-50
                 transition-colors font-medium text-base"
    >
      {children}
    </button>
  );
}

// Danger Button - red for destructive actions
function DangerButton({ children, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="bg-red-600 text-white px-6 py-3 rounded-lg
                 hover:bg-red-700 disabled:opacity-50
                 transition-colors font-medium text-base"
    >
      {children}
    </button>
  );
}
```

### Input Field Styling

```tsx
// Standard text input with consistent styling
function TextField({ label, value, onChange, error, required }: TextFieldProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={onChange}
        className={`
          w-full px-4 py-3 rounded-lg border
          ${error ? 'border-red-300 focus:ring-red-500' : 'border-gray-300 focus:ring-tre-teal'}
          focus:outline-none focus:ring-2 focus:border-transparent
          transition-colors
        `}
      />
      {error && (
        <p className="text-sm text-red-600 flex items-center gap-1">
          <AlertCircle className="w-4 h-4" />
          {error}
        </p>
      )}
    </div>
  );
}
```

### Card Component

```tsx
// Standard card wrapper used across tool pages
function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 ${className}`}>
      {children}
    </div>
  );
}

// Card with header section
function CardWithHeader({ title, action, children }: CardWithHeaderProps) {
  return (
    <Card>
      <div className="border-b border-gray-100 p-6 flex justify-between items-center">
        <h3 className="text-xl font-semibold text-tre-navy">{title}</h3>
        {action}
      </div>
      <div className="p-6">{children}</div>
    </Card>
  );
}
```

---

## Visual Hierarchy in Components

### Typography Hierarchy

```tsx
// Page-level component showing clear hierarchy
function ProrationPage() {
  return (
    <div className="space-y-8">
      {/* Level 1: Page Title */}
      <h1 className="text-4xl font-bold text-tre-navy">
        Proration Tool
      </h1>

      {/* Level 2: Section Headers */}
      <section className="space-y-6">
        <h2 className="text-2xl font-semibold text-tre-navy border-b border-gray-200 pb-3">
          RRC Data Status
        </h2>

        {/* Level 3: Subsection Headers */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-900">
            Last Updated
          </h3>
          <p className="text-base text-gray-700 leading-relaxed">
            Oil proration data: January 2026
          </p>
        </div>
      </section>
    </div>
  );
}
```

### WARNING: Flat Visual Hierarchy

**The Problem:**

```tsx
// BAD - Everything looks the same
<div>
  <p className="text-base">Proration Tool</p>
  <p className="text-base">RRC Data Status</p>
  <p className="text-base">Last Updated</p>
  <p className="text-base">January 2026</p>
</div>
```

**Why This Breaks:**
1. Users can't scan the page to find sections
2. No visual distinction between titles and content
3. Cognitive load increases as users read every line

**The Fix:** Use the 3-level hierarchy (h1 → h2 → h3) with consistent font sizes and weights.

---

## Consistent Visual Treatments

### Spacing and Padding

```tsx
// GOOD - Consistent spacing using Tailwind scale
<Card className="p-8">           {/* Outer card padding */}
  <div className="space-y-6">    {/* Section gaps */}
    <div className="space-y-3">  {/* Item gaps */}
      <label className="mb-2">Name</label>
      <input className="px-4 py-3" />
    </div>
  </div>
</Card>

// BAD - Arbitrary spacing
<Card style={{ padding: '31px' }}>
  <div style={{ marginBottom: '17px' }}>
    <label style={{ marginBottom: '9px' }}>Name</label>
    <input style={{ padding: '13px 19px' }} />
  </div>
</Card>
```

### Border Treatments

```tsx
// GOOD - Consistent border colors and widths
<div className="border border-gray-200">        {/* Dividers */}
<div className="border-2 border-tre-teal">      {/* Emphasis */}
<div className="border-l-4 border-tre-teal">    {/* Active state (sidebar) */}
<div className="border-t border-gray-100">      {/* Subtle separators */}

// BAD - Inconsistent border styles
<div style={{ border: '1.5px solid #ccc' }}>
<div className="border-4 border-blue-500">
```

### Shadow Consistency

```tsx
// GOOD - Progressive shadow elevation
<div className="shadow-sm">              {/* Default cards */}
<div className="shadow-md hover:shadow-lg transition-shadow">  {/* Interactive cards */}
<div className="shadow-2xl">             {/* Modals only */}

// BAD - Random shadow usage
<div className="shadow-xl">
  <div className="shadow-lg">
    <div className="shadow-md">
      <p className="shadow-sm">Text</p>
    </div>
  </div>
</div>
```

---

## Integration with Lucide Icons

### Icon Sizing and Alignment

```tsx
import { FileText, Upload, Download, AlertCircle, CheckCircle } from 'lucide-react';

// GOOD - Icons aligned with text, consistent sizing
<button className="flex items-center gap-2">
  <Upload className="w-5 h-5" />
  <span>Upload PDF</span>
</button>

<div className="flex items-center gap-3">
  <CheckCircle className="w-6 h-6 text-green-600" />
  <p className="text-base">Processing complete</p>
</div>

// BAD - Misaligned icons, inconsistent sizes
<button>
  <Upload className="w-8 h-3" />  {/* Distorted aspect ratio */}
  Upload PDF
</button>
```

### Icon Colors

```tsx
// GOOD - Semantic icon colors
<FileText className="w-12 h-12 text-tre-teal" />       {/* Brand accent */}
<AlertCircle className="w-5 h-5 text-red-600" />       {/* Error state */}
<CheckCircle className="w-5 h-5 text-green-600" />     {/* Success state */}
<Info className="w-5 h-5 text-blue-600" />             {/* Info state */}

// BAD - Random colors
<FileText className="w-12 h-12 text-purple-500" />     {/* Not in brand palette */}
```

### Icon-Only Buttons

```tsx
// GOOD - Accessible icon button with tooltip
<button
  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
  aria-label="Download CSV"
  title="Download CSV"
>
  <Download className="w-5 h-5 text-gray-700" />
</button>

// BAD - No accessibility attributes
<button className="p-2">
  <Download className="w-5 h-5" />
</button>
```

---

## Component Composition

### Compound Components Pattern

```tsx
// DataTable with compound components for flexibility
function DataTable<T extends object>({ children, data }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        {children}
      </table>
    </div>
  );
}

DataTable.Header = function Header({ children }: { children: React.ReactNode }) {
  return (
    <thead className="bg-gray-50 border-b border-gray-200">
      <tr>{children}</tr>
    </thead>
  );
};

DataTable.HeaderCell = function HeaderCell({ children, sortable }: HeaderCellProps) {
  return (
    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
      {children}
      {sortable && <ChevronDown className="w-4 h-4 inline ml-2" />}
    </th>
  );
};

DataTable.Body = function Body({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-gray-100">{children}</tbody>;
};

DataTable.Row = function Row({ children }: { children: React.ReactNode }) {
  return <tr className="hover:bg-gray-50 transition-colors">{children}</tr>;
};

DataTable.Cell = function Cell({ children }: { children: React.ReactNode }) {
  return <td className="px-6 py-4 text-sm text-gray-700">{children}</td>;
};

// Usage
<DataTable data={entries}>
  <DataTable.Header>
    <DataTable.HeaderCell sortable>Name</DataTable.HeaderCell>
    <DataTable.HeaderCell>Address</DataTable.HeaderCell>
  </DataTable.Header>
  <DataTable.Body>
    {entries.map(entry => (
      <DataTable.Row key={entry.id}>
        <DataTable.Cell>{entry.name}</DataTable.Cell>
        <DataTable.Cell>{entry.address}</DataTable.Cell>
      </DataTable.Row>
    ))}
  </DataTable.Body>
</DataTable>
```

### WARNING: Overly Generic Components

**The Problem:**

```tsx
// BAD - Too many props, impossible to reason about
<Button
  variant="primary"
  size="lg"
  color="blue"
  rounded="full"
  shadow="xl"
  leftIcon={<Upload />}
  rightIcon={<ChevronRight />}
  loading={isLoading}
  disabled={isDisabled}
  fullWidth
  uppercase
  className="custom-override"
>
  Upload
</Button>
```

**Why This Breaks:**
1. Prop explosion makes the component hard to maintain
2. Too many variants dilute design consistency
3. Custom className overrides defeat the purpose of variants

**The Fix:** Create specific button components for each use case (PrimaryButton, SecondaryButton, DangerButton) with minimal props.