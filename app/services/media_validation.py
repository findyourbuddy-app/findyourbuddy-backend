import io
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION = 1600
JPEG_QUALITY = 82


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
        # Open fresh buffer for verify(); verify() exhausts the image object
        # so we must re-open separately to check the format afterwards.
        Image.open(io.BytesIO(data)).verify()
        fmt_image = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Not a valid image file") from exc

    if fmt_image.format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {fmt_image.format}")

    return data


def compress_image(data: bytes) -> bytes:
    """Downscales and re-encodes an already-validated image as JPEG so
    uploads served to the app stay small and fast to load, regardless of
    how large the original phone photo was. EXIF metadata is stripped."""
    image = Image.open(io.BytesIO(data))
    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True, exif=b"")
    return output.getvalue()
