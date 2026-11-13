"""
core.py - Domain State Machine, Failure Hardening & Spatial Dispatch Engine

Includes:
1. Haversine 2D Spherical Geodesic Distance Engine
2. Driver Pool Management (IDLE, ASSIGNED, BUSY, OFFLINE)
3. Spatial Dispatcher: Nearest-driver matching with radius bounds & graceful backoff
4. Invariants, Failure-first protections (Q1-Q4)
"""

from dataclasses import asdict, dataclass
from enum import Enum
import math
import time
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple
import uuid


class DomainError(Exception):
    """Base exception for all domain logic violations."""
    pass


class IllegalStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    pass


class InvariantViolationError(DomainError):
    """Raised when a core system invariant is broken."""
    pass


class PoisonPayloadError(DomainError):
    """Raised when an incoming packet violates boundary types or limits."""
    pass


class NoDriverAvailableError(DomainError):
    """Raised when dispatch engine cannot find an eligible nearby driver."""
    pass


class TripState(str, Enum):
    """Explicit lifecycle states for a mobility trip."""
    REQUESTED = "REQUESTED"
    MATCHED = "MATCHED"
    DRIVER_ARRIVING = "DRIVER_ARRIVING"
    IN_TRANSIT = "IN_TRANSIT"
    DROPPED_OFF = "DROPPED_OFF"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DriverState(str, Enum):
    """Explicit states for mobility drivers."""
    IDLE = "IDLE"
    ASSIGNED = "ASSIGNED"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


ALLOWED_TRANSITIONS: Dict[TripState, Set[TripState]] = {
    TripState.REQUESTED: {TripState.MATCHED, TripState.CANCELLED},
    TripState.MATCHED: {TripState.DRIVER_ARRIVING, TripState.CANCELLED},
    TripState.DRIVER_ARRIVING: {TripState.IN_TRANSIT, TripState.CANCELLED},
    TripState.IN_TRANSIT: {TripState.DROPPED_OFF, TripState.CANCELLED},
    TripState.DROPPED_OFF: {TripState.COMPLETED},
    TripState.COMPLETED: set(),  # Terminal Lock
    TripState.CANCELLED: set(),  # Terminal Lock
}


