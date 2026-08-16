from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama genelinde kullanılan, .env üzerinden okunan ayarlar."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    redis_url: str | None = None
    iyzico_api_key: str = "sandbox-dummy-api-key"
    iyzico_secret_key: str = "sandbox-dummy-secret-key"
    # HTTPSConnection takes a bare host, not a URL -- no scheme prefix here.
    iyzico_base_url: str = "sandbox-api.iyzipay.com"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str = "noreply@findyourbuddy.com"

    daily_swipe_limit: int = 10
    daily_super_like_limit: int = 1
    premium_daily_super_like_limit: int = 5
    weekly_event_creation_limit: int = 3
    match_common_interest_weight: float = 0.6
    match_distance_weight: float = 0.4
    match_max_distance_km: float = 50.0

    rate_limit_default_per_minute: int = 100
    rate_limit_auth_per_minute: int = 10
    rate_limit_messages_per_minute: int = 30
    rate_limit_event_writes_per_minute: int = 20

    moderation_banned_words: str = "spam,scam"

    novita_api_key: str = ""
    novita_base_url: str = "https://api.novita.ai/v3/openai"
    novita_model: str = "deepseek/deepseek-r1-distill-llama-70b"
    novita_vision_model: str = "meta-llama/llama-3.2-11b-vision-instruct"

    scraper_api_key: str
    allowed_event_categories: list[str] = [
        "running",
        "coffee",
        "concert",
        "climbing",
        "hiking",
        "cycling",
        "yoga",
        "boardgames",
        "football",
        "party",
        "theatre",
        "art",
        "workshop",
        "hobby",
        "other",
    ]

    @field_validator("allowed_event_categories", mode="before")
    @classmethod
    def _split_allowed_event_categories(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    media_root: str = "media"
    media_base_url: str = "/media"
    public_base_url: str = "http://127.0.0.1:8000"

    push_provider: str = "logging"
    expo_push_api_url: str = "https://exp.host/--/api/v2/push/send"

    # SMS gönderim altyapısı: hesap/API bilgisi olmadan "logging" kalır (kod
    # sadece sunucu loglarında görünür, kullanıcı kayıt sırasında otomatik
    # doğrulanmış sayılır). Netgsm hesabı açılınca bu üç alanı .env'e
    # eklemek + sms_provider="netgsm" yapmak yeterli, kod değişikliği gerekmez.
    sms_provider: str = "logging"
    netgsm_username: str = ""
    netgsm_password: str = ""
    netgsm_header: str = ""

    cors_allowed_origins: str = "*"
    log_level: str = "INFO"

    sentry_dsn: str = ""
    environment: str = "development"

    event_retention_days: int = 30
    scheduler_interval_hours: float = 6.0

    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "findyourbuddy-app/0.1 (contact@findyourbuddy.dev)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
