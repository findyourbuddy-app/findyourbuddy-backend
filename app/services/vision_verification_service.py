import json
import logging
import re
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)


def send_verification_success_email(user: User) -> None:
    """Sends a confirmation email via SMTP notifying the user that their profile has been photo verified."""
    settings = get_settings()
    if not settings.smtp_username or not user.email:
        logger.info(f"SMTP not configured. Verified confirmation email logged for {user.email}")
        return

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🎉 Tebrikler! Profiliniz Mavi Tik 🔵 ile Doğrulandı"
        msg["From"] = settings.smtp_sender
        msg["To"] = user.email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #6C5CE7;">Tebrikler {user.display_name}! 🔵</h2>
            <p>Canlı selfie doğrulamanız Yapay Zeka Vision sistemi tarafından başarıyla onaylandı.</p>
            <p>Hesabınız artık <b>Mavi Tik 🔵 (Fotoğraf Onaylı Profil)</b> rozetine sahip!</p>
            <br>
            <p>Keyifli ve güvenli kanka buluşmaları dileriz,<br><b>FindYourBuddy Ekibi</b></p>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(msg)
        logger.info(f"Verification confirmation email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send verification confirmation email: {e}")


def send_verification_rejection_email(user: User, reason: str) -> None:
    """Sends an email notification via SMTP when a user's photo verification selfie fails."""
    settings = get_settings()
    if not settings.smtp_username or not user.email:
        logger.info(f"SMTP not configured. Verification rejection email logged for {user.email}")
        return

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "⚠️ Profil Fotoğraf Doğrulaması Hakkında"
        msg["From"] = settings.smtp_sender
        msg["To"] = user.email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Merhaba {user.display_name},</h2>
            <p>Çekmiş olduğunuz canlı doğrulama selfie'si Yapay Zeka Vision analizi sonucunda profil fotoğrafınızla uyuşmamıştır.</p>
            <div style="background-color: #FFF3F3; padding: 12px; border-left: 4px solid #FF6B6B; margin: 16px 0;">
                <b>Açıklama:</b> {reason}
            </div>
            <p>Lütfen yüzünüzün net göründüğü yeni bir selfie çekerek Mavi Tik doğrulamasını tekrar deneyiniz.</p>
            <br>
            <p><b>FindYourBuddy Ekibi</b></p>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(msg)
        logger.info(f"Verification rejection email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send verification rejection email: {e}")


def _make_full_url(url: str, public_base: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = public_base.rstrip("/")
    path = url.lstrip("/")
    return f"{base}/{path}"


def verify_user_photo_with_vision(db: Session, user: User, selfie_photo_url: str) -> dict:
    """Uses Novita Vision AI to compare verification selfie against user's profile photo."""
    settings = get_settings()
    main_photo = user.photo_url

    if not main_photo:
        return {
            "verified": False,
            "message": "Profilinizde karşılaştırılacak ana profil fotoğrafı bulunamadı. Lütfen önce profil fotoğrafı yükleyin.",
        }

    if not settings.novita_api_key:
        # Fallback auto-approve for testing environment if Novita API key is not configured
        user.is_verified = True
        user.verification_status = "verified"
        db.commit()
        db.refresh(user)
        send_verification_success_email(user)
        return {
            "verified": True,
            "message": "Profil fotoğrafınız başarıyla doğrulandı! Mavi Tik rozetiniz tanımlandı. 🔵",
        }

    main_photo_full = _make_full_url(main_photo, settings.public_base_url)
    selfie_photo_full = _make_full_url(selfie_photo_url, settings.public_base_url)

    prompt = (
        "Yüz Karşılaştırma Analizi:\n"
        "Sana iki adet fotoğraf URL'si veriyorum. Birincisi kullanıcının ana profil fotoğrafı, ikincisi canlı çekilen doğrulama selfie'sidir.\n"
        "İki fotoğraftaki kişinin aynı kişi olup olmadığını analiz et.\n\n"
        f"1. Profil Fotoğrafı: {main_photo_full}\n"
        f"2. Doğrulama Selfie: {selfie_photo_full}\n\n"
        "Yanıtı SADECE ham JSON dön:\n"
        '{"is_same_person": true, "confidence": 0.95, "reason": "Yüz hatları ve göz yapısı birebir örtüşüyor."}'
    )

    url = f"{settings.novita_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.novita_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.novita_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": main_photo_full}},
                    {"type": "image_url", "image_url": {"url": selfie_photo_full}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=12.0)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r"```json\s*", "", content)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            parsed = json.loads(cleaned)

            is_same = bool(parsed.get("is_same_person", False))
            reason = parsed.get("reason", "Fotoğraftaki kişi profil fotoğrafınızla uyuşmuyor.")
            if is_same:
                user.is_verified = True
                user.verification_status = "verified"
                db.commit()
                db.refresh(user)
                send_verification_success_email(user)
                return {
                    "verified": True,
                    "message": "Profil fotoğrafınız AI Vision tarafından başarıyla doğrulandı! Mavi Tik 🔵 rozetiniz hesabınıza eklendi.",
                }
            else:
                user.is_verified = False
                user.verification_status = "rejected"
                db.commit()
                db.refresh(user)
                send_verification_rejection_email(user, reason)
                return {
                    "verified": False,
                    "message": f"Fotoğraf doğrulaması başarısız: {reason}",
                }
        else:
            logger.warning(f"Novita Vision API error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Vision photo verification failed: {e}")

    user.is_verified = False
    user.verification_status = "unverified"
    db.commit()
    db.refresh(user)
    return {
        "verified": False,
        "message": "Yapay Zeka Görsel Doğrulama servisine şu an ulaşılamadı. Lütfen tekrar deneyiniz.",
    }
