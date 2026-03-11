# Phase 2: Encryption Hardening - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Sensitive API keys stored in Firestore are encrypted at rest, and the application refuses to start without the encryption key in production. Encryption is transparent -- the app behaves identically from the user's perspective. No UI changes.

</domain>

<decisions>
## Implementation Decisions

### Startup validation
- Fail fast in FastAPI lifespan (startup event handler in main.py) when `ENVIRONMENT=production` and `ENCRYPTION_KEY` is not set
- Hard crash with `SystemExit` and clear log message including key generation command: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Add `environment: str = "development"` field to Pydantic Settings in config.py -- check `settings.environment == "production"`
- Dev mode without ENCRYPTION_KEY: plaintext fallback with warning (current behavior preserved)

### Encryption coverage
- Encrypt ALL API keys: Gemini, Google Maps, PDL, SearchBug, GHL tokens
- Encrypt in both Firestore AND local JSON settings cache (data/app_settings.json) -- no plaintext anywhere on disk
- Encryption happens at the storage boundary: `save_app_settings` encrypts before persisting, `load_app_settings` decrypts after reading
- GHL connection_service and enrichment API already encrypt at handler level -- leave as-is, don't refactor for consistency

### Migration from plaintext
- Encrypt on next save -- when admin updates any setting, `save_app_settings` encrypts all keys before persisting
- Startup (`init_app_settings_from_firestore`) is read-only -- no migration side effects at startup
- `decrypt_value`'s graceful plaintext handling preserved: values without `enc:` prefix returned as-is (necessary for migration period)
- Runtime config (`settings.gemini_api_key` etc.) always receives decrypted plaintext -- `init_app_settings_from_firestore` passes values through `decrypt_value` before applying

### Fallback behavior
- Production with ENCRYPTION_KEY set: if encryption fails, raise an exception -- don't silently store plaintext
- Production decryption failure (e.g., key rotation): log error, return `None` -- feature appears unconfigured, admin re-enters key to fix
- Dev mode: keep existing plaintext fallback with warning
- No UI changes -- admin settings already show `has_key: true/false`, never expose actual keys

### Claude's Discretion
- Which specific keys in the settings dict to target for encryption (field name enumeration)
- How to structure the encrypt/decrypt helpers for the settings boundary (utility function vs decorator vs inline)
- Error message formatting and log levels
- Test approach for encryption (covered in Phase 3, but implementation details here are flexible)

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared/encryption.py`: Fernet encrypt/decrypt with `enc:` prefix detection -- core utility ready to use
- `_get_fernet()`: Lazy Fernet initialization from `settings.encryption_key` -- already handles missing key gracefully
- `encrypt_value()` / `decrypt_value()`: Existing API with prefix-based encrypted value detection

### Established Patterns
- `save_app_settings()` in `admin.py` (line 49): Saves to local JSON + fire-and-forget Firestore persist -- encryption choke point for admin settings
- `load_app_settings()` in `admin.py` (line 38): Reads from local JSON cache -- decryption choke point
- `init_app_settings_from_firestore()` in `admin.py` (line 73): Startup loader applies Firestore values to runtime Settings -- add decrypt_value pass-through here
- GHL `connection_service.py` and `enrichment.py` already use encrypt/decrypt at handler level -- working pattern, leave untouched
- Pydantic Settings in `config.py`: `encryption_key: Optional[str] = None` -- add `environment` field here

### Integration Points
- `main.py` startup hooks: Add ENCRYPTION_KEY validation check in FastAPI lifespan, before existing `init_app_settings_from_firestore` call
- `admin.py` settings endpoints (Gemini: line 344, Google Maps: line 388): Currently save plaintext -- will be handled by storage boundary encryption
- `config.py` Settings class: Add `environment` field for production detection
- `encryption.py` `encrypt_value`: Modify to raise exception instead of fallback when key is set but encryption fails

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 02-encryption-hardening*
*Context gathered: 2026-03-11*
