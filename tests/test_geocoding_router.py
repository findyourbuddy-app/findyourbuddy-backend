from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "S3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _mock_response(payload: list[dict]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_search_requires_auth(client: TestClient) -> None:
    response = client.get("/geocoding/search", params={"q": "Kadıköy"})

    assert response.status_code == 401


def test_search_rejects_short_query(client: TestClient) -> None:
    headers = _register_and_login(client, "ada@example.com")

    response = client.get("/geocoding/search", params={"q": "ab"}, headers=headers)

    assert response.status_code == 400


def test_search_returns_mapped_results(client: TestClient) -> None:
    headers = _register_and_login(client, "ada@example.com")
    payload = [{"display_name": "Kadıköy, İstanbul", "lat": "40.99", "lon": "29.03"}]

    with patch("app.services.geocoding_service.httpx.get", return_value=_mock_response(payload)):
        response = client.get("/geocoding/search", params={"q": "Kadıköy"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body[0]["display_name"] == "Kadıköy, İstanbul"
    assert body[0]["latitude"] == 40.99
