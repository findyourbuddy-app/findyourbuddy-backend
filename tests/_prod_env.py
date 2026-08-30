"""Shared helper: a fully valid ENVIRONMENT=production env for tests that need
Settings to pass _check_production_secrets."""

import pytest

_VALID_PRODUCTION_ENV = {
    "ENVIRONMENT": "production",
    "IYZICO_API_KEY": "prod-real-api-key",
    "IYZICO_SECRET_KEY": "prod-real-secret-key",
    "IYZICO_BASE_URL": "api.iyzipay.com",
    "PUBLIC_BASE_URL": "https://findyourbuddy.dev",
    "CORS_ALLOWED_ORIGINS": "https://findyourbuddy.dev",
    "JWT_SECRET_KEY": "x" * 48,
    "SCRAPER_API_KEY": "prod-real-scraper-key",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USERNAME": "mailer",
    "SMTP_PASSWORD": "mailer-pass",
    "EVENT_RETENTION_DAYS": "30",
    # SENTRY_DSN left unset on purpose -- missing DSN only warns, and a fake DSN
    # makes the SDK attempt real network sends during tests.
}


def apply_valid_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _VALID_PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)
