All 5 files updated. Key corrections made across the skill:

**Critical fixes:**
- All `StorageService` methods are **synchronous** — removed all incorrect `await` calls throughout
- Corrected method signatures: `upload_file(content, path, content_type)` not `upload_file(file_content, filename, subfolder)`
- `download_file()` returns `None` on miss — it does NOT raise `FileNotFoundError`
- Documented the 4 global instances: `storage_service`, `rrc_storage`, `upload_storage`, `profile_storage`

**New in this revision:**
- `errors.md`: Added specific warning about the `None` return vs `FileNotFoundError` confusion (common trap from old docs)
- `errors.md`: Added production fallback detection via `gcloud logging read`
- `modules.md`: Accurate lazy `_init_client()` pattern with `_initialized` flag
- `types.md`: `ProfileStorage.get_profile_image_url()` returns API proxy URL (not GCS signed URL) — important nuance
- `patterns.md`: BinaryIO seek behavior when GCS falls back to local