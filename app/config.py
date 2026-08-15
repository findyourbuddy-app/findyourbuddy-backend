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
    iyzico_base_url: str = "https://sandbox-api.iyzipay.com"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str = "noreply@findyourbuddy.com"

    daily_swipe_limit: int = 50
    daily_super_like_limit: int = 1
    premium_daily_super_like_limit: int = 5
    match_common_interest_weight: float = 0.6
    match_distance_weight: float = 0.4
    match_max_distance_km: float = 50.0

    rate_limit_default_per_minute: int = 100
    rate_limit_auth_per_minute: int = 10

    moderation_banned_words: str = "spam,scam"

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

    cors_allowed_origins: str = "*"
    log_level: str = "INFO"

    sentry_dsn: str = ""
    environment: str = "development"

    event_retention_days: int = 30
    scheduler_interval_hours: float = 6.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
