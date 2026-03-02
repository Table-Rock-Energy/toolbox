# In-App Guidance Reference

## Contents
- Tooltip Patterns
- Inline Help & Contextual Docs
- Error Recovery Guidance
- Field-Level Help
- Anti-Patterns

---

## Tooltip Patterns

Table Rock Tools currently has **no tooltip implementation**. Add tooltips for:
- Icon-only buttons
- Technical terms (NRA, RRC, OCC)
- Status indicators

### Simple CSS Tooltip (No Library)

```tsx
// Reusable Tooltip component
export function Tooltip({ 
  children, 
  content 
}: { 
  children: React.ReactNode
  content: string 
}) {
  return (
    <div className="relative group inline-block">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-gray-900 text-white text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
        {content}
        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900" />
      </div>
    </div>
  )
}

// Usage in Extract.tsx
<Tooltip content="Entries with incomplete addresses or ambiguous entity types">
  <button className="flex items-center gap-1 text-sm text-gray-600">
    <Flag className="w-4 h-4" />
    Flagged Entries ({flaggedCount})
  </button>
</Tooltip>
```

### Technical Term Tooltips

```tsx
// Proration.tsx - Explain NRA
<h2 className="text-xl font-oswald font-semibold text-tre-navy mb-4">
  Calculate{' '}
  <Tooltip content="Net Revenue Allocation - determines how revenue is distributed based on mineral interests">
    <span className="underline decoration-dotted decoration-gray-400 cursor-help">
      NRA
    </span>
  </Tooltip>
</h2>
```

---

## Inline Help & Contextual Docs

### Collapsible Help Sections

```tsx
// Extract.tsx - Show help for flagged entries
{flaggedCount > 0 && (
  <details className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
    <summary className="cursor-pointer font-medium text-blue-900 flex items-center gap-2">
      <HelpCircle className="w-4 h-4" />
      What are flagged entries?
    </summary>
    <div className="mt-3 text-sm text-blue-800 space-y-2">
      <p>
        Entries are automatically flagged when:
      </p>
      <ul className="list-disc list-inside ml-2 space-y-1">
        <li>Address contains "UNKNOWN" or is incomplete</li>
        <li>Entity type is ambiguous (e.g., "LLC" vs "Trust")</li>
        <li>Name format is unusual or contains special characters</li>
      </ul>
      <p className="mt-3">
        <strong>What to do:</strong> Review each flagged entry manually and add notes to clarify details before exporting.
      </p>
    </div>
  </details>
)}
```

### Smart Empty States with Next Steps

```tsx
// Proration.tsx - Empty state with prerequisite guidance
{!rrcDataLoaded && (
  <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
    <Database className="w-16 h-16 mx-auto mb-4 text-gray-300" />
    <h3 className="font-oswald font-semibold text-lg mb-2">RRC Data Required</h3>
    <p className="text-gray-600 mb-6 max-w-md mx-auto">
      Before processing mineral holders, download the latest Railroad Commission proration data.
    </p>
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left max-w-lg mx-auto">
      <p className="text-sm text-blue-900 mb-3">
        <strong>What is RRC data?</strong>
      </p>
      <p className="text-sm text-blue-800">
        The Texas Railroad Commission publishes monthly proration schedules for oil and gas wells. 
        This data is used to calculate Net Revenue Allocations based on lease assignments.
      </p>
    </div>
    <button
      onClick={handleDownloadRRC}
      className="px-6 py-3 bg-tre-teal text-white rounded-lg font-medium hover:bg-tre-teal/90"
    >
      Download RRC Data
    </button>
  </div>
)}
```

### Contextual Help Links

```tsx
// Link to specific Help section from tool page
<div className="flex items-center justify-between mb-6">
  <h1 className="text-3xl font-oswald font-semibold text-tre-navy">Extract</h1>
  <a
    href="/help#extract-tool"
    className="flex items-center gap-1 text-sm text-tre-teal hover:underline"
  >
    <HelpCircle className="w-4 h-4" />
    Extract Help
  </a>
</div>
```

**Add anchor links to Help.tsx:**

```tsx
// toolbox/frontend/src/pages/Help.tsx
const faqs = [
  {
    id: 'extract-tool',
    question: 'How does the Extract tool work?',
    answer: 'The Extract tool uses PyMuPDF and pdfplumber to parse OCC Exhibit A PDFs...',
  },
  // ... other FAQs
]

// Render with id anchors
{filteredFaqs.map((faq) => (
  <div key={faq.id} id={faq.id} className="p-4">
    {/* ... existing content */}
  </div>
))}
```

---

## Error Recovery Guidance

### Upload Errors with Actionable Messages

