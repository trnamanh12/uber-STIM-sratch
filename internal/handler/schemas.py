"""
internal/handler/schemas.py - Wire protocol request & response schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GeoCoordinateSchema(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude [-90, 90]")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude [-180, 180]")


class TripCreateRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, description="Unique client idempotency token")
    rider_id: str = Field(..., min_length=1, description="ID of requesting rider")
    origin: GeoCoordinateSchema
    destination: GeoCoordinateSchema
    passenger_count: int = Field(default=1, ge=1, le=6, description="Number of passengers")


class CancelTripRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for cancellation")


class AddWaypointRequest(BaseModel):
    waypoint: GeoCoordinateSchema


class TripResponse(BaseModel):
    trip_id: str
    rider_id: str
    driver_id: Optional[str]
    state: str
    origin: GeoCoordinateSchema
    destination: GeoCoordinateSchema
    current_position: GeoCoordinateSchema
    distance_km: float
    duration_seconds: float
    fare: float
    cancel_reason: Optional[str] = None
    waypoints: list[GeoCoordinateSchema] = Field(default_factory=list)
    visited_waypoints: list[GeoCoordinateSchema] = Field(default_factory=list)


class MatchDriverResponse(BaseModel):
    trip_id: str
    driver_id: str
    driver_name: str
    eta_minutes: float
    trip_state: str