@dataclass(frozen=True)
class GeoCoordinate:
    """
    Guards Against Q1 (The Poison Pill).
    Enforces strict geospatial validity (-90 <= lat <= 90, -180 <= lon <= 180, no NaN/Inf).
    """
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not isinstance(self.lat, (int, float)) or not isinstance(self.lon, (int, float)):
            raise PoisonPayloadError(f"Coordinates must be numeric. Got lat={type(self.lat)}, lon={type(self.lon)}")
        if math.isnan(self.lat) or math.isinf(self.lat):
            raise PoisonPayloadError(f"Poison coordinate detected: latitude is NaN or Inf ({self.lat})")
        if math.isnan(self.lon) or math.isinf(self.lon):
            raise PoisonPayloadError(f"Poison coordinate detected: longitude is NaN or Inf ({self.lon})")
        if not (-90.0 <= self.lat <= 90.0):
            raise PoisonPayloadError(f"Latitude out of bounds [-90, 90]: {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise PoisonPayloadError(f"Longitude out of bounds [-180, 180]: {self.lon}")


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


@dataclass(frozen=True)
class TripRequestPayload:
    idempotency_key: str
    rider_id: str
    origin: GeoCoordinate
    destination: GeoCoordinate
    passenger_count: int = 1

    def __post_init__(self) -> None:
        if not self.idempotency_key or not self.idempotency_key.strip():
            raise PoisonPayloadError("Idempotency key cannot be empty")
        if not self.rider_id or not self.rider_id.strip():
            raise PoisonPayloadError("Rider ID cannot be empty")
        if not isinstance(self.passenger_count, int) or not (1 <= self.passenger_count <= 6):
            raise PoisonPayloadError(
                f"Passenger count must be an integer between 1 and 6. Got: {self.passenger_count}"
            )
        if self.origin == self.destination:
            raise PoisonPayloadError("Origin and Destination coordinates cannot be identical")


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    correlation_id: str
    event_type: str
    timestamp: float
    payload: Dict[str, Any]


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

    def update_location(self, new_location: GeoCoordinate) -> None:
        self.location = new_location

    def assign_to_trip(self, trip_id: str) -> None:
        if self.state != DriverState.IDLE:
            raise IllegalStateTransitionError(
                f"Driver {self.driver_id} is in state {self.state.value}; cannot be assigned to trip {trip_id}"
            )
        self.state = DriverState.ASSIGNED
        self.assigned_trip_id = trip_id

    def mark_busy(self) -> None:
        self.state = DriverState.BUSY

    def release(self) -> None:
        self.state = DriverState.IDLE
        self.assigned_trip_id = None


class DriverPool:
    """Manages the in-memory pool of active fleet drivers."""

    def __init__(self) -> None:
        self._drivers: Dict[str, Driver] = {}

    def register_driver(self, driver: Driver) -> None:
        self._drivers[driver.driver_id] = driver

    def get_driver(self, driver_id: str) -> Optional[Driver]:
        return self._drivers.get(driver_id)

    def list_available_drivers(self) -> List[Driver]:
        return [d for d in self._drivers.values() if d.state == DriverState.IDLE]

    def all_drivers(self) -> List[Driver]:
        return list(self._drivers.values())


class DispatchEngine:
    """
    Spatial Dispatch Engine:
    Selects the nearest available driver to rider pickup using Haversine metric.
    """

    def __init__(self, driver_pool: DriverPool, default_search_radius_km: float = 10.0) -> None:
        self.driver_pool = driver_pool
        self.default_search_radius_km = default_search_radius_km

    def match_nearest_driver(
        self, pickup: GeoCoordinate, max_search_radius_km: Optional[float] = None
    ) -> Tuple[Driver, float, float]:
        """
        Finds the nearest IDLE driver within search radius.
        Returns (Driver, distance_km, eta_minutes).
        Raises NoDriverAvailableError if none found.
        """
        radius = max_search_radius_km or self.default_search_radius_km
        available = self.driver_pool.list_available_drivers()
        if not available:
            raise NoDriverAvailableError("No available idle drivers found in fleet")

        best_driver: Optional[Driver] = None
        min_distance = float("inf")

        for driver in available:
            dist = haversine_distance_km(driver.location, pickup)
            if dist < min_distance and dist <= radius:
                min_distance = dist
                best_driver = driver

        if best_driver is None:
            raise NoDriverAvailableError(
                f"No idle drivers found within search radius of {radius:.1f} km"
            )

        # Estimate ETA assuming average urban speed of 30 km/h
        eta_minutes = round((min_distance / 30.0) * 60.0, 1)
        return best_driver, round(min_distance, 3), max(1.0, eta_minutes)


class Trip:
    """
    Hardened Trip Aggregate Root.
    Guarantees invariants, records structured events, and supports crash recovery.
    """

    def __init__(
        self,
        trip_id: str,
        rider_id: str,
        origin: GeoCoordinate,
        destination: GeoCoordinate,
        passenger_count: int = 1,
        idempotency_key: Optional[str] = None,
    ) -> None:
        if not trip_id or not trip_id.strip():
            raise InvariantViolationError("Trip ID cannot be empty")
        if not rider_id or not rider_id.strip():
            raise InvariantViolationError("Rider ID cannot be empty")
        if origin == destination:
            raise InvariantViolationError("Origin and Destination cannot be identical")

        self.trip_id = trip_id
        self.rider_id = rider_id
        self.origin = origin
        self._locked_destination: GeoCoordinate = destination
        self.passenger_count = passenger_count
        self.idempotency_key = idempotency_key or f"idem-{trip_id}"

        self.driver_id: Optional[str] = None
        self.current_lat: float = origin.lat
        self.current_lon: float = origin.lon
        self.state: TripState = TripState.REQUESTED

        # Invariant C: Non-negative metrics
        self.distance_km: float = 0.0
        self.duration_seconds: float = 0.0
        self.fare: float = 0.0
        self.cancel_reason: Optional[str] = None

        # Event ledger
        self.events: List[DomainEvent] = []
        self._record_event("TRIP_CREATED", {
            "origin": asdict(self.origin),
            "destination": asdict(self._locked_destination),
            "passenger_count": self.passenger_count,
        })
        self._verify_invariants()

    @property
    def destination(self) -> GeoCoordinate:
        return self._locked_destination

    def _record_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            correlation_id=self.trip_id,
            event_type=event_type,
            timestamp=time.time(),
            payload=payload,
        )
        self.events.append(event)

    def _verify_invariants(self) -> None:
        if self._locked_destination == self.origin:
            raise InvariantViolationError("Destination cannot collapse to origin")
        if self.distance_km < 0.0:
            raise InvariantViolationError(f"Negative distance violation: {self.distance_km}")
        if self.duration_seconds < 0.0:
            raise InvariantViolationError(f"Negative duration violation: {self.duration_seconds}")
        if self.fare < 0.0:
            raise InvariantViolationError(f"Negative fare violation: {self.fare}")

    def transition_to(self, target_state: TripState, reason: str = "") -> None:
        self._verify_invariants()

        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if target_state not in allowed:
            raise IllegalStateTransitionError(
                f"Illegal transition: Cannot transition from {self.state.value} to {target_state.value}. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )

        previous_state = self.state
        self.state = target_state
        self._record_event("STATE_TRANSITIONED", {
            "from_state": previous_state.value,
            "to_state": target_state.value,
            "reason": reason,
        })
        self._verify_invariants()

    def assign_driver(self, driver_id: str) -> None:
        if not driver_id or not driver_id.strip():
            raise InvariantViolationError("Cannot assign empty driver ID")
        self.driver_id = driver_id
        self.transition_to(TripState.MATCHED, f"Assigned to driver {driver_id}")

    def driver_arrived(self) -> None:
        if not self.driver_id:
            raise InvariantViolationError("Cannot arrive without an assigned driver")
        self.transition_to(TripState.DRIVER_ARRIVING, "Driver at pickup")

    def start_trip(self) -> None:
        self.transition_to(TripState.IN_TRANSIT, "Trip en route")

    def update_telemetry(self, lat: float, lon: float, distance_delta_km: float, time_delta_sec: float) -> None:
        if self.state != TripState.IN_TRANSIT:
            raise IllegalStateTransitionError(
                f"Cannot update transit telemetry while trip is in state {self.state.value}"
            )
        coord = GeoCoordinate(lat=lat, lon=lon)
        if distance_delta_km < 0.0:
            raise InvariantViolationError("Distance delta cannot be negative")
        if time_delta_sec < 0.0:
            raise InvariantViolationError("Time delta cannot be negative")

        self.current_lat = coord.lat
        self.current_lon = coord.lon
        self.distance_km += distance_delta_km
        self.duration_seconds += time_delta_sec

        self._record_event("TELEMETRY_UPDATED", {
            "lat": self.current_lat,
            "lon": self.current_lon,
            "distance_km": round(self.distance_km, 3),
            "duration_sec": round(self.duration_seconds, 1),
        })
        self._verify_invariants()

    def drop_off(self) -> None:
        self.current_lat = self.destination.lat
        self.current_lon = self.destination.lon
        self.transition_to(TripState.DROPPED_OFF, "Arrived at destination")

    def complete_trip(self, final_fare: float) -> None:
        if final_fare < 0.0:
            raise InvariantViolationError("Final fare must be non-negative")
        self.fare = final_fare
        self.transition_to(TripState.COMPLETED, f"Settled fare ${final_fare:.2f}")

    def cancel(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise InvariantViolationError("Cancellation reason must be provided")
        self.cancel_reason = reason
        self.transition_to(TripState.CANCELLED, reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "rider_id": self.rider_id,
            "origin": asdict(self.origin),
            "destination": asdict(self._locked_destination),
            "passenger_count": self.passenger_count,
            "idempotency_key": self.idempotency_key,
            "driver_id": self.driver_id,
            "current_lat": self.current_lat,
            "current_lon": self.current_lon,
            "state": self.state.value,
            "distance_km": self.distance_km,
            "duration_seconds": self.duration_seconds,
            "fare": self.fare,
            "cancel_reason": self.cancel_reason,
            "events": [asdict(e) for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trip":
        trip = cls(
            trip_id=data["trip_id"],
            rider_id=data["rider_id"],
            origin=GeoCoordinate(**data["origin"]),
            destination=GeoCoordinate(**data["destination"]),
            passenger_count=data["passenger_count"],
            idempotency_key=data["idempotency_key"],
        )
        trip.driver_id = data["driver_id"]
        trip.current_lat = data["current_lat"]
        trip.current_lon = data["current_lon"]
        trip.state = TripState(data["state"])
        trip.distance_km = data["distance_km"]
        trip.duration_seconds = data["duration_seconds"]
        trip.fare = data["fare"]
        trip.cancel_reason = data["cancel_reason"]
        trip.events = [DomainEvent(**e) for e in data.get("events", [])]
        return trip


class InMemoryTripRepository:
    def __init__(self) -> None:
        self._trips: Dict[str, Trip] = {}
        self._idempotency_registry: Dict[str, str] = {}

    def request_trip_idempotent(self, payload: TripRequestPayload) -> Tuple[Trip, bool]:
        if payload.idempotency_key in self._idempotency_registry:
            existing_trip_id = self._idempotency_registry[payload.idempotency_key]
            return self._trips[existing_trip_id], True

        trip_id = f"trip-{uuid.uuid4().hex[:8]}"
        trip = Trip(
            trip_id=trip_id,
            rider_id=payload.rider_id,
            origin=payload.origin,
            destination=payload.destination,
            passenger_count=payload.passenger_count,
            idempotency_key=payload.idempotency_key,
        )

        self._trips[trip_id] = trip
        self._idempotency_registry[payload.idempotency_key] = trip_id
        return trip, False

    def get(self, trip_id: str) -> Optional[Trip]:
        return self._trips.get(trip_id)

    def save(self, trip: Trip) -> None:
        self._trips[trip.trip_id] = trip

    def create_snapshot(self) -> Dict[str, Any]:
        return {
            "trips": {tid: t.to_dict() for tid, t in self._trips.items()},
            "idempotency_registry": dict(self._idempotency_registry),
        }

    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._trips.clear()
        self._idempotency_registry.clear()
        for tid, t_dict in snapshot.get("trips", {}).items():
            self._trips[tid] = Trip.from_dict(t_dict)
        self._idempotency_registry.update(snapshot.get("idempotency_registry", {}))