```tsx
// Extract.tsx - Show specific error guidance
{error && (
  <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
      <div className="flex-1">
        <p className="font-medium text-red-900">Upload Failed</p>
        <p className="text-sm text-red-700 mt-1">{error}</p>
        
        {/* Specific recovery steps based on error type */}
        {error.includes('file size') && (
          <div className="mt-3 text-sm text-red-800">
            <p className="font-medium mb-1">How to fix:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Reduce file size by compressing the PDF</li>
              <li>Split large PDFs into smaller sections</li>
              <li>Contact support if file must exceed 50MB</li>
            </ul>
          </div>
        )}
        
        {error.includes('parsing') && (
          <div className="mt-3 text-sm text-red-800">
            <p className="font-medium mb-1">Possible causes:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>PDF is scanned image (not searchable text)</li>
              <li>PDF is password-protected or corrupted</li>
              <li>File format is not supported</li>
            </ul>
            <button
              onClick={handleRetry}
              className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  </div>
)}
```

### Network Error Recovery

```tsx
// Handle API failures gracefully
const [retryCount, setRetryCount] = useState(0)

const handleUpload = async (file: File) => {
  try {
    const response = await fetch(`${API_BASE}/extract/upload`, {
      method: 'POST',
      body: formData,
    })
    
    if (!response.ok) {
      throw new Error('Upload failed')
    }
  } catch (err) {
    if (retryCount < 3) {
      // Auto-retry with exponential backoff
      const delay = Math.pow(2, retryCount) * 1000
      setTimeout(() => {
        setRetryCount(retryCount + 1)
        handleUpload(file)
      }, delay)
      
      setError(`Upload failed. Retrying in ${delay / 1000}s...`)
    } else {
      setError('Upload failed after 3 attempts. Please check your connection and try again.')
    }
  }
}
```

---

## Field-Level Help

### Input Field Help Text

```tsx
// Settings.tsx - Show help for each field
<div>
  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
    Email Address
  </label>
  <input
    type="email"
    id="email"
    className="w-full px-4 py-2 border rounded-lg"
  />
  <p className="text-xs text-gray-500 mt-1">
    This email is used for notifications and job summaries. Must match your Table Rock domain.
  </p>
</div>
```

### Validation Feedback

```tsx
// Real-time validation with helpful messages
const [emailError, setEmailError] = useState<string | null>(null)

const validateEmail = (email: string) => {
  if (!email.includes('@tablerocktx.com')) {
    setEmailError('Email must be a Table Rock domain address (@tablerocktx.com)')
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setEmailError('Please enter a valid email address')
  } else {
    setEmailError(null)
  }
}

<div>
  <input
    type="email"
    value={email}
    onChange={(e) => {
      setEmail(e.target.value)
      validateEmail(e.target.value)
    }}
    className={`w-full px-4 py-2 border rounded-lg ${
      emailError ? 'border-red-500' : 'border-gray-300'
    }`}
  />
  {emailError && (
    <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
      <AlertCircle className="w-3 h-3" />
      {emailError}
    </p>
  )}
</div>
```

---

## Anti-Patterns

### WARNING: Chatbot for Simple FAQs

**The Problem:**

```tsx
// BAD - Chatbot widget for static help content
<ChatbotWidget>
  <Chatbot onMessage={handleMessage} />
</ChatbotWidget>
```

**Why This Breaks:**
1. **Overkill** - Simple FAQs don't need AI/chat
2. **Slow** - Typing questions slower than scanning FAQs
3. **Unpredictable** - AI might give wrong answers about internal processes

**The Fix:**

Use **searchable FAQ accordion** (already implemented in Help.tsx):

```tsx
// GOOD - Help.tsx pattern (lines 54-99)
<input
  type="text"
  placeholder="Search for help..."
  value={searchQuery}
  onChange={(e) => setSearchQuery(e.target.value)}
  className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg"
/>

{filteredFaqs.map((faq, index) => (
  <div key={index} className="p-4">
    <button onClick={() => setExpandedFaq(expandedFaq === index ? null : index)}>
      <span className="font-medium text-gray-900">{faq.question}</span>
    </button>
    {expandedFaq === index && (
      <div className="mt-3 text-gray-600 text-sm">{faq.answer}</div>
    )}
  </div>
))}
```

**When You Might Be Tempted:**
When you want to feel "cutting-edge" with AI. Resist. Static FAQs are faster, more reliable, and easier to maintain.

### WARNING: Too Many Inline Tooltips

**The Problem:**

```tsx
// BAD - Tooltip on every field
<Tooltip content="Your first name">
  <input placeholder="First Name" />
</Tooltip>
<Tooltip content="Your last name">
  <input placeholder="Last Name" />
</Tooltip>
<Tooltip content="Your email address">
  <input placeholder="Email" />
</Tooltip>
```

**Why This Breaks:**
1. **Noise** - Obvious fields don't need explanation
2. **Accessibility** - Screen readers announce every tooltip
3. **Distraction** - Hover states everywhere

**The Fix:**

Only add tooltips for **ambiguous or technical terms**:

```tsx
// GOOD - Tooltips only where needed
<input placeholder="First Name" />
<input placeholder="Last Name" />
<div>
  <label className="flex items-center gap-1">
    Email
    <Tooltip content="Must be a @tablerocktx.com address">
      <HelpCircle className="w-3 h-3 text-gray-400" />
    </Tooltip>
  </label>
  <input placeholder="you@tablerocktx.com" />
</div>