import uuid
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings


class MediaStorage(Protocol):
    def upload(self, file: BinaryIO, filename: str) -> str:
        """Stores a file and returns its publicly accessible URL."""
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


@lru_cache
def get_media_storage() -> MediaStorage:
    settings = get_settings()
    public_media_url = f"{settings.public_base_url.rstrip('/')}{settings.media_base_url}"
    return LocalMediaStorage(Path(settings.media_root), public_media_url)
