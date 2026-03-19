---
phase: quick
plan: 260319-jda
type: execute
---

<objective>
Fix ETA showing negative time in EnrichmentModal and update tool page subtitles to match actual capabilities.
</objective>

<tasks>
<task type="auto">
  <name>Task 1: Fix ETA negative time and update page subtitles</name>
  <files>
    frontend/src/components/EnrichmentModal.tsx
    frontend/src/pages/Extract.tsx
    frontend/src/pages/Revenue.tsx
  </files>
  <action>
    1. Clamp remainingSec to Math.max(0, ...) and return null when 0
    2. Extract subtitle: "PDF filings" instead of "OCC Exhibit A PDFs"
    3. Revenue subtitle: "Convert revenue statement PDFs to M1 CSV format"
  </action>
</task>
</tasks>
