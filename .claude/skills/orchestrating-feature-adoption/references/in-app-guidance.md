# In-App Guidance Reference

## Contents
- Tooltips and Hints
- Interactive Tours
- Contextual Help Links
- Feature Highlights
- Error State Guidance

---

## Tooltips and Hints

**Use sparingly.** For internal tools, assume users will ask you directly. Only tooltip **non-obvious** features.

### Pattern: Hover Tooltip for Complex Fields

```tsx
// Proration.tsx - Explain NRA calculation field
import { Info } from 'lucide-react';
import { useState } from 'react';

function NraTooltip() {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="text-gray-400 hover:text-gray-600"
      >
        <Info className="w-4 h-4" />
      </button>
      
      {showTooltip && (
        <div className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg">
          <p className="mb-1 font-semibold">Net Revenue Acre (NRA)</p>
          <p>
            Calculated as: Gross Acres × Net Revenue Interest (NRI).
            Used to determine proportional revenue distribution.
          </p>
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
            <div className="border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      )}
    </div>
  );
}
```

**WARNING: Don't use third-party tooltip libraries** (Tippy, Floating UI) for 2-3 tooltips. The code above is sufficient and eliminates a dependency.

---

## Interactive Tours

**For small internal teams, tours are overkill.** Instead, use **single-step hints** that persist until dismissed.

### Pattern: Dismissible Feature Callout

```tsx
// Revenue.tsx - Point out multi-file upload
const [showMultiUploadHint, setShowMultiUploadHint] = useState(false);

useEffect(() => {
  const dismissed = localStorage.getItem('revenue_multi_upload_hint_dismissed');
  const hasUploadedMultiple = localStorage.getItem('revenue_multi_upload_used');
  
  if (!dismissed && !hasUploadedMultiple) {
    setShowMultiUploadHint(true);
  }
}, []);

// Inline hint above file upload
{showMultiUploadHint && (
  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-start gap-3">
    <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
    <div className="flex-1">
      <p className="text-sm text-blue-900">
        <strong>Tip:</strong> You can upload multiple revenue PDFs at once.
        Select multiple files or drag a folder.
      </p>
    </div>
    <button
      onClick={() => {
        setShowMultiUploadHint(false);
        localStorage.setItem('revenue_multi_upload_hint_dismissed', 'true');
      }}
      className="text-blue-600 hover:text-blue-800"
    >
      <X className="w-4 h-4" />
    </button>
  </div>
)}
```

**When You Might Be Tempted to Use a Tour Library:**
- User asks "How do I do X?" repeatedly
- Reality: Just add it to Help.tsx FAQ section instead

---

## Contextual Help Links

**Every error state should link to Help.tsx or external docs.**

### Pattern: Error → FAQ Deeplink

```tsx
// Title.tsx - Link to specific FAQ on upload failure
const [error, setError] = useState<string | null>(null);

{error && (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
    <div className="flex items-start gap-3">
      <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
      <div className="flex-1">
        <p className="font-medium text-red-900 text-sm mb-1">Upload failed</p>
        <p className="text-sm text-red-800">{error}</p>
        
        {/* Link to relevant FAQ */}
        {error.includes('format') && (
          <Link
            to="/help#file-formats"
            className="text-sm text-red-700 underline hover:text-red-900 mt-2 inline-block"
          >
            What file formats are supported? →
          </Link>
        )}
        
        {error.includes('size') && (
          <Link
            to="/help#file-size-limits"
            className="text-sm text-red-700 underline hover:text-red-900 mt-2 inline-block"
          >
            View file size limits →
          </Link>
        )}
      </div>
    </div>
  </div>
)}
```

**Implementation note:** Help.tsx needs anchor IDs on FAQ items:

```tsx
// Help.tsx - Add IDs for deeplinking
{filteredFaqs.map((faq, index) => (
  <div
    key={index}
    id={faq.id} // ← Add this
    className="p-4"
  >
    {/* ... */}
  </div>
))}

// Update FAQ data:
const faqs = [
  {
    id: 'file-formats',
    question: 'What file formats are supported?',
    answer: '...',
  },
  {
    id: 'file-size-limits',
    question: 'Are there file size limits?',
    answer: 'Maximum 50MB per file. For larger files, contact support.',
  },
  // ...
];
```

---

## Feature Highlights

**Pattern: Temporary badge on new features**

```tsx
// Sidebar.tsx - Show "New" badge on Proration link
const [showProrationBadge, setShowProrationBadge] = useState(false);

useEffect(() => {
  const badgeDismissed = localStorage.getItem('proration_rrc_auto_badge_dismissed');
  const badgeExpiry = localStorage.getItem('proration_rrc_auto_badge_expiry');
  
  // Show badge for 7 days after feature launch
  const launchDate = new Date('2026-02-01'); // Feature launch date
  const expiryDate = new Date(launchDate.getTime() + 7 * 24 * 60 * 60 * 1000);
  
  if (!badgeDismissed && new Date() < expiryDate) {
    setShowProrationBadge(true);
  }
}, []);

// Sidebar link:
<Link to="/proration" className="relative flex items-center gap-3 px-4 py-3 ...">
  <Calculator className="w-5 h-5" />
  <span>Proration</span>
  
  {showProrationBadge && (
    <span className="absolute right-4 top-1/2 -translate-y-1/2 px-2 py-0.5 bg-tre-teal text-tre-navy text-xs font-semibold rounded-full">
      New
    </span>
  )}
</Link>
```

---

## Error State Guidance

**Every upload/processing failure should explain next steps.**

### Pattern: Actionable Error Messages

```tsx
// Extract.tsx - Specific error guidance
const handleUploadError = (error: Error) => {
  let message = error.message;
  let helpText = null;
  
  if (error.message.includes('PDF')) {
    message = 'Unable to extract text from PDF';
    helpText = (
      <>
        The PDF may be image-based (scanned). Try using OCR software first, or{' '}
        <a href="mailto:support@tablerockenergy.com" className="underline">
          contact support
        </a>{' '}
        for help.
      </>
    );
  } else if (error.message.includes('timeout')) {
    message = 'Processing timed out';
    helpText = (
      <>
        Large documents take longer. Try splitting the PDF into smaller files,
        or increase the timeout in Settings.
      </>
    );
  } else if (error.message.includes('format')) {
    message = 'Unsupported file format';
    helpText = (
      <>
        We only support PDF, DOCX, XLS, and CSV files.{' '}
        <Link to="/help#file-formats" className="underline">
          View all supported formats
        </Link>
      </>
    );
  }
  
  setError({ message, helpText });
};

// Render:
{error && (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
      <div>
        <p className="font-medium text-red-900 text-sm">{error.message}</p>
        {error.helpText && (
          <p className="text-sm text-red-800 mt-1">{error.helpText}</p>
        )}
      </div>
    </div>
  </div>
)}
```

**The Fix is Better Than Generic:**
- ❌ "An error occurred. Please try again."
- ✅ "PDF is image-based. Try OCR first, or contact support."