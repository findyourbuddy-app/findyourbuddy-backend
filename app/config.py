from functools import lru_cache

from pydantic import field_validator, model_validator
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
    iyzico_buyer_identity_number: str = "11111111111"
    subscription_price_try: str = "99.00"

    turn_urls: list[str] = []
    turn_username: str = ""
    turn_credential: str = ""

    @field_validator("turn_urls", mode="before")
    @classmethod
    def _split_turn_urls(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            return [u.strip() for u in value.split(",") if u.strip()]
        return value
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30
    jwt_refresh_expire_days: int = 30

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
    rate_limit_ai_per_minute: int = 5

    moderation_banned_words: str = "spam,scam"

    novita_api_key: str = ""
    novita_base_url: str = "https://api.novita.ai/openai"
    novita_model: str = "deepseek/deepseek-v4-flash"
    novita_vision_model: str = "qwen/qwen3.6-27b"

    scraper_api_key: str

    # Firebase Admin service account, as raw JSON (single line). Used to
    # relay chat messages into Firestore server-side, after moderation and
    # rate-limiting, instead of the client writing there directly.
    firebase_service_account_json: str = ""
    allowed_event_categories: list[str] = [
        "running",
        "coffee",
        "concert",
        "festival",
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
    public_base_url: str = ""

    # "local" (default, disk-backed) or "s3" (AWS S3 or an S3-compatible
    # provider like Cloudflare R2). The disk backend is fine for a single
    # server but loses files if the container/volume goes away.
    media_storage_backend: str = "local"
    s3_bucket_name: str = ""
    s3_region: str = "auto"
    # Leave unset for real AWS S3. Set to the account endpoint for R2, e.g.
    # https://<account_id>.r2.cloudflarestorage.com
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    # Public base URL files are served from -- a CDN domain, an R2 public
    # bucket URL, or an S3 bucket website endpoint.
    s3_public_url_base: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    push_provider: str = "logging"
    expo_push_api_url: str = "https://exp.host/--/api/v2/push/send"

    cors_allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,https://findyourbuddy.dev"
    log_level: str = "INFO"

    sentry_dsn: str = ""
    environment: str = "development"

    event_retention_days: int = 0
    scheduler_interval_hours: float = 6.0

    # Accounts are suspended (is_active=False) once trust_score has stayed
    # below the threshold for this many consecutive days -- not on a single
    # low reading, so one bad night doesn't nuke an otherwise good account.
    trust_score_suspension_threshold: int = -5
    trust_score_suspension_grace_days: int = 14

    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "findyourbuddy-app/0.1 (contact@findyourbuddy.dev)"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.environment == "production":
            if "sandbox" in self.iyzico_api_key or "dummy" in self.iyzico_api_key:
                raise ValueError("iyzico_api_key must be a real production key in production environment")
            if "sandbox" in self.iyzico_secret_key or "dummy" in self.iyzico_secret_key:
                raise ValueError("iyzico_secret_key must be a real production key in production environment")
            if "sandbox" in self.iyzico_base_url:
                raise ValueError("iyzico_base_url must be the production endpoint in production environment")
            if not self.public_base_url:
                raise ValueError("public_base_url must be set in production environment")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
