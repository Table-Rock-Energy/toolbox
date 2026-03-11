All corrections made. Here's a summary of what was fixed:

**`references/unit.md`**
- `generate_uid()` → `generate_uid(check_number, property_number, line_number)` (3 required args)
- `parse_date` test corrected to match actual supported formats (`"Dec 2024"`, not `"January 15, 2025"`)
- `await service.upload_file(...)` → sync `service.upload_file(content, path)` with correct arg order
- `service.use_gcs` → `service.is_gcs_enabled`

**`references/mocking.md`**
- `StorageService.use_gcs` → `is_gcs_enabled`
- `upload_file` calls made sync with correct `(content, path)` arg order
- `app.services.firestore_service._get_client` → `get_firestore_client` (actual function name)
- Firebase Auth mock replaced: no `verify_token` exists — now uses `app.dependency_overrides[get_current_user]` (correct FastAPI pattern)

**`references/fixtures.md`**
- Same `_get_client` → `get_firestore_client` fix
- `service.use_gcs` → `service.is_gcs_enabled`
- Removed `DATA_DIR` env var from storage mock (not actually used by StorageService)