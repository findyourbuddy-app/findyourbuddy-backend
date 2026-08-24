import io
from typing import BinaryIO

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True

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
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Not a valid image file") from exc

    if fmt_image.format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {fmt_image.format}")

    return data


def compress_image(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output.getvalue()
