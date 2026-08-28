import io
from typing import BinaryIO

import pillow_heif
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True
# iOS shares photos as HEIC by default; without this Pillow can't open them.
pillow_heif.register_heif_opener()

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB
# Formats a browser / React Native <Image> can render, so they are stored as-is.
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Formats we accept on upload; anything here that isn't web-renderable is
# transcoded to JPEG before storage.
DECODABLE_FORMATS = ALLOWED_FORMATS | {"HEIF", "HEIC"}
MAX_DIMENSION = 1600
JPEG_QUALITY = 82
# Chat photos keep their original resolution; only used when a HEIC upload has
# to be transcoded to JPEG.
CHAT_JPEG_QUALITY = 95


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

    if fmt_image.format not in DECODABLE_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {fmt_image.format}")

    return data, fmt_image.format


def validate_image(file: BinaryIO) -> bytes:
    """Validates an uploaded image and returns its raw bytes. HEIC is allowed
    through here because the profile-photo path re-encodes to JPEG afterwards."""
    data, _ = _read_and_verify(file)
    return data


def validate_chat_image(file: BinaryIO) -> tuple[bytes, str]:
    """For chat photos: web-renderable formats (JPEG/PNG/WEBP) are returned
    untouched so the recipient sees the sender's original resolution. HEIC is
    transcoded to a full-resolution JPEG (no downscaling). Returns
    (bytes, file extension)."""
    data, fmt = _read_and_verify(file)
    if fmt in ALLOWED_FORMATS:
        return data, _FORMAT_EXTENSIONS[fmt]

    try:
        image = Image.open(io.BytesIO(data))
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=CHAT_JPEG_QUALITY)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Not a valid image file") from exc
    return output.getvalue(), ".jpg"


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
