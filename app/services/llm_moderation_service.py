import json
import logging
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.event import Event

logger = logging.getLogger(__name__)


def check_user_event_collisions(db: Session, creator_id: int, starts_at: datetime, location_name: str, current_event_id: int | None = None) -> str | None:
    """Checks if the user has another duplicate event starting at the exact same time, location and title."""
    if not creator_id or not starts_at or not location_name:
        return None
    try:
        window_start = starts_at - timedelta(minutes=15)
        window_end = starts_at + timedelta(minutes=15)

        query = db.query(Event).filter(
            Event.creator_id == creator_id,
            Event.location_name == location_name,
            Event.starts_at >= window_start,
            Event.starts_at <= window_end,
        )
        if current_event_id:
            query = query.filter(Event.id != current_event_id)

        existing_conflict = query.first()

        if existing_conflict is not None and existing_conflict.title == location_name:
            return f"Aynı mekan ({location_name}) ve aynı zaman diliminde zaten başka bir etkinliğiniz bulunmaktadır."
    except Exception as e:
        logger.warning(f"Collision check bypassed: {e}")
    return None


def evaluate_event_with_llm(event: Event) -> tuple[bool, str | None]:
    """Uses Novita AI to evaluate user-created event content for troll, spam, or inappropriate text."""
    settings = get_settings()
    if not settings.novita_api_key:
        # If Novita key is not set, default auto-approve clean text
        return True, None

    prompt = (
        "Etkinlik Moderasyonu: Aşağıdaki sosyal etkinlik teklifini değerlendir.\n"
        "Kurallar:\n"
        "1. Küfür, nefret söylemi, yasadışı veya cinsel içerik barındıran metinleri REDDET.\n"
        "2. Anlamsız harf yığınları, troll amaçlı veya sahte etkinlikleri REDDET.\n"
        "3. Düzgün, topluluğa uygun sosyal buluşma tekliflerini ONAYLA.\n\n"
        f"Başlık: {event.title}\n"
        f"Açıklama: {event.description or 'Açıklama yok'}\n"
        f"Kategori: {event.category}\n"
        f"Mekan: {event.location_name}\n\n"
        "SADECE ham JSON dön:\n"
        '{"approved": true, "reason": null}\n'
        "veya\n"
        '{"approved": false, "reason": "Red sebebi..."}'
    )

    url = f"{settings.novita_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.novita_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.novita_model,
        "messages": [
            {"role": "system", "content": "Sen bir içerik moderatörüsün. Yalnızca geçerli JSON çıktısı üretirsin."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=8.0)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            approved = bool(parsed.get("approved", True))
            reason = parsed.get("reason")
            return approved, reason
        else:
            logger.warning(f"Novita Moderation API error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to moderate event with LLM: {e}")

    return True, None


from app.models.user import User


def send_event_approval_email(creator: User, event: Event) -> None:
    """Sends an email notification via SMTP when a user's created event is approved."""
    settings = get_settings()
    if not settings.smtp_username or not creator or not creator.email:
        logger.info(f"SMTP not configured. Event approval email logged for user {creator.email if creator else 'unknown'}")
        return

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎉 Etkinliğiniz Yayınlandı: {event.title}"
        msg["From"] = settings.smtp_sender
        msg["To"] = creator.email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #6C5CE7;">Tebrikler {creator.display_name}! 🚀</h2>
            <p>Oluşturduğunuz <b>"{event.title}"</b> başlıklı etkinlik Yapay Zeka Moderasyon kontrolünden geçerek onaylandı.</p>
            <p>Etkinliğiniz artık <b>FindYourBuddy</b> haritasında ve keşfet ekranında yayınlanıyor!</p>
            <br>
            <p>Mekan: {event.location_name}<br>Tarih: {event.starts_at.strftime('%Y-%m-%d %H:%M')}</p>
            <br>
            <p>Harika kanka buluşmaları dileriz,<br><b>FindYourBuddy Ekibi</b></p>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(msg)
        logger.info(f"Event approval email sent to {creator.email}")
    except Exception as e:
        logger.error(f"Failed to send event approval email: {e}")


def send_event_rejection_email(creator: User, event: Event, reason: str | None) -> None:
    """Sends an email notification via SMTP when a user's created event is rejected by moderation."""
    settings = get_settings()
    if not settings.smtp_username or not creator or not creator.email:
        logger.info(f"SMTP not configured. Event rejection email logged for user {creator.email if creator else 'unknown'}")
        return

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⚠️ Etkinlik Talebiniz Hakkında: {event.title}"
        msg["From"] = settings.smtp_sender
        msg["To"] = creator.email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Merhaba {creator.display_name},</h2>
            <p>Oluşturduğunuz <b>"{event.title}"</b> başlıklı etkinlik talebiniz Yapay Zeka Moderasyon değerlendirmesi sonucunda yayınlanamamıştır.</p>
            <div style="background-color: #FFF3F3; padding: 12px; border-left: 4px solid #FF6B6B; margin: 16px 0;">
                <b>Red Sebebi:</b> {reason or 'İçerik topluluk kurallarına uygun bulunamadı.'}
            </div>
            <p>Lütfen bilgileri düzenleyip tekrar deneyiniz.</p>
            <br>
            <p><b>FindYourBuddy Ekibi</b></p>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(msg)
        logger.info(f"Event rejection email sent to {creator.email}")
    except Exception as e:
        logger.error(f"Failed to send event rejection email: {e}")


def moderate_new_event(db: Session, event: Event) -> Event:
    """Runs collision checks and LLM moderation on a newly created event."""
    if event.creator_id is None:
        # Scraped or admin events are pre-approved
        event.is_approved = True
        return event

    creator = db.get(User, event.creator_id)

    collision_reason = check_user_event_collisions(db, event.creator_id, event.starts_at, event.location_name, current_event_id=event.id)
    if collision_reason:
        event.is_approved = False
        event.approval_rejection_reason = collision_reason
        db.commit()
        db.refresh(event)
        if creator:
            send_event_rejection_email(creator, event, collision_reason)
        return event

    approved, rejection_reason = evaluate_event_with_llm(event)
    event.is_approved = approved
    event.approval_rejection_reason = rejection_reason
    db.commit()
    db.refresh(event)
    if creator:
        if approved:
            send_event_approval_email(creator, event)
        else:
            send_event_rejection_email(creator, event, rejection_reason)
    return event
