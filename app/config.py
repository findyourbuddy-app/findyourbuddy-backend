from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama genelinde kullanılan, .env üzerinden okunan ayarlar."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    daily_swipe_limit: int = 50
    match_common_interest_weight: float = 0.6
    match_distance_weight: float = 0.4
    match_max_distance_km: float = 50.0

    rate_limit_default_per_minute: int = 100
    rate_limit_auth_per_minute: int = 10

    moderation_banned_words: str = "spam,scam"

    media_root: str = "media"
    media_base_url: str = "/media"

    cors_allowed_origins: str = "*"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
