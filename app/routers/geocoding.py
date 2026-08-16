from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.geocoding import GeocodingResultRead
from app.services.geocoding_service import reverse_geocode, search_locations

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.get("/search", response_model=list[GeocodingResultRead])
def search(
    q: str,
    _current_user: User = Depends(get_current_user),
) -> list[GeocodingResultRead]:
    if len(q.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query must be at least 3 characters"
        )
    results = search_locations(q.strip())
    return [
        GeocodingResultRead(
            display_name=r.display_name, latitude=r.latitude, longitude=r.longitude
        )
        for r in results
    ]


@router.get("/reverse", response_model=GeocodingResultRead)
def reverse(
    lat: float,
    lon: float,
    _current_user: User = Depends(get_current_user),
) -> GeocodingResultRead:
    result = reverse_geocode(lat, lon)
    return GeocodingResultRead(
        display_name=result.display_name, latitude=result.latitude, longitude=result.longitude
    )
