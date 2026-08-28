import io
from typing import BinaryIO

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION = 1600
JPEG_QUALITY = 82


class InvalidImageError(Exception):
    pass


class ImageTooLargeError(Exception):
    pass


_FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _read_and_verify(file: BinaryIO) -> tuple[bytes, str]:
    """Reads an upload, enforces the size limit, and content-sniffs it via
    Pillow (rather than trusting the client content-type, which is trivially
    spoofable). Returns (raw bytes, Pillow format name)."""
    data = file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(len(data))

    try:
        # verify() exhausts the image object, so re-open separately to read
        # the format afterwards.
        Image.open(io.BytesIO(data)).verify()
        fmt_image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Not a valid image file") from exc

    if fmt_image.format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {fmt_image.format}")

    return data, fmt_image.format


def validate_image(file: BinaryIO) -> bytes:
    """Validates an uploaded image and returns its raw bytes."""
    data, _ = _read_and_verify(file)
    return data


def validate_chat_image(file: BinaryIO) -> tuple[bytes, str]:
    """Like validate_image, but for chat photos: the bytes are returned
    untouched (no downscaling, no re-encoding) so the recipient sees the
    sender's original resolution. Returns (bytes, file extension)."""
    data, fmt = _read_and_verify(file)
    return data, _FORMAT_EXTENSIONS[fmt]


WEBP_QUALITY = 80


def compress_image(data: bytes, format: str = "JPEG") -> bytes:
    image = Image.open(io.BytesIO(data))
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    if format.upper() == "WEBP":
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=WEBP_QUALITY, method=4)
        return output.getvalue()

    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output.getvalue()
