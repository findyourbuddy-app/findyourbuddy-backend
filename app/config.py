import logging
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Substrings that mark a value as a leftover placeholder rather than a real
# production secret. Matched case-insensitively.
_PLACEHOLDER_MARKERS = ("change-me", "changeme", "change_me", "dummy", "sandbox", "placeholder", "your-", "example")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    """Uygulama genelinde kullanılan, .env üzerinden okunan ayarlar."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    # Postgres connection pool + timeouts. statement_timeout is the important
    # one: it caps how long a single query can pin a request-handler thread,
    # so one slow DB moment can't cascade into an unrecoverable freeze.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_s: int = 10
    db_pool_recycle_s: int = 1800
    db_connect_timeout_s: int = 10
    db_statement_timeout_ms: int = 8000
    db_lock_timeout_ms: int = 4000
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
    # coturn "use-auth-secret" REST API. When set, /calls/ice-servers issues a
    # short-lived HMAC credential per request instead of the static pair above.
    turn_static_auth_secret: str = ""
    turn_credential_ttl_seconds: int = 86400

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
    # UTC hour the like / super-like allowance resets. 21 == 00:00 in Turkey
    # (UTC+3), so the daily reset lands at local midnight.
    daily_quota_reset_hour_utc: int = 21
    weekly_event_creation_limit: int = 3
    match_common_interest_weight: float = 0.6
    match_distance_weight: float = 0.4
    match_max_distance_km: float = 50.0

    rate_limit_default_per_minute: int = 100
    rate_limit_auth_per_minute: int = 10
    rate_limit_messages_per_minute: int = 30
    rate_limit_event_writes_per_minute: int = 20
    rate_limit_ai_per_minute: int = 5
    # Empty -> in-memory counters (fine for a single process). Set to a shared
    # store (e.g. the Redis URL) so limits stay correct across multiple workers
    # or hosts -- otherwise each process enforces its own copy of the limit.
    rate_limit_storage_uri: str = ""

    moderation_banned_words: str = "spam,scam"

    novita_api_key: str = ""
    novita_base_url: str = "https://api.novita.ai/openai"
    novita_model: str = "deepseek/deepseek-v4-flash"
    novita_vision_model: str = "qwen/qwen3.6-27b"

    scraper_api_key: str
    # Lets Prometheus scrape /health/metrics without a staff JWT. Empty = only
    # a staff JWT is accepted (endpoint stays private).
    metrics_api_key: str = ""

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
    admin_alert_email: str = ""

    push_provider: str = "logging"
    expo_push_api_url: str = "https://exp.host/--/api/v2/push/send"

    cors_allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,https://findyourbuddy.dev"
    log_level: str = "INFO"

    sentry_dsn: str = ""
    environment: str = "development"

    event_retention_days: float = 0.25
    scheduler_interval_hours: float = 6.0
    # The periodic cleanup jobs (see app/core/scheduler.py). With more than one
    # web worker, disable this on the workers and run one dedicated process with
    # it enabled -- a Postgres advisory lock still guards against overlap.
    scheduler_enabled: bool = True

    # Trust score is a 0-100 value recomputed from a user's real signals (see
    # trust_service.recompute_trust_score) -- never an unbounded running total.
    trust_base_score: int = 30
    trust_photo_verified_points: int = 25
    trust_phone_verified_points: int = 8
    trust_email_verified_points: int = 5
    trust_attendance_max_points: int = 15
    trust_rating_swing_points: int = 12  # +/- at a 5-star / 1-star average
    trust_rating_min_count: int = 2      # ratings received before they count
    trust_meetup_points_each: int = 2
    trust_meetup_max_points: int = 8
    trust_no_show_penalty_each: int = 5
    trust_no_show_max_penalty: int = 20
    trust_report_reviewed_penalty: int = 10
    trust_report_pending_penalty: int = 3
    trust_report_max_penalty: int = 30
    trust_block_penalty_each: int = 2
    trust_block_max_penalty: int = 10

    # Accounts are suspended (is_active=False) once trust_score has stayed
    # below the threshold for this many consecutive days -- not on a single
    # low reading, so one bad night doesn't nuke an otherwise good account.
    trust_score_suspension_threshold: int = 15
    trust_score_suspension_grace_days: int = 14

    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "findyourbuddy-app/0.1 (contact@findyourbuddy.dev)"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.environment != "production":
            return self

        errors: list[str] = []

        # Payments
        if _looks_like_placeholder(self.iyzico_api_key):
            errors.append("iyzico_api_key must be a real production key")
        if _looks_like_placeholder(self.iyzico_secret_key):
            errors.append("iyzico_secret_key must be a real production key")
        if "sandbox" in self.iyzico_base_url:
            errors.append("iyzico_base_url must be the production endpoint")

        # URLs / CORS
        if not self.public_base_url:
            errors.append("public_base_url must be set")
        if "*" in self.cors_allowed_origins:
            errors.append("cors_allowed_origins must not contain '*' -- list explicit origins")

        # Auth / API keys
        if _looks_like_placeholder(self.jwt_secret_key) or len(self.jwt_secret_key) < 32:
            errors.append("jwt_secret_key must be a strong, non-placeholder value (>= 32 chars)")
        if _looks_like_placeholder(self.scraper_api_key):
            errors.append("scraper_api_key must be a real value, not a placeholder")
        if self.metrics_api_key and _looks_like_placeholder(self.metrics_api_key):
            errors.append("metrics_api_key must be a real value, not a placeholder")

        # Password reset delivery -- without SMTP the reset code only lands in
        # the logs and the user never gets it, while the endpoint still says 200.
        if not (self.smtp_host and self.smtp_username and self.smtp_password):
            errors.append("smtp_host / smtp_username / smtp_password must all be set (password reset needs email)")

        # Data retention -- the 0.25 (6h) dev value would wipe events almost
        # immediately in production.
        if self.event_retention_days < 1:
            errors.append("event_retention_days looks like a dev value (< 1); set a real retention period")

        if errors:
            raise ValueError(
                "invalid production configuration:\n  - " + "\n  - ".join(errors)
            )

        if not self.sentry_dsn:
            logger.warning(
                "sentry_dsn is not set -- running in production without error tracking"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
