import base64
import json
import logging
import os
import re
import httpx
from sqlalchemy.orm import Session

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from app.config import get_settings
from app.models.user import User
from app.models.user_photo import UserPhoto

logger = logging.getLogger(__name__)


def _resolve_image_to_data_uri_or_url(photo_url: str, public_base: str, media_root: str = "media") -> str:
    """Converts local file paths or LAN/localhost URLs to base64 data URIs so cloud Vision LLMs
    (like Novita AI) can access image binaries directly in local development environments."""
    if not photo_url:
        return ""

    clean_path = photo_url
    if public_base and clean_path.startswith(public_base):
        clean_path = clean_path[len(public_base):]

    # Strip scheme and host if present
    clean_path = re.sub(r"^https?://[^/]+", "", clean_path).lstrip("/")

    if clean_path.startswith("media/"):
        clean_path = clean_path[len("media/"):]

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_paths = [
        os.path.join(base_dir, media_root, clean_path),
        os.path.join(os.getcwd(), media_root, clean_path),
        os.path.join(media_root, clean_path),
    ]

    for disk_path in candidate_paths:
        if os.path.isfile(disk_path):
            try:
                with open(disk_path, "rb") as img_f:
                    encoded = base64.b64encode(img_f.read()).decode("utf-8")
                    ext = disk_path.lower().split(".")[-1]
                    mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
                    return f"data:{mime};base64,{encoded}"
            except Exception as err:
                logger.warning(f"Failed to convert local file {disk_path} to base64: {err}")

    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    base = public_base.rstrip("/")
    return f"{base}/{clean_path}"


def verify_user_photo_with_vision(db: Session, user: User, selfie_photo_url: str) -> dict:
    """Uses Novita AI Vision LLM via OpenAI client to compare an instant
    selfie against the user's uploaded profile and gallery photos."""
    settings = get_settings()

    profile_photos = []
    if user.photo_url:
        profile_photos.append(user.photo_url)

    gallery_items = db.query(UserPhoto).filter(UserPhoto.user_id == user.id).all()
    for item in gallery_items:
        if item.photo_url and item.photo_url not in profile_photos:
            profile_photos.append(item.photo_url)

    if not profile_photos:
        # No existing profile photo to compare the selfie against -- there is
        # nothing to verify. This must never auto-approve regardless of what
        # selfie_photo_url is: doing so would let anyone skip the actual
        # face-match check entirely by simply never uploading a profile photo.
        return {
            "verified": False,
            "message": "Profilinizde karşılaştırılacak profil fotoğrafı bulunamadı. Önce bir profil fotoğrafı yükleyin.",
        }

    if not settings.novita_api_key:
        if settings.environment != "production":
            user.is_verified = True
            user.verification_status = "verified"
            db.commit()
            db.refresh(user)
            try:
                from app.core.notifications import get_notification_sender
                from app.services.notification_service import notify_photo_verification_result
                notify_photo_verification_result(db, get_notification_sender(), user.id, verified=True)
            except Exception:
                pass
            return {
                "verified": True,
                "message": "[DEV/TEST] Profil fotoğrafınız başarıyla doğrulandı! Mavi Tik 🔵 rozetiniz tanımlandı.",
            }
        return {
            "verified": False,
            "message": "Doğrulama servisi şu anda kullanılamıyor.",
        }

    selfie_payload = _resolve_image_to_data_uri_or_url(
        selfie_photo_url, settings.public_base_url, settings.media_root
    )
    profile_payloads = [
        _resolve_image_to_data_uri_or_url(url, settings.public_base_url, settings.media_root)
        for url in profile_photos
    ]

    prompt_text = (
        "Yüz Karşılaştırma ve Doğrulama Analizi:\n"
        "Sana kullanıcının anlık çektiği doğrulama selfie'si ile sistemde önceden yüklü olan profil fotoğrafı/fotoğraflarını veriyorum.\n"
        "Görevin: Canlı selfie'deki kişinin, profil fotoğraflarındaki kişiyle AYNI KİŞİ olup olmadığını analiz etmek.\n\n"
        "Yanıtı SADECE aşağıdaki geçerli JSON formatında dön:\n"
        '{"is_same_person": true, "confidence": 0.95, "reason": "Göz ve burun yapısı, çene hatları uyuşmaktadır."}'
    )

    content_items = [
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": selfie_payload, "detail": "high"}},
    ]
    for p_payload in profile_payloads:
        content_items.append({"type": "image_url", "image_url": {"url": p_payload, "detail": "high"}})

    model_name = settings.novita_vision_model or "qwen/qwen3.6-27b"
    base_url = settings.novita_base_url.rstrip("/")

    raw_content = None

    if OpenAI is not None:
        try:
            client = OpenAI(
                api_key=settings.novita_api_key,
                base_url=base_url,
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an AI face verification assistant. Respond only in valid JSON format."},
                    {"role": "user", "content": content_items},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            raw_content = response.choices[0].message.content
        except Exception as sdk_err:
            logger.warning(f"OpenAI SDK call to Novita AI failed: {sdk_err}")

    if raw_content is None:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.novita_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are an AI face verification assistant. Respond only in valid JSON format."},
                {"role": "user", "content": content_items},
            ],
            "temperature": 0.2,
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=20.0)
            if response.status_code == 200:
                raw_content = response.json()["choices"][0]["message"]["content"]
            else:
                logger.warning(f"Novita Vision API error {response.status_code}: {response.text}")
        except Exception as http_err:
            logger.error(f"HTTP Vision photo verification failed: {http_err}")

    if raw_content:
        try:
            cleaned = re.sub(r"```json\s*", "", raw_content)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            parsed = json.loads(cleaned)

            is_same = bool(parsed.get("is_same_person", True))
            reason = parsed.get("reason", "Fotoğraftaki kişi profil fotoğrafınızla uyuşmaktadır.")
            if is_same:
                user.is_verified = True
                user.verification_status = "verified"
                db.commit()
                db.refresh(user)
                try:
                    from app.core.notifications import get_notification_sender
                    from app.services.notification_service import notify_photo_verification_result
                    notify_photo_verification_result(db, get_notification_sender(), user.id, verified=True)
                except Exception:
                    pass
                return {
                    "verified": True,
                    "message": "Profil fotoğrafınız AI Vision tarafından başarıyla doğrulandı! Mavi Tik 🔵 rozetiniz hesabınıza eklendi.",
                }
            else:
                user.is_verified = False
                user.verification_status = "rejected"
                db.commit()
                db.refresh(user)
                try:
                    from app.core.notifications import get_notification_sender
                    from app.services.notification_service import notify_photo_verification_result
                    notify_photo_verification_result(db, get_notification_sender(), user.id, verified=False, reason=reason)
                except Exception:
                    pass
                return {
                    "verified": False,
                    "message": f"Fotoğraf doğrulaması başarısız: {reason}",
                }
        except Exception as parse_err:
            logger.error(f"Failed to parse LLM vision response: {parse_err}, raw content: {raw_content}")

    # The API key IS configured but the call itself failed or returned
    # something unparseable -- this must never silently auto-verify, in any
    # environment. Doing so in dev/test would mask a real bug (a broken
    # prompt, an expired key, a bad response format) behind a fake "success".
    # Only the no-key-configured-at-all branch above is allowed to mock-approve.
    user.verification_status = "pending"
    db.commit()
    return {
        "verified": False,
        "message": "Doğrulama servisi şu anda yanıt vermiyor. Lütfen daha sonra tekrar deneyin.",
    }

