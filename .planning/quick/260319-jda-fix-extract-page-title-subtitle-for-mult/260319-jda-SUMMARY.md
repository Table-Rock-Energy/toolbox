---
phase: quick
plan: 260319-jda
status: complete
---

## Summary

Fixed EnrichmentModal ETA showing negative time ("-3 minutes") by clamping `remainingSec` to `Math.max(0, ...)` and returning null at 0. Updated Extract subtitle from "OCC Exhibit A PDFs" to "PDF filings" (supports OCC, ECF, Convey 640). Updated Revenue subtitle to "Convert revenue statement PDFs to M1 CSV format" (handles EnergyLink, Enverus, Energy Transfer).

## Changes

- `frontend/src/components/EnrichmentModal.tsx`: Clamp ETA to non-negative
- `frontend/src/pages/Extract.tsx`: Updated subtitle
- `frontend/src/pages/Revenue.tsx`: Updated subtitle
