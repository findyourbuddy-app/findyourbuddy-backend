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


@lru_cache
def get_settings() -> Settings:
    return Settings()
