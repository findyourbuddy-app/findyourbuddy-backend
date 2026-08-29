import io

import pytest
from PIL import Image

from app.services.media_validation import (
    MAX_IMAGE_BYTES,
    ImageTooLargeError,
    InvalidImageError,
    validate_chat_image,
    validate_image,
)


def _image_bytes(fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="blue").save(buffer, format=fmt)
    return buffer.getvalue()


def test_validate_image_accepts_valid_png() -> None:
    data = _image_bytes("PNG")

    result = validate_image(io.BytesIO(data))

    assert result == data


def test_validate_image_accepts_valid_jpeg() -> None:
    data = _image_bytes("JPEG")

    result = validate_image(io.BytesIO(data))

    assert result == data


def test_validate_image_rejects_non_image_bytes() -> None:
    with pytest.raises(InvalidImageError):
        validate_image(io.BytesIO(b"this is definitely not an image"))


def test_validate_image_rejects_disallowed_format() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="green").save(buffer, format="BMP")

    with pytest.raises(InvalidImageError):
        validate_image(io.BytesIO(buffer.getvalue()))


def test_validate_image_rejects_oversized_file() -> None:
    oversized = b"\x00" * (MAX_IMAGE_BYTES + 1)

    with pytest.raises(ImageTooLargeError):
        validate_image(io.BytesIO(oversized))


def test_validate_chat_image_reencodes_jpeg_keeping_dimensions() -> None:
    data = _image_bytes("JPEG")

    result, ext = validate_chat_image(io.BytesIO(data))

    # Chat photos are always normalized to optimized JPEG (size win), so the
    # bytes change even for a JPEG input -- only the pixel dimensions are kept.
    assert ext == ".jpg"
    out = Image.open(io.BytesIO(result))
    assert out.format == "JPEG"
    assert out.size == (2, 2)


def test_validate_chat_image_transcodes_png_to_jpeg() -> None:
    result, ext = validate_chat_image(io.BytesIO(_image_bytes("PNG")))

    assert ext == ".jpg"
    assert Image.open(io.BytesIO(result)).format == "JPEG"


def test_validate_chat_image_rejects_disallowed_format() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="green").save(buffer, format="BMP")

    with pytest.raises(InvalidImageError):
        validate_chat_image(io.BytesIO(buffer.getvalue()))


def test_validate_chat_image_rejects_oversized_file() -> None:
    with pytest.raises(ImageTooLargeError):
        validate_chat_image(io.BytesIO(b"\x00" * (MAX_IMAGE_BYTES + 1)))


def _heic_bytes(width: int = 120, height: int = 80) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color="red").save(buffer, format="HEIF")
    return buffer.getvalue()


def test_validate_image_accepts_heic() -> None:
    # iOS shares photos as HEIC; the profile-photo path re-encodes afterwards.
    assert validate_image(io.BytesIO(_heic_bytes())) == _heic_bytes()


def test_validate_chat_image_transcodes_heic_to_jpeg_keeping_size() -> None:
    data, ext = validate_chat_image(io.BytesIO(_heic_bytes(320, 200)))

    assert ext == ".jpg"
    transcoded = Image.open(io.BytesIO(data))
    assert transcoded.format == "JPEG"
    assert transcoded.size == (320, 200)
