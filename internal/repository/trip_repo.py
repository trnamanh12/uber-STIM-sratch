"""
internal/repository/trip_repo.py - Trip Persistence Contracts & Implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from internal.domain.trip import Trip


class TripRepository(ABC):
    """Abstract interface defining the trip storage boundary."""

    @abstractmethod
    def save(self, trip: Trip) -> None:
        pass

    @abstractmethod
    def get_by_id(self, trip_id: str) -> Optional[Trip]:
        pass

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Optional[Trip]:
        pass

    @abstractmethod
    def create_snapshot(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        pass


class InMemoryTripRepository(TripRepository):
    """In-memory implementation of TripRepository with atomic snapshotting."""

    def __init__(self) -> None:
        self._trips: Dict[str, Trip] = {}
        self._idempotency_registry: Dict[str, str] = {}  # key -> trip_id

    def save(self, trip: Trip) -> None:
        self._trips[trip.trip_id] = trip
        if trip.idempotency_key:
            self._idempotency_registry[trip.idempotency_key] = trip.trip_id

    def get_by_id(self, trip_id: str) -> Optional[Trip]:
        return self._trips.get(trip_id)

    def get_by_idempotency_key(self, key: str) -> Optional[Trip]:
        trip_id = self._idempotency_registry.get(key)
        if trip_id:
            return self._trips.get(trip_id)
        return None

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
