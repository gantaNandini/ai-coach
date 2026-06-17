"""
app/core/storage.py — Object storage abstraction.

Supports local disk (dev) and S3-compatible (MinIO / AWS S3 / R2) for production.
Set STORAGE_BACKEND=local or STORAGE_BACKEND=s3 in .env.

Local disk is NOT suitable for production multi-instance deployments —
uploaded files would not be shared across replicas and would be lost
on container redeploy. Use S3 in production.

Usage:
    from app.core.storage import get_storage
    storage = get_storage()
    key = await storage.upload(file_bytes, filename="report.pdf", content_type="application/pdf")
    url = await storage.get_url(key)
    content = await storage.download(key)
    await storage.delete(key)
"""
from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger("ai_coach.storage")


class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        tenant_id: str | None = None,
    ) -> str:
        """Upload bytes, return storage key."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download by key, return bytes."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete by key."""

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a (possibly pre-signed) URL for the given key."""


class LocalStorage(StorageBackend):
    """
    Local disk storage for development.
    Files are stored under UPLOAD_DIR / <key>.
    NOT suitable for production multi-instance deployments.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal — strip leading slashes/dots
        safe_key = key.lstrip("./")
        return self._base / safe_key

    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        tenant_id: str | None = None,
    ) -> str:
        ext = Path(filename).suffix.lower()
        prefix = f"{tenant_id}/" if tenant_id else ""
        key = f"{prefix}{uuid.uuid4().hex}{ext}"
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.debug("[STORAGE] Local upload: key=%s size=%d", key, len(data))
        return key

    async def download(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
            logger.debug("[STORAGE] Local delete: key=%s", key)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        from app.core.config import settings
        # Local: return a path-based URL (served by the app's /uploads route or directly)
        return f"{settings.APP_BASE_URL}/uploads/{key}"


class S3Storage(StorageBackend):
    """
    S3-compatible storage backend (AWS S3, MinIO, Cloudflare R2).

    Configured via:
        S3_ENDPOINT_URL   — None for AWS, set for MinIO/R2
        S3_ACCESS_KEY_ID
        S3_SECRET_ACCESS_KEY
        S3_BUCKET
        S3_REGION
    """

    def __init__(self) -> None:
        from app.core.config import settings
        import boto3

        kwargs: dict = {
            "region_name": settings.S3_REGION,
            "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
        }
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        self._s3 = boto3.client("s3", **kwargs)
        self._bucket = settings.S3_BUCKET

    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        tenant_id: str | None = None,
    ) -> str:
        import asyncio
        ext = Path(filename).suffix.lower()
        prefix = f"tenants/{tenant_id}/" if tenant_id else "uploads/"
        key = f"{prefix}{uuid.uuid4().hex}{ext}"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            ),
        )
        logger.info("[STORAGE] S3 upload: bucket=%s key=%s size=%d", self._bucket, key, len(data))
        return key

    async def download(self, key: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._s3.get_object(Bucket=self._bucket, Key=key),
        )
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.delete_object(Bucket=self._bucket, Key=key),
        )
        logger.info("[STORAGE] S3 delete: bucket=%s key=%s", self._bucket, key)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL valid for expires_in seconds."""
        import asyncio
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            ),
        )
        return url


# ── Singleton factory ─────────────────────────────────────────────────────────

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the configured storage backend (singleton per process)."""
    global _storage_instance
    if _storage_instance is None:
        from app.core.config import settings
        if settings.STORAGE_BACKEND == "s3":
            _storage_instance = S3Storage()
            logger.info("[STORAGE] Using S3 backend (bucket=%s)", settings.S3_BUCKET)
        else:
            _storage_instance = LocalStorage(settings.UPLOAD_DIR)
            logger.info("[STORAGE] Using local storage at %s", settings.UPLOAD_DIR)
    return _storage_instance
