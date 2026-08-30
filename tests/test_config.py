import pytest

from app.config import Settings

_BASE = {
    "database_url": "postgresql://u:p@db/app",
    "jwt_secret_key": "x" * 48,
    "scraper_api_key": "a-real-scraper-key",
    "environment": "production",
    "public_base_url": "https://api.findyourbuddy.app",
    "cors_allowed_origins": "https://findyourbuddy.app",
    "iyzico_api_key": "real-key",
    "iyzico_secret_key": "real-secret",
    "iyzico_base_url": "api.iyzipay.com",
    "smtp_host": "smtp.example.com",
    "smtp_username": "mailer",
    "smtp_password": "mailer-pass",
    "event_retention_days": 30,
    "sentry_dsn": "https://x@sentry.io/1",
}


def _settings(**overrides) -> Settings:
    return Settings(**{**_BASE, **overrides})


def test_valid_production_config_passes() -> None:
    _settings()


def test_development_config_skips_production_checks() -> None:
    Settings(
        database_url="sqlite:///:memory:",
        jwt_secret_key="short",
        scraper_api_key="change-me",
        environment="development",
    )


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"smtp_username": ""}, "smtp"),
        ({"smtp_password": ""}, "smtp"),
        ({"jwt_secret_key": "change-me-please-really"}, "jwt_secret_key"),
        ({"jwt_secret_key": "short"}, "jwt_secret_key"),
        ({"cors_allowed_origins": "*"}, "cors_allowed_origins"),
        ({"cors_allowed_origins": "https://a.app,*"}, "cors_allowed_origins"),
        ({"scraper_api_key": "change-me"}, "scraper_api_key"),
        ({"iyzico_api_key": "sandbox-dummy-api-key"}, "iyzico_api_key"),
        ({"event_retention_days": 0.25}, "event_retention_days"),
    ],
)
def test_production_config_rejects_bad_values(overrides, expected) -> None:
    with pytest.raises(ValueError, match=expected):
        _settings(**overrides)


def test_production_without_sentry_warns_but_starts(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        _settings(sentry_dsn="")
    assert "sentry_dsn" in caplog.text
