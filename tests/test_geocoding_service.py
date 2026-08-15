from unittest.mock import MagicMock, patch

from app.services.geocoding_service import search_locations


def _mock_response(payload: list[dict]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_search_locations_maps_nominatim_response() -> None:
    payload = [
        {"display_name": "Kadıköy, İstanbul, Türkiye", "lat": "40.99", "lon": "29.03"},
    ]
    with patch("app.services.geocoding_service.httpx.get", return_value=_mock_response(payload)) as mock_get:
        results = search_locations("Kadıköy")

    assert len(results) == 1
    assert results[0].display_name == "Kadıköy, İstanbul, Türkiye"
    assert results[0].latitude == 40.99
    assert results[0].longitude == 29.03
    assert mock_get.call_args.kwargs["params"]["q"] == "Kadıköy"
    assert "User-Agent" in mock_get.call_args.kwargs["headers"]


def test_search_locations_returns_empty_list_when_no_matches() -> None:
    with patch("app.services.geocoding_service.httpx.get", return_value=_mock_response([])):
        results = search_locations("asdkjhasdkjhasd")

    assert results == []
