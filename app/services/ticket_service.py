import io

import cv2
import numpy as np
from PIL import Image


def decode_qr_or_barcode(image_bytes: bytes) -> str | None:
    """Best-effort QR/barcode decode from an uploaded ticket image. Returns
    the decoded text if a code was found and readable, otherwise None.

    This only confirms *a* scannable code is present in the photo -- it does
    not verify the ticket is genuine or unused, since that requires the
    ticket vendor's own validation API, which this app doesn't have access to.
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    detector = cv2.QRCodeDetector()
    text, _, _ = detector.detectAndDecode(frame)
    if text:
        return text

    barcode_detector = cv2.barcode.BarcodeDetector()
    decoded_info, _, _ = barcode_detector.detectAndDecode(frame)
    if decoded_info:
        for value in decoded_info:
            if value:
                return value

    return None
