"""
internal/domain/trip.py - Core Trip Domain Aggregate, States, Invariants & Events.

Zero external framework dependencies. Pure domain logic.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import math
import time
from typing import Any, Dict, List, Optional, Set
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


class TripState(str, Enum):
    """Explicit lifecycle states for a mobility trip."""
    REQUESTED = "REQUESTED"
    MATCHED = "MATCHED"
    DRIVER_ARRIVING = "DRIVER_ARRIVING"
    IN_TRANSIT = "IN_TRANSIT"
    DROPPED_OFF = "DROPPED_OFF"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


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
    Geospatial coordinate value object.
    Enforces strict range validation and rejects NaN / Inf.
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


@dataclass(frozen=True)
class DomainEvent:
    """Structured domain event with correlation ID."""
    event_id: str
    correlation_id: str
    event_type: str
    timestamp: float
    payload: Dict[str, Any]


class Trip:
    """
    Trip Aggregate Root.
    Guarantees domain invariants across all state mutations.
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
        if not (1 <= passenger_count <= 6):
            raise InvariantViolationError(f"Invalid passenger count: {passenger_count}")

        self.trip_id = trip_id
        self.rider_id = rider_id
        self.origin = origin
        
        # Invariant A: Destination Integrity (destination locked)
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

        # Q4 Observability: Structured Event Ledger
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
