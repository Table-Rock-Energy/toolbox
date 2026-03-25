"""Tests for SQLAlchemy database models completeness."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.models.db_models import (
    AuditLog,
    AppConfig,
    ExtractEntry,
    GHLConnection,
    Job,
    ProrationRow,
    RevenueRow,
    RevenueStatement,
    RRCCountyStatus,
    RRCDataSync,
    RRCGasProration,
    RRCMetadata,
    RRCOilProration,
    RRCSyncJob,
    TitleEntry,
    User,
    UserPreference,
)

# All 17 models mapped to expected table names
ALL_MODELS = {
    "users": User,
    "jobs": Job,
    "extract_entries": ExtractEntry,
    "title_entries": TitleEntry,
    "proration_rows": ProrationRow,
    "revenue_statements": RevenueStatement,
    "revenue_rows": RevenueRow,
    "rrc_oil_proration": RRCOilProration,
    "rrc_gas_proration": RRCGasProration,
    "rrc_data_syncs": RRCDataSync,
    "audit_logs": AuditLog,
    "app_config": AppConfig,
    "user_preferences": UserPreference,
    "rrc_county_status": RRCCountyStatus,
    "ghl_connections": GHLConnection,
    "rrc_sync_jobs": RRCSyncJob,
    "rrc_metadata": RRCMetadata,
}


class TestModelCompleteness:
    """Verify all 17 models exist with correct table names."""

    def test_all_17_models_importable(self):
        assert len(ALL_MODELS) == 17

    @pytest.mark.parametrize("table_name,model_cls", ALL_MODELS.items())
    def test_model_tablename(self, table_name: str, model_cls):
        assert model_cls.__tablename__ == table_name


class TestUserModel:
    """Verify User model has auth columns for local JWT auth."""

    def _columns(self):
        return {c.name: c for c in User.__table__.columns}

    def test_user_model_auth_columns(self):
        cols = self._columns()
        for col_name in ("password_hash", "role", "scope", "tools", "added_by"):
            assert col_name in cols, f"User missing column: {col_name}"

    def test_user_id_has_default(self):
        cols = self._columns()
        assert cols["id"].default is not None, "User.id should have a default callable"

    def test_user_password_hash_nullable(self):
        cols = self._columns()
        assert cols["password_hash"].nullable is True

    def test_user_role_default(self):
        cols = self._columns()
        assert cols["role"].default.arg == "user"

    def test_user_scope_default(self):
        cols = self._columns()
        assert cols["scope"].default.arg == "all"

    def test_user_tools_is_jsonb(self):
        cols = self._columns()
        assert "JSONB" in str(cols["tools"].type) or "JSON" in str(cols["tools"].type)

    def test_user_added_by_nullable(self):
        cols = self._columns()
        assert cols["added_by"].nullable is True


class TestAppConfigModel:
    """Verify AppConfig model."""

    def _columns(self):
        return {c.name: c for c in AppConfig.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        for name in ("key", "data", "updated_at"):
            assert name in cols, f"AppConfig missing column: {name}"

    def test_key_is_primary_key(self):
        cols = self._columns()
        assert cols["key"].primary_key is True

    def test_data_is_jsonb(self):
        cols = self._columns()
        assert "JSONB" in str(cols["data"].type) or "JSON" in str(cols["data"].type)


class TestUserPreferenceModel:
    """Verify UserPreference model."""

    def _columns(self):
        return {c.name: c for c in UserPreference.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        for name in ("id", "user_id", "data", "updated_at"):
            assert name in cols, f"UserPreference missing column: {name}"

    def test_id_is_primary_key(self):
        cols = self._columns()
        assert cols["id"].primary_key is True

    def test_user_id_has_foreign_key(self):
        cols = self._columns()
        fk_targets = [str(fk.target_fullname) for fk in cols["user_id"].foreign_keys]
        assert "users.id" in fk_targets

    def test_user_id_is_unique(self):
        cols = self._columns()
        assert cols["user_id"].unique is True

    def test_has_user_relationship(self):
        mapper = inspect(UserPreference)
        rel_names = [r.key for r in mapper.relationships]
        assert "user" in rel_names


class TestRRCCountyStatusModel:
    """Verify RRCCountyStatus model."""

    def _columns(self):
        return {c.name: c for c in RRCCountyStatus.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        for name in ("key", "status", "oil_record_count", "last_downloaded_at", "error_message", "updated_at"):
            assert name in cols, f"RRCCountyStatus missing column: {name}"

    def test_key_is_primary_key(self):
        cols = self._columns()
        assert cols["key"].primary_key is True

    def test_oil_record_count_is_integer(self):
        cols = self._columns()
        assert "INTEGER" in str(cols["oil_record_count"].type).upper()


class TestGHLConnectionModel:
    """Verify GHLConnection model."""

    def _columns(self):
        return {c.name: c for c in GHLConnection.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        expected = (
            "id", "name", "encrypted_token", "token_last4", "location_id",
            "notes", "validation_status", "created_at", "updated_at",
        )
        for name in expected:
            assert name in cols, f"GHLConnection missing column: {name}"

    def test_id_is_primary_key(self):
        cols = self._columns()
        assert cols["id"].primary_key is True

    def test_validation_status_default(self):
        cols = self._columns()
        assert cols["validation_status"].default.arg == "pending"


class TestRRCSyncJobModel:
    """Verify RRCSyncJob model."""

    def _columns(self):
        return {c.name: c for c in RRCSyncJob.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        expected = ("id", "status", "started_at", "completed_at", "oil_rows", "gas_rows", "error", "steps")
        for name in expected:
            assert name in cols, f"RRCSyncJob missing column: {name}"

    def test_id_is_primary_key(self):
        cols = self._columns()
        assert cols["id"].primary_key is True

    def test_steps_is_jsonb(self):
        cols = self._columns()
        assert "JSONB" in str(cols["steps"].type) or "JSON" in str(cols["steps"].type)


class TestRRCMetadataModel:
    """Verify RRCMetadata model."""

    def _columns(self):
        return {c.name: c for c in RRCMetadata.__table__.columns}

    def test_columns_exist(self):
        cols = self._columns()
        expected = ("key", "oil_rows", "gas_rows", "last_sync_at", "new_records", "updated_records", "updated_at")
        for name in expected:
            assert name in cols, f"RRCMetadata missing column: {name}"

    def test_key_is_primary_key(self):
        cols = self._columns()
        assert cols["key"].primary_key is True
