"""Google Cloud Storage service for persistent file storage."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import GCS client
try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    logger.warning("google-cloud-storage not installed, using local storage only")


class StorageService:
    """Service for managing file storage in Google Cloud Storage with local fallback."""

    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        self._initialized = False

    def _init_client(self) -> bool:
        """Initialize the GCS client lazily."""
        if self._initialized:
            return self._client is not None

        self._initialized = True

        if not GCS_AVAILABLE:
            logger.info("GCS not available, using local storage")
            return False

        if not settings.use_gcs:
            logger.info("GCS not configured, using local storage")
            return False

        try:
            self._client = storage.Client(project=settings.gcs_project_id)
            self._bucket = self._client.bucket(settings.gcs_bucket_name)

            # Check if bucket exists, create if not
            if not self._bucket.exists():
                logger.info(f"Creating GCS bucket: {settings.gcs_bucket_name}")
                self._bucket = self._client.create_bucket(
                    settings.gcs_bucket_name,
                    location="us-central1"
                )

            logger.info(f"GCS initialized with bucket: {settings.gcs_bucket_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GCS: {e}")
            self._client = None
            self._bucket = None
            return False

    @property
    def is_gcs_enabled(self) -> bool:
        """Check if GCS is available and enabled."""
        return self._init_client()

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
        Upload a file to storage.

        Args:
            content: File content as bytes or file-like object
            path: Destination path in storage (e.g., "rrc-data/oil_proration.csv")
            content_type: MIME type of the file

        Returns:
            The storage path (GCS path or local path)
        """
        if self.is_gcs_enabled:
            return self._upload_to_gcs(content, path, content_type)
        else:
            return self._upload_to_local(content, path)

    def download_file(self, path: str) -> bytes | None:
        """
        Download a file from storage.

        Args:
            path: Path to the file in storage

        Returns:
            File content as bytes, or None if not found
        """
        if self.is_gcs_enabled:
            return self._download_from_gcs(path)
        else:
            return self._download_from_local(path)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in storage."""
        if self.is_gcs_enabled:
            return self._exists_in_gcs(path)
        else:
            return self._exists_locally(path)

    def get_file_info(self, path: str) -> dict | None:
        """
        Get file metadata.

        Returns:
            Dict with 'size', 'modified', 'content_type' or None if not found
        """
        if self.is_gcs_enabled:
            return self._get_gcs_file_info(path)
        else:
            return self._get_local_file_info(path)

    def delete_file(self, path: str) -> bool:
        """Delete a file from storage."""
        if self.is_gcs_enabled:
            return self._delete_from_gcs(path)
        else:
            return self._delete_from_local(path)

    def list_files(self, prefix: str) -> list[str]:
        """List files with a given prefix."""
        if self.is_gcs_enabled:
            return self._list_gcs_files(prefix)
        else:
            return self._list_local_files(prefix)

    def get_signed_url(self, path: str, expiration_minutes: int = 60) -> str | None:
        """
        Get a signed URL for temporary access to a file.
        Only available with GCS.
        """
        if not self.is_gcs_enabled:
            return None

        try:
            blob = self._bucket.blob(path)
            if not blob.exists():
                return None

            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )
            return url

        except Exception as e:
            logger.error(f"Error generating signed URL for {path}: {e}")
            return None

    # -------------------------------------------------------------------------
    # GCS operations
    # -------------------------------------------------------------------------

    def _upload_to_gcs(
        self,
        content: bytes | BinaryIO,
        path: str,
        content_type: str,
    ) -> str:
        """Upload file to GCS."""
        try:
            blob = self._bucket.blob(path)

            if isinstance(content, bytes):
                blob.upload_from_string(content, content_type=content_type)
            else:
                blob.upload_from_file(content, content_type=content_type)

            logger.info(f"Uploaded to GCS: {path}")
            return f"gs://{settings.gcs_bucket_name}/{path}"

        except Exception as e:
            logger.error(f"GCS upload failed for {path}: {e}")
            raise

    def _download_from_gcs(self, path: str) -> bytes | None:
        """Download file from GCS."""
        try:
            blob = self._bucket.blob(path)
            if not blob.exists():
                logger.warning(f"File not found in GCS: {path}")
                return None

            content = blob.download_as_bytes()
            logger.debug(f"Downloaded from GCS: {path} ({len(content)} bytes)")
            return content

        except NotFound:
            return None
        except Exception as e:
            logger.error(f"GCS download failed for {path}: {e}")
            return None

    def _exists_in_gcs(self, path: str) -> bool:
        """Check if file exists in GCS."""
        try:
            blob = self._bucket.blob(path)
            return blob.exists()
        except Exception as e:
            logger.error(f"GCS exists check failed for {path}: {e}")
            return False

    def _get_gcs_file_info(self, path: str) -> dict | None:
        """Get file info from GCS."""
        try:
            blob = self._bucket.blob(path)
            if not blob.exists():
                return None

            blob.reload()
            return {
                "size": blob.size,
                "modified": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type,
            }
        except Exception as e:
            logger.error(f"GCS file info failed for {path}: {e}")
            return None

    def _delete_from_gcs(self, path: str) -> bool:
        """Delete file from GCS."""
        try:
            blob = self._bucket.blob(path)
            blob.delete()
            logger.info(f"Deleted from GCS: {path}")
            return True
        except NotFound:
            return True  # Already gone
        except Exception as e:
            logger.error(f"GCS delete failed for {path}: {e}")
            return False

    def _list_gcs_files(self, prefix: str) -> list[str]:
        """List files in GCS with prefix."""
        try:
            blobs = self._bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"GCS list failed for prefix {prefix}: {e}")
            return []

    # -------------------------------------------------------------------------
    # Local file operations (fallback)
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
        self.folder = settings.gcs_rrc_data_folder

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
            "storage_type": "gcs" if self.storage.is_gcs_enabled else "local",
        }


class UploadStorage:
    """Helper class for user upload storage."""

    def __init__(self, storage: StorageService):
        self.storage = storage
        self.folder = settings.gcs_uploads_folder

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
        self.folder = settings.gcs_profiles_folder

    def save_profile_image(self, content: bytes, user_id: str, filename: str) -> str:
        """Save a profile image."""
        ext = filename.split(".")[-1] if "." in filename else "jpg"
        path = f"{self.folder}/{user_id}/avatar.{ext}"
        content_type = f"image/{ext}" if ext in ["png", "jpg", "jpeg", "gif"] else "image/jpeg"
        return self.storage.upload_file(content, path, content_type)

    def get_profile_image_url(self, user_id: str) -> str | None:
        """Get signed URL for profile image."""
        # Check common extensions
        for ext in ["jpg", "jpeg", "png", "gif"]:
            path = f"{self.folder}/{user_id}/avatar.{ext}"
            if self.storage.file_exists(path):
                return self.storage.get_signed_url(path, expiration_minutes=60)
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
