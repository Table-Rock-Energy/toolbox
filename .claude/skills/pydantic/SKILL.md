Three files updated. Here's what changed:

**Fix applied across all 3 skill files:** Replaced the deprecated `class Config:` pattern with the correct Pydantic v2 style `model_config = SettingsConfigDict(env_file=".env")` — matching what `backend/app/core/config.py` actually uses.

Specifically:
- `SKILL.md`: Both Settings examples updated
- `references/patterns.md`: Settings configuration section updated; added an explicit BAD example showing `class Config:` so it's clearly marked as the wrong pattern
- `references/workflows.md`: "Add New Environment Variable" workflow updated