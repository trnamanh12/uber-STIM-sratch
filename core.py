"""
core.py - High-Level Facade re-exporting decoupled domain, repository, and service boundaries.
"""

from internal.domain.trip import (
    DomainError,
    IllegalStateTransitionError,
    InvariantViolationError,
    PoisonPayloadError,
    TripState,
    GeoCoordinate,
    DomainEvent,
    Trip,
    ALLOWED_TRANSITIONS,
)
from internal.domain.driver import (
    DriverState,
    Driver,
    haversine_distance_km,
)
from internal.repository.driver_repo import (
    DriverRepository,
    InMemoryDriverRepository,
)
from internal.repository.trip_repo import (
    TripRepository,
    InMemoryTripRepository,
)
from internal.service.matching import (
    MatchingService,
    NoDriverAvailableError,
)
from internal.service.trip_service import (
    TripService,
    TripNotFoundError,
)

__all__ = [
    "DomainError",
    "IllegalStateTransitionError",
    "InvariantViolationError",
    "PoisonPayloadError",
    "TripState",
    "GeoCoordinate",
    "DomainEvent",
    "Trip",
    "ALLOWED_TRANSITIONS",
    "DriverState",
    "Driver",
    "haversine_distance_km",
    "DriverRepository",
    "InMemoryDriverRepository",
    "TripRepository",
    "InMemoryTripRepository",
    "MatchingService",
    "NoDriverAvailableError",
    "TripService",
    "TripNotFoundError",
]
