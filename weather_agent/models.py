from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str
    province: str
    district: str
    latitude: float
    longitude: float
    elevation_m: float
    country_code: str = ""

