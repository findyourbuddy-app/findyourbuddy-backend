import importlib

from fastapi.testclient import TestClient

from tests._prod_env import apply_valid_production_env


def _reload_app_with_environment(monkeypatch, environment: str):
    from app.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", environment)
    if environment == "production":
        apply_valid_production_env(monkeypatch)
    get_settings.cache_clear()

    import app.main as main_module

    importlib.reload(main_module)
    return main_module.app


def test_docs_enabled_outside_production(monkeypatch) -> None:
    app = _reload_app_with_environment(monkeypatch, "development")
    client = TestClient(app)

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_in_production(monkeypatch) -> None:
    app = _reload_app_with_environment(monkeypatch, "production")
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
