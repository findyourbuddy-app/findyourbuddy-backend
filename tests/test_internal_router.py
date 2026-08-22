from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings


def _batch_payload(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "external_id": "evt-1",
        "source": "biletix",
        "title": "Trail run",
        "category": "running",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    event.update(overrides)
    return {"events": [event]}


def test_ingest_without_api_key_returns_401(client: TestClient) -> None:
    response = client.post("/internal/events/ingest", json=_batch_payload())

    assert response.status_code == 401


def test_ingest_with_wrong_api_key_returns_401(client: TestClient) -> None:
    response = client.post(
        "/internal/events/ingest",
        json=_batch_payload(),
        headers={"X-Scraper-Api-Key": "wrong-key"},
    )

    assert response.status_code == 401


def test_ingest_with_correct_api_key_returns_result(client: TestClient) -> None:
    response = client.post(
        "/internal/events/ingest",
        json=_batch_payload(),
        headers={"X-Scraper-Api-Key": get_settings().scraper_api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"created": 1, "updated": 0, "skipped": 0, "errors": []}
