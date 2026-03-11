---
phase: 13-production-hardening
plan: 03
subsystem: frontend
tags: [documentation, help, ghl, user-facing]
dependency_graph:
  requires: []
  provides: [ghl-documentation]
  affects: []
tech_stack:
  added: []
  patterns: [accordion-ui, expandable-sections]
key_files:
  created: []
  modified:
    - toolbox/frontend/src/pages/Help.tsx
decisions: []
metrics:
  duration: 83s
  completed: 2026-02-27T15:16:35Z
---

# Phase 13 Plan 03: GHL Integration Documentation Summary

**One-liner:** Comprehensive GHL Integration help section with setup guide, field mapping table, and troubleshooting FAQ in accordion format.

## What Was Built

Added a complete GHL Integration documentation section to the Help page, positioned before the existing FAQ section. The section includes:

1. **Setup Guide**: 4 expandable accordion steps covering:
   - Creating a Private Integration Token
   - Finding Your Location ID
   - Adding a Connection in Settings
   - Sending Your First Batch

2. **Field Mapping Table**: Compact table showing 9 CSV → GHL field mappings with:
   - CSV Column names
   - GHL Field names (with font-mono styling)
   - Required/Optional badges (green badge for required, gray text for optional)
   - Notes column with additional context

3. **Troubleshooting FAQ**: 6 expandable accordion items covering:
   - Why Send to GHL button is disabled
   - Why some contacts failed
   - Daily limit explanation
   - Contact owner assignment logic
   - Page closure during send
   - Retrying failed contacts

## Technical Implementation

- **New imports**: Added `Settings` and `ChevronDown` icons from lucide-react
- **State management**: Added separate accordion state for GHL sections (`openGhlStep`, `openGhlFaq`)
- **Styling**: Used existing Help page patterns for consistency:
  - Section header with icon in `bg-tre-teal/10` rounded container
  - Accordion items with `border-gray-200` borders and `hover:bg-gray-50` transitions
  - Field mapping table with alternating row backgrounds (`bg-white` / `bg-gray-50/50`)
  - Uppercase tracking-wide subsection headers
  - ChevronDown icon with `rotate-180` transform on expand

## Deviations from Plan

None - plan executed exactly as written.

## Files Changed

- **toolbox/frontend/src/pages/Help.tsx**: Added 174 lines
  - Added 3 new data arrays: `ghlSetupSteps`, `ghlFaqs`, `fieldMapping`
  - Added 2 new state variables for accordion management
  - Added complete GHL Integration section with 3 subsections
  - Imported Settings and ChevronDown icons

## Testing

- TypeScript compilation: ✓ Passed (`npx tsc --noEmit`)
- All accordions work independently (separate state management)
- Field mapping table displays correctly with required/optional indicators
- Section positioned before existing FAQ as specified

## Commit

- **8170e2b**: feat(13-03): add GHL Integration documentation to Help page

## Self-Check: PASSED

✓ Modified file exists: toolbox/frontend/src/pages/Help.tsx
✓ Commit exists: 8170e2b
✓ TypeScript compilation passes
✓ All specified content added (4 setup steps, 9 field mappings, 6 troubleshooting FAQs)
