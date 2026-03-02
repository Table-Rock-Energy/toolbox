# Activation & Onboarding Reference

## Contents
- Empty State Conversion
- First Success Paths
- Progressive Disclosure
- Setup Wizards (Per Tool)
- Help Resources Integration

---

## Empty State Conversion

**The Problem:** Dashboard shows placeholder text when `recentActivity.length === 0` but doesn't drive action.

```tsx
// BAD - Just tells users there's no data
<div className="p-8 text-center text-gray-500">
  <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
  <p className="font-medium">No activity yet</p>
  <p className="text-sm mt-1">Tool usage will appear here</p>
</div>
```

**Why This Fails:**
1. No next step—user doesn't know what to do
2. Doesn't educate on which tool to start with
3. Missed opportunity to create first success

**The Fix:**

```tsx
// GOOD - Empty state with primary CTA
<div className="p-8 text-center">
  <div className="max-w-md mx-auto">
    <FileSearch className="w-16 h-16 mx-auto mb-4 text-tre-teal" />
    <h3 className="font-oswald font-semibold text-tre-navy text-lg mb-2">
      Ready to extract your first document?
    </h3>
    <p className="text-sm text-gray-600 mb-6">
      Most teams start with Extract to pull party data from OCC Exhibit A PDFs.
      Takes less than 2 minutes.
    </p>
    <div className="flex gap-3 justify-center">
      <Link
        to="/extract"
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-tre-teal text-tre-navy rounded-lg font-medium hover:bg-tre-teal/90"
      >
        Try Extract Tool <ArrowRight className="w-4 h-4" />
      </Link>
      <Link
        to="/help"
        className="inline-flex items-center gap-2 px-5 py-2.5 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50"
      >
        <HelpCircle className="w-4 h-4" />
        View All Tools
      </Link>
    </div>
  </div>
</div>
```

---

## First Success Paths

**Define the "aha moment" for each tool:**

| Tool | First Success | Time to Value |
|------|---------------|---------------|
| Extract | Uploaded PDF → see 10+ parties extracted | ~2 min |
| Title | Uploaded Excel → see deduplicated owners | ~3 min |
| Proration | Uploaded mineral holders → see NRA calculations | ~5 min (requires RRC data) |
| Revenue | Uploaded revenue PDF → see M1 CSV ready | ~2 min |

**Pattern: Post-Upload Success Modal**

```tsx
// Extract.tsx - Show success modal after first upload
const [showSuccessModal, setShowSuccessModal] = useState(false);

const handleUploadComplete = (result: ExtractionResult) => {
  setData(result);
  
  // Check if this is user's first extraction
  const firstExtraction = localStorage.getItem('first_extraction_complete');
  if (!firstExtraction) {
    localStorage.setItem('first_extraction_complete', 'true');
    setShowSuccessModal(true);
  }
};

// Modal content:
<Modal isOpen={showSuccessModal} onClose={() => setShowSuccessModal(false)}>
  <div className="text-center">
    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
      <Check className="w-8 h-8 text-green-600" />
    </div>
    <h2 className="text-xl font-oswald font-semibold text-tre-navy mb-2">
      Extraction Complete!
    </h2>
    <p className="text-gray-600 mb-4">
      We found {result.entries.length} parties in your document.
      Ready to export or process another?
    </p>
    <div className="flex gap-3 justify-center">
      <button
        onClick={() => {/* Trigger export */}}
        className="px-4 py-2 bg-tre-teal text-tre-navy rounded-lg font-medium"
      >
        Export to Excel
      </button>
      <button
        onClick={() => setShowSuccessModal(false)}
        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium"
      >
        Process Another
      </button>
    </div>
  </div>
</Modal>
```

---

## Progressive Disclosure

**Don't show all features at once.** Reveal advanced options after users complete basic flow.

```tsx
// Proration.tsx - Hide "Export to PDF" until user has results
const [showAdvancedExport, setShowAdvancedExport] = useState(false);

useEffect(() => {
  if (results && results.length > 0) {
    // User has completed at least one calculation
    const hasSeenPdfExport = localStorage.getItem('proration_pdf_export_unlocked');
    if (!hasSeenPdfExport) {
      localStorage.setItem('proration_pdf_export_unlocked', 'true');
      setShowAdvancedExport(true); // Highlight new option
    }
  }
}, [results]);

// UI: Show badge on "Export to PDF" button if newly unlocked
<button className="relative ...">
  Export to PDF
  {showAdvancedExport && (
    <span className="absolute -top-1 -right-1 flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tre-teal opacity-75"></span>
      <span className="relative inline-flex rounded-full h-3 w-3 bg-tre-teal"></span>
    </span>
  )}
</button>
```

---

## Setup Wizards (Per Tool)

**For Proration tool specifically:** RRC data must be downloaded before calculations work. Guide users through prerequisite.

```tsx
// Proration.tsx - Check RRC data status on mount
const [rrcStatus, setRrcStatus] = useState<'loading' | 'available' | 'missing'>('loading');

useEffect(() => {
  const checkRrcData = async () => {
    const response = await fetch('/api/proration/rrc/status');
    const data = await response.json();
    
    if (data.oil_count === 0 && data.gas_count === 0) {
      setRrcStatus('missing');
    } else {
      setRrcStatus('available');
    }
  };
  
  checkRrcData();
}, []);

// Show setup wizard if RRC data is missing
{rrcStatus === 'missing' && (
  <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 mb-6">
    <div className="flex items-start gap-3">
      <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0" />
      <div className="flex-1">
        <h3 className="font-semibold text-amber-900 mb-2">
          RRC Data Required
        </h3>
        <p className="text-sm text-amber-800 mb-4">
          The Proration tool needs RRC lease data to calculate NRA.
          This is a one-time setup step (takes ~2 minutes).
        </p>
        <button
          onClick={async () => {
            await fetch('/api/proration/rrc/download', { method: 'POST' });
            setRrcStatus('available');
          }}
          className="px-4 py-2 bg-amber-600 text-white rounded-lg font-medium hover:bg-amber-700"
        >
          Download RRC Data Now
        </button>
      </div>
    </div>
  </div>
)}
```

---

## Help Resources Integration

**Pattern: Contextual help links on error states**

```tsx
// Extract.tsx - Link to Help on upload failure
const [uploadError, setUploadError] = useState<string | null>(null);

{uploadError && (
  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
    <div className="flex items-start gap-3">
      <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-red-800">{uploadError}</p>
        <Link
          to="/help"
          className="text-sm text-red-700 underline hover:text-red-900 mt-2 inline-flex items-center gap-1"
        >
          View troubleshooting guide <ExternalLink className="w-3 h-3" />
        </Link>
      </div>
    </div>
  </div>
)}
```

**WARNING: Don't use generic "Contact Support" as a crutch.** For internal tools, users can walk over to your desk. Provide self-service answers in Help.tsx FAQs.