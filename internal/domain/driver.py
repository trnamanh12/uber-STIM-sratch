"""
internal/domain/driver.py - Driver Entity, States & Geodesic Mathematics.

Zero external framework dependencies. Pure domain logic.
"""

from enum import Enum
import math
from typing import Optional
from internal.domain.trip import GeoCoordinate, IllegalStateTransitionError, InvariantViolationError


class DriverState(str, Enum):
    """Explicit states for mobility fleet drivers."""
    IDLE = "IDLE"
    ASSIGNED = "ASSIGNED"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


def haversine_distance_km(coord1: GeoCoordinate, coord2: GeoCoordinate) -> float:
    """
    Computes Great-Circle spherical distance between two coordinates in kilometers.
    Earth radius R = 6371.0 km.
    """
    r_earth = 6371.0
    lat1_rad = math.radians(coord1.lat)
    lon1_rad = math.radians(coord1.lon)
    lat2_rad = math.radians(coord2.lat)
    lon2_rad = math.radians(coord2.lon)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


class Driver:
    """Represents a driver in the mobility fleet."""

    def __init__(self, driver_id: str, name: str, location: GeoCoordinate) -> None:
        if not driver_id or not driver_id.strip():
            raise InvariantViolationError("Driver ID cannot be empty")
        if not name or not name.strip():
            raise InvariantViolationError("Driver name cannot be empty")

        self.driver_id = driver_id
        self.name = name
        self.location = location
        self.state = DriverState.IDLE
        self.assigned_trip_id: Optional[str] = None
        self.version: int = 1

    def update_location(self, new_location: GeoCoordinate) -> None:
        self.location = new_location
        self.version += 1

    def assign_to_trip(self, trip_id: str) -> None:
        if self.state != DriverState.IDLE:
            raise IllegalStateTransitionError(
                f"Driver {self.driver_id} is in state {self.state.value}; cannot be assigned to trip {trip_id}"
            )
        self.state = DriverState.ASSIGNED
        self.assigned_trip_id = trip_id
        self.version += 1

    def mark_busy(self) -> None:
        self.state = DriverState.BUSY
        self.version += 1

    def release(self) -> None:
        self.state = DriverState.IDLE
        self.assigned_trip_id = None
        self.version += 1
