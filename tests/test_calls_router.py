from fastapi.testclient import TestClient

import app.routers.calls as calls_module


def test_get_ice_servers_requires_auth(client: TestClient) -> None:
    response = client.get("/calls/ice-servers")
    assert response.status_code == 401


def test_get_ice_servers_returns_stun_by_default(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/calls/ice-servers", headers=auth_headers)

    assert response.status_code == 200
    ice_servers = response.json()["ice_servers"]
    assert isinstance(ice_servers, list)
    stun_urls = [s["urls"] for s in ice_servers]
    assert any("stun:" in url for url in stun_urls)


def test_get_ice_servers_includes_turn_when_configured(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from app.config import Settings

    fake_settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret_key="test-secret",
        scraper_api_key="test",
        turn_urls=["turn:turn.example.com:3478"],
        turn_username="user",
        turn_credential="pass",
    )
    monkeypatch.setattr(calls_module, "get_settings", lambda: fake_settings)

    response = client.get("/calls/ice-servers", headers=auth_headers)

    assert response.status_code == 200
    ice_servers = response.json()["ice_servers"]
    turn_servers = [s for s in ice_servers if "turn:" in s["urls"]]
    assert len(turn_servers) == 1
    assert turn_servers[0]["username"] == "user"
    assert turn_servers[0]["credential"] == "pass"
