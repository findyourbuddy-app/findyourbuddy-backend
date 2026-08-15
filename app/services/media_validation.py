import io
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImageError(Exception):
    pass


class ImageTooLargeError(Exception):
    pass


def validate_image(file: BinaryIO) -> bytes:
    """Reads and validates an uploaded file is really an image of an allowed
    format and within the size limit. Returns the raw bytes on success so the
    caller doesn't need to re-read the stream. Content-sniffs via Pillow
    rather than trusting the client-supplied content-type header, which is
    trivially spoofable."""
    data = file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(len(data))

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Not a valid image file") from exc

    if image.format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {image.format}")

    return data
