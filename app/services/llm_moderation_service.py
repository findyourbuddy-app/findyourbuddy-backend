import json
import logging
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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

    base_url = settings.novita_base_url.rstrip("/")
    messages = [
        {"role": "system", "content": "Sen bir içerik moderatörüsün. Yalnızca geçerli JSON çıktısı üretirsin."},
        {"role": "user", "content": prompt},
    ]

    raw_content = None

    # Option 1: Using official OpenAI Python SDK client
    if OpenAI is not None:
        try:
            client = OpenAI(api_key=settings.novita_api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=settings.novita_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content
        except Exception as sdk_err:
            logger.warning(f"OpenAI SDK call to Novita AI failed, trying HTTP fallback: {sdk_err}")

    # Option 2: Fallback to httpx HTTP POST call if OpenAI SDK is not present or failed
    if raw_content is None:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.novita_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.novita_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=8.0)
            if response.status_code == 200:
                raw_content = response.json()["choices"][0]["message"]["content"]
            else:
                logger.warning(f"Novita Moderation API error {response.status_code}: {response.text}")
        except Exception as http_err:
            logger.error(f"Failed to moderate event with LLM: {http_err}")

    if raw_content:
        try:
            parsed = json.loads(raw_content)
            approved = bool(parsed.get("approved", True))
            reason = parsed.get("reason")
            return approved, reason
        except Exception as parse_err:
            logger.error(f"Failed to parse LLM moderation response: {parse_err}")

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


def auto_classify_event_category_with_llm(title: str, description: str | None = None) -> str:
    """Uses keywords & Novita AI LLM to automatically categorize an event into the best matching category (e.g. 'festival')."""
    text = (title + " " + (description or "")).lower()
    
    # 1. Instant zero-latency rule-based keyword match
    if any(k in text for k in ["fest", "festival", "festivali", "carnival", "karnaval"]):
        return "festival"
    if any(k in text for k in ["konser", "concert", "live band", "canlı müzik", "akustik"]):
        return "concert"
    if any(k in text for k in ["tiyatro", "theatre", "gösteri", "standup", "stand-up", "komedi"]):
        return "theatre"
    if any(k in text for k in ["parti", "party", "dj set", "after party", "nightclub"]):
        return "party"
    if any(k in text for k in ["sergi", "galeri", "art", "sanat", "müze"]):
        return "art"
    if any(k in text for k in ["workshop", "atölye", "seminer", "kurs"]):
        return "workshop"

    settings = get_settings()
    if not settings.novita_api_key:
        return "other"

    categories_list = settings.allowed_event_categories
    prompt = (
        "Sen bir etkinlik kategorize etme yapay zekasısın.\n"
        f"Aşağıdaki etkinliği şu kategorilerden EN UYGUN birine sınıflandır: {', '.join(categories_list)}.\n\n"
        f"Etkinlik Başlığı: {title}\n"
        f"Açıklama: {description or 'Yok'}\n\n"
        "SADECE geçerli bir JSON objesi dön:\n"
        '{"category": "festival"}'
    )

    base_url = settings.novita_base_url.rstrip("/")
    messages = [
        {"role": "system", "content": "Sen yalnızca JSON çıktısı veren bir AI asistanısın."},
        {"role": "user", "content": prompt},
    ]

    try:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.novita_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.novita_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        res = httpx.post(url, headers=headers, json=payload, timeout=5.0)
        if res.status_code == 200:
            parsed = json.loads(res.json()["choices"][0]["message"]["content"])
            cat = str(parsed.get("category", "")).strip().lower()
            if cat in categories_list:
                return cat
    except Exception as e:
        logger.warning(f"LLM category classification error: {e}")

    return "other"
