import json
import logging
import re
import httpx

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from app.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)


def generate_llm_kanka_synergy(user1: User, user2: User) -> dict:
    """Generates an LLM-powered Kanka friendship match score & detailed synergy report using Novita AI."""
    settings = get_settings()

    # Pre-calculate base Jaccard similarity for hobbies & interests
    hobbies1 = set(user1.hobbies or [])
    hobbies2 = set(user2.hobbies or [])
    shared_hobbies = list(hobbies1.intersection(hobbies2))

    interests1 = set(user1.interests or [])
    interests2 = set(user2.interests or [])
    shared_interests = list(interests1.intersection(interests2))

    if not settings.novita_api_key:
        # Fallback intelligent rule-based synergy generator when key is missing
        base_score = 70 + len(shared_hobbies) * 8 + len(shared_interests) * 5
        score = min(99, max(55, base_score))
        return {
            "score": score,
            "synergy_title": f"%{score} Uyumlu Aktivite Kankası 🎯",
            "summary": f"{user1.display_name} ve {user2.display_name} ortak hobileri ve astrolojik uyumlarıyla harika bir kanka ikilisi oluşturuyor.",
            "highlights": [
                f"Ortak Hobiler: {', '.join(shared_hobbies) if shared_hobbies else 'Spor ve Sosyal Etkinlikler'}",
                f"Zodyak Element Sinerjisi: {user1.zodiac_sign or 'Bilinmiyor'} & {user2.zodiac_sign or 'Bilinmiyor'}",
                "Birlikte yeni grup etkinliklerine katılmak için harika bir enerji!",
            ],
            "shared_hobbies": shared_hobbies,
        }

    prompt = (
        "Sen gelişmiş bir Yapay Zeka Kanka Eşleştiricisisin.\n"
        "İki kullanıcının profillerini analiz et ve aralarındaki arkadaşlık uyumunu hesapla.\n\n"
        f"Kullanıcı 1 ({user1.display_name}): Yaş={user1.age}, Burç={user1.zodiac_sign}, Hobiler={user1.hobbies}, Biyo='{user1.bio}'\n"
        f"Kullanıcı 2 ({user2.display_name}): Yaş={user2.age}, Burç={user2.zodiac_sign}, Hobiler={user2.hobbies}, Biyo='{user2.bio}'\n\n"
        "Yanıtı SADECE geçerli bir JSON objesi olarak dön (markdown veya ekstra metin yazma):\n"
        "{\n"
        '  "score": 94,\n'
        '  "synergy_title": "%94 Harika Kahve & Spor Kankası ☕⚽",\n'
        '  "summary": "İkiniz de haftasonu outdoor aktivitelerden hoşlanıyorsunuz...",\n'
        '  "highlights": [\n'
        '    "Ortak Tenis ve Fitness merakı",\n'
        '    "Astrolojik element uyumu yüksek",\n'
        '    "Benzer yaşam temposu"\n'
        "  ]\n"
        "}"
    )

    base_url = settings.novita_base_url.rstrip("/")
    messages = [
        {"role": "system", "content": "Sen yalnızca JSON çıktısı veren bir AI asistanısın."},
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
                logger.warning(f"Novita LLM Matchmaker API status {response.status_code}: {response.text}")
        except Exception as http_err:
            logger.error(f"Failed to generate LLM kanka synergy: {http_err}")

    if raw_content:
        try:
            cleaned = re.sub(r"```json\s*", "", raw_content)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            parsed = json.loads(cleaned)
            parsed["shared_hobbies"] = shared_hobbies
            return parsed
        except Exception as parse_err:
            logger.error(f"Failed to parse LLM kanka synergy response: {parse_err}")

    score = min(99, max(60, 75 + len(shared_hobbies) * 6))
    return {
        "score": score,
        "synergy_title": f"%{score} İdeal Kanka İkilisi ✨",
        "summary": f"{user1.display_name} ve {user2.display_name} ortak ilgi alanlarıyla harika anlaşıyor.",
        "highlights": [
            f"Ortak Hobiler: {', '.join(shared_hobbies) if shared_hobbies else 'Genel Aktivite'}",
            f"Burç Uyumu: {user1.zodiac_sign or 'Bilinmiyor'} & {user2.zodiac_sign or 'Bilinmiyor'}",
            "Sosyal dinamikleri yüksek",
        ],
        "shared_hobbies": shared_hobbies,
    }
