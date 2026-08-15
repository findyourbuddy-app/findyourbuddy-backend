import httpx

from app.config import get_settings


class GeocodingResult:
    def __init__(self, display_name: str, latitude: float, longitude: float) -> None:
        self.display_name = display_name
        self.latitude = latitude
        self.longitude = longitude


def search_locations(query: str, limit: int = 5) -> list[GeocodingResult]:
    """Forward-geocodes a free-text query (address/place name) into a short
    list of candidate locations, so users can pick an exact spot on a map
    instead of typing raw coordinates."""
    settings = get_settings()
    response = httpx.get(
        f"{settings.geocoding_base_url}/search",
        params={"q": query, "format": "json", "limit": limit, "addressdetails": 0},
        headers={"User-Agent": settings.geocoding_user_agent},
        timeout=10.0,
    )
    response.raise_for_status()
    return [
        GeocodingResult(
            display_name=item["display_name"],
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
        )
        for item in response.json()
    ]
