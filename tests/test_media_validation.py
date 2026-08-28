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


def test_validate_chat_image_returns_original_bytes_untouched() -> None:
    data = _image_bytes("JPEG")

    result, ext = validate_chat_image(io.BytesIO(data))

    assert result == data
    assert ext == ".jpg"


def test_validate_chat_image_maps_extension_by_format() -> None:
    _, ext = validate_chat_image(io.BytesIO(_image_bytes("PNG")))

    assert ext == ".png"


def test_validate_chat_image_rejects_disallowed_format() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="green").save(buffer, format="BMP")

    with pytest.raises(InvalidImageError):
        validate_chat_image(io.BytesIO(buffer.getvalue()))


def test_validate_chat_image_rejects_oversized_file() -> None:
    with pytest.raises(ImageTooLargeError):
        validate_chat_image(io.BytesIO(b"\x00" * (MAX_IMAGE_BYTES + 1)))
