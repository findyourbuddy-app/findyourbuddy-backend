from pydantic import BaseModel


class GeocodingResultRead(BaseModel):
    display_name: str
    latitude: float
    longitude: float
