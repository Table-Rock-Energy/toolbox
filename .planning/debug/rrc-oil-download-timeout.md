---
status: awaiting_human_verify
trigger: "rrc-oil-download-timeout"
created: 2026-03-03T00:00:00Z
updated: 2026-03-03T00:00:04Z
---

## Current Focus

hypothesis: CONFIRMED - Oil CSV download exceeds 300s timeout while Gas completes within 300s
test: The Feb 6 fix increased Cloud Run timeout to 600s but forgot to update the requests timeout in download_oil_data()
expecting: Increasing timeout from 300s to 600s (or higher) will fix the oil download
next_action: Implement fix by increasing timeout in both download_oil_data() and download_gas_data() to 900s for safety margin

## Symptoms

expected: Both Oil and Gas RRC data should download and sync successfully (Gas gets ~138,985 rows)
actual: Gas OK (138,985 rows), Oil fails with timeout after 300 seconds
errors: Error downloading oil data: HTTPSConnectionPool(host='webapps2.rrc.texas.gov', port=443): Read timed out. (read timeout=300)
reproduction: Click sync/download RRC data button on the Proration page in the web UI
started: Recurring issue. User says they thought it was fixed last month but it's happening again.

## Eliminated

## Evidence

- timestamp: 2026-03-03T00:00:00Z
  checked: rrc_data_service.py lines 100-151 (download_oil_data method)
  found: Timeout is hardcoded to 300 seconds on line 126 for CSV download
  implication: Oil CSV likely exceeds 300s to download, while Gas CSV (same 300s timeout) completes in time

- timestamp: 2026-03-03T00:00:01Z
  checked: Git history for timeout fixes
  found: Commit 1bbc90f (Feb 6, 2026) increased Cloud Run timeout to 600s and moved DB sync to background
  implication: Cloud Run timeout was increased but the requests library timeout in download_oil_data() was NOT updated

- timestamp: 2026-03-03T00:00:02Z
  checked: download_gas_data method (lines 152-202)
  found: Gas also uses 300s timeout (line 178), but completes successfully with 138,985 rows
  implication: Oil CSV is significantly larger than Gas CSV, causing it to exceed 300s

- timestamp: 2026-03-03T00:00:03Z
  checked: .github/workflows/deploy.yml Cloud Run configuration
  found: Cloud Run timeout is 600s (line 40) which is less than the 900s requests timeout needed
  implication: Even if requests timeout is increased, Cloud Run would terminate the request at 600s, need to increase both

## Resolution

root_cause: The Feb 6, 2026 fix (commit 1bbc90f) increased Cloud Run timeout from 300s to 600s but failed to update the requests library timeout in download_oil_data() method. Oil CSV is larger than Gas CSV, so it exceeds the 300s timeout while Gas completes successfully.
fix:
  1. Increased timeout in both download_oil_data() and download_gas_data() from 300s to 900s (15 minutes)
  2. Increased Cloud Run timeout from 600s to 1200s (20 minutes) to prevent Cloud Run from terminating the request before download completes
verification:
  - Python syntax check passed
  - Need human verification: test oil download via UI in production after deployment to confirm it completes without timeout error
files_changed:
  - backend/app/services/proration/rrc_data_service.py (lines 126, 178)
  - .github/workflows/deploy.yml (line 40)
