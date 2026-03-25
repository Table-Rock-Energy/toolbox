"""Local filesystem storage service."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Local filesystem storage service."""

    # -------------------------------------------------------------------------
    # Core file operations
    # -------------------------------------------------------------------------

    def upload_file(
        self,
        content: bytes | BinaryIO,
        path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a file to local storage.

        Args:
            content: File content as bytes or file-like object
            path: Destination path in storage (e.g., "rrc-data/oil_proration.csv")
            content_type: MIME type of the file

        Returns:
            The local storage path
        """
        return self._upload_to_local(content, path)

    def download_file(self, path: str) -> bytes | None:
        """
        Download a file from local storage.

        Args:
            path: Path to the file in storage

        Returns:
            File content as bytes, or None if not found
        """
        return self._download_from_local(path)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in storage."""
        return self._exists_locally(path)

    def get_file_info(self, path: str) -> dict | None:
        """
        Get file metadata.

        Returns:
            Dict with 'size', 'modified', 'content_type' or None if not found
        """
        return self._get_local_file_info(path)

    def delete_file(self, path: str) -> bool:
        """Delete a file from storage."""
        return self._delete_from_local(path)

    def list_files(self, prefix: str) -> list[str]:
        """List files with a given prefix."""
        return self._list_local_files(prefix)

    # -------------------------------------------------------------------------
    # Local file operations
    # -------------------------------------------------------------------------

    def _get_local_path(self, path: str) -> Path:
        """Convert storage path to local filesystem path."""
        return settings.data_dir / path

    def _upload_to_local(self, content: bytes | BinaryIO, path: str) -> str:
        """Upload file to local filesystem."""
        local_path = self._get_local_path(path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            local_path.write_bytes(content)
        else:
            local_path.write_bytes(content.read())

        logger.info(f"Saved locally: {local_path}")
        return str(local_path)

    def _download_from_local(self, path: str) -> bytes | None:
        """Download file from local filesystem."""
        local_path = self._get_local_path(path)
        if not local_path.exists():
            return None

        return local_path.read_bytes()

    def _exists_locally(self, path: str) -> bool:
        """Check if file exists locally."""
        return self._get_local_path(path).exists()

    def _get_local_file_info(self, path: str) -> dict | None:
        """Get file info from local filesystem."""
        local_path = self._get_local_path(path)
        if not local_path.exists():
            return None

        stat = local_path.stat()
        return {
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "content_type": "application/octet-stream",
        }

    def _delete_from_local(self, path: str) -> bool:
        """Delete file from local filesystem."""
        local_path = self._get_local_path(path)
        try:
            if local_path.exists():
                local_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Local delete failed for {path}: {e}")
            return False

    def _list_local_files(self, prefix: str) -> list[str]:
        """List files locally with prefix."""
        base_path = self._get_local_path(prefix)
        if not base_path.exists():
            return []

        if base_path.is_file():
            return [prefix]

        return [
            str(p.relative_to(settings.data_dir))
            for p in base_path.rglob("*")
            if p.is_file()
        ]


# -------------------------------------------------------------------------
# Helper functions for specific use cases
# -------------------------------------------------------------------------

class RRCDataStorage:
    """Helper class for RRC proration data storage."""

    def __init__(self, storage: StorageService):
        self.storage = storage
        self.folder = settings.storage_rrc_data_folder

    @property
    def oil_path(self) -> str:
        return f"{self.folder}/oil_proration.csv"

    @property
    def gas_path(self) -> str:
        return f"{self.folder}/gas_proration.csv"

    def save_oil_data(self, content: bytes) -> str:
        return self.storage.upload_file(content, self.oil_path, "text/csv")

    def save_gas_data(self, content: bytes) -> str:
        return self.storage.upload_file(content, self.gas_path, "text/csv")

    def get_oil_data(self) -> bytes | None:
        return self.storage.download_file(self.oil_path)

    def get_gas_data(self) -> bytes | None:
        return self.storage.download_file(self.gas_path)

    def get_status(self) -> dict:
        """Get status of RRC data files."""
        oil_info = self.storage.get_file_info(self.oil_path)
        gas_info = self.storage.get_file_info(self.gas_path)

        return {
            "oil_available": oil_info is not None,
            "gas_available": gas_info is not None,
            "oil_size": oil_info["size"] if oil_info else 0,
            "gas_size": gas_info["size"] if gas_info else 0,
            "oil_modified": oil_info["modified"] if oil_info else None,
            "gas_modified": gas_info["modified"] if gas_info else None,
            "storage_type": "local",
        }


class UploadStorage:
    """Helper class for user upload storage."""

    def __init__(self, storage: StorageService):
        self.storage = storage
        self.folder = settings.storage_uploads_folder

    def save_upload(
        self,
        content: bytes | BinaryIO,
        filename: str,
        tool: str,
        user_id: str | None = None,
    ) -> str:
        """Save an uploaded file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = filename.replace(" ", "_")

        if user_id:
            path = f"{self.folder}/{tool}/{user_id}/{timestamp}_{safe_filename}"
        else:
            path = f"{self.folder}/{tool}/{timestamp}_{safe_filename}"

        content_type = self._get_content_type(filename)
        return self.storage.upload_file(content, path, content_type)

    def _get_content_type(self, filename: str) -> str:
        """Determine content type from filename."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        types = {
            "pdf": "application/pdf",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        return types.get(ext, "application/octet-stream")


class ProfileStorage:
    """Helper class for user profile image storage."""

    def __init__(self, storage: StorageService):
        self.storage = storage
        self.folder = settings.storage_profiles_folder

    def save_profile_image(self, content: bytes, user_id: str, filename: str) -> str:
        """Save a profile image."""
        ext = filename.split(".")[-1] if "." in filename else "jpg"
        path = f"{self.folder}/{user_id}/avatar.{ext}"
        content_type = f"image/{ext}" if ext in ["png", "jpg", "jpeg", "gif"] else "image/jpeg"
        return self.storage.upload_file(content, path, content_type)

    def get_profile_image_url(self, user_id: str) -> str | None:
        """Get URL for profile image. Always returns the API proxy endpoint."""
        for ext in ["jpg", "jpeg", "png", "gif"]:
            path = f"{self.folder}/{user_id}/avatar.{ext}"
            if self.storage.file_exists(path):
                return f"/api/admin/profile-image/{user_id}"
        return None

    def get_profile_image_path(self, user_id: str) -> Path | None:
        """Get the local filesystem path for a user's profile image."""
        for ext in ["jpg", "jpeg", "png", "gif"]:
            path = f"{self.folder}/{user_id}/avatar.{ext}"
            local_path = self.storage._get_local_path(path)
            if local_path.exists():
                return local_path
        return None

    def delete_profile_image(self, user_id: str) -> bool:
        """Delete profile image."""
        for ext in ["jpg", "jpeg", "png", "gif"]:
            path = f"{self.folder}/{user_id}/avatar.{ext}"
            self.storage.delete_file(path)
        return True


# Global instances
storage_service = StorageService()
rrc_storage = RRCDataStorage(storage_service)
upload_storage = UploadStorage(storage_service)
profile_storage = ProfileStorage(storage_service)
