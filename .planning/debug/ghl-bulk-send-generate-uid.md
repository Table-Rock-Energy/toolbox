---
status: resolved
trigger: "When trying to send the sync to GHL via bulk-send, a 500 error occurs because `generate_uid()` is called without its 3 required positional arguments: 'check_number', 'property_number', and 'line_number'."
created: 2026-02-27T00:00:00Z
updated: 2026-02-27T00:00:00Z
---

## Current Focus

hypothesis: Fix is applied and syntax validated
test: Python syntax check passed, now need human verification that bulk-send works end-to-end
expecting: User confirms GHL bulk-send now completes without 500 error
next_action: Request human verification of the fix

## Symptoms

expected: GHL bulk-send should sync contacts successfully
actual: 500 Internal Server Error on POST /api/ghl/contacts/bulk-send
errors: generate_uid() missing 3 required positional arguments: 'check_number', 'property_number', and 'line_number'
reproduction: Click sync/send button for GHL contacts bulk-send
started: Current issue, likely introduced during recent GHL integration work

## Eliminated

## Evidence

- timestamp: 2026-02-27T00:00:00Z
  checked: toolbox/backend/app/utils/helpers.py line 141
  found: generate_uid() requires 3 positional arguments: check_number, property_number, line_number
  implication: This function is revenue-specific for generating UIDs for revenue rows

- timestamp: 2026-02-27T00:00:00Z
  checked: toolbox/backend/app/api/ghl.py line 326
  found: generate_uid() is called without any arguments in bulk_send_endpoint()
  implication: This is the source of the 500 error - function called incorrectly

- timestamp: 2026-02-27T00:00:00Z
  checked: Other API files (ghl_prep.py, title.py)
  found: Standard pattern is to use str(uuid4()) for job ID generation
  implication: uuid4 is the correct approach for generating unique job IDs

## Resolution

root_cause: Line 326 in ghl.py calls generate_uid() without arguments, but the function requires 3 revenue-specific parameters (check_number, property_number, line_number). The GHL bulk-send feature needs a generic UUID generator, not a revenue-specific UID function.

fix: |
  1. Added uuid4 import at line 18: `from uuid import uuid4`
  2. Removed incorrect import: `from app.utils.helpers import generate_uid`
  3. Changed line 326 from `job_id = generate_uid()` to `job_id = str(uuid4())`
  This matches the pattern used in ghl_prep.py and other API files.

verification: |
  Self-verified:
  - Python syntax check passed (py_compile)
  - Import statement added correctly
  - Usage matches pattern in other API files (ghl_prep.py line 49)

  Awaiting human verification:
  - GHL bulk-send completes without 500 error
  - Job ID is generated and returned correctly
  - SSE progress streaming works with new UUID format

files_changed: ["/Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox/backend/app/api/ghl.py"]
