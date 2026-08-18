import mimetypes
import uuid
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings


class MediaStorage(Protocol):
    def upload(self, file: BinaryIO, filename: str) -> str:
        """Stores a file and returns its publicly accessible URL."""
        ...

    def delete(self, url_or_path: str | None) -> None:
        """Deletes a file from media storage if it exists."""
        ...


class LocalMediaStorage:
    def __init__(self, base_dir: Path, base_url: str) -> None:
        self._base_dir = base_dir
        self._base_url = base_url.rstrip("/")
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, file: BinaryIO, filename: str) -> str:
        stored_name = f"{uuid.uuid4().hex}{Path(filename).suffix}"
        with (self._base_dir / stored_name).open("wb") as destination:
            destination.write(file.read())
        return f"{self._base_url}/{stored_name}"

    def delete(self, url_or_path: str | None) -> None:
        if not url_or_path:
            return
        filename = Path(url_or_path).name
        file_path = self._base_dir / filename
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass


class S3MediaStorage:
    """Works for both real AWS S3 and any S3-compatible provider (e.g.
    Cloudflare R2) by pointing endpoint_url at the provider's endpoint."""

    def __init__(
        self,
        bucket_name: str,
        region: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        public_url_base: str,
    ) -> None:
        import boto3

        self._bucket_name = bucket_name
        self._public_url_base = public_url_base.rstrip("/")
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def upload(self, file: BinaryIO, filename: str) -> str:
        stored_name = f"{uuid.uuid4().hex}{Path(filename).suffix}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self._client.upload_fileobj(
            file,
            self._bucket_name,
            stored_name,
            ExtraArgs={"ContentType": content_type},
        )
        return f"{self._public_url_base}/{stored_name}"

    def delete(self, url_or_path: str | None) -> None:
        if not url_or_path:
            return
        key = Path(url_or_path).name
        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=key)
        except Exception:
            pass


@lru_cache
def get_media_storage() -> MediaStorage:
    settings = get_settings()
    if settings.media_storage_backend == "s3":
        return S3MediaStorage(
            bucket_name=settings.s3_bucket_name,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            public_url_base=settings.s3_public_url_base,
        )
    public_media_url = f"{settings.public_base_url.rstrip('/')}{settings.media_base_url}"
    return LocalMediaStorage(Path(settings.media_root), public_media_url)
