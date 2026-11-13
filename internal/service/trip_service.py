"""
internal/service/trip_service.py - Trip Lifecycle Orchestration Service.
"""

from typing import Optional, Tuple
import uuid
from internal.domain.driver import Driver
from internal.domain.pricing import SurgePricingEngine
from internal.domain.trip import (
    DomainError,
    GeoCoordinate,
    InvariantViolationError,
    Trip,
    TripState,
)
from internal.repository.driver_repo import DriverRepository
from internal.repository.trip_repo import TripRepository
from internal.service.matching import MatchingService


class TripNotFoundError(DomainError):
    """Raised when trip cannot be found by ID."""
    pass


class TripService:
    """
    Application Service: Orchestrates trip use cases, coordinates domain entities,
    and manages persistence transaction boundaries.
    """

    def __init__(
        self,
        trip_repo: TripRepository,
        driver_repo: DriverRepository,
        matching_service: MatchingService,
        pricing_engine: Optional[SurgePricingEngine] = None,
    ) -> None:
        self.trip_repo = trip_repo
        self.driver_repo = driver_repo
        self.matching_service = matching_service
        self.pricing_engine = pricing_engine or SurgePricingEngine()

    def request_trip(
        self,
        idempotency_key: str,
        rider_id: str,
        origin: GeoCoordinate,
        destination: GeoCoordinate,
        passenger_count: int = 1,
    ) -> Tuple[Trip, bool]:
        """
        Use case: Rider requests a trip.
        Guarantees idempotency: returns existing trip if key was already processed.
        """
        # Double Strike check
        existing = self.trip_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing, True

        trip_id = f"trip-{uuid.uuid4().hex[:8]}"
        trip = Trip(
            trip_id=trip_id,
            rider_id=rider_id,
            origin=origin,
            destination=destination,
            passenger_count=passenger_count,
            idempotency_key=idempotency_key,
        )
        self.trip_repo.save(trip)
        return trip, False

    def match_and_assign_driver(
        self, trip_id: str, max_search_radius_km: Optional[float] = None
    ) -> Tuple[Trip, Driver, float]:
        """
        Use case: Matches nearest available driver and binds to trip.
        Guarantees thread-safe atomic assignment via Optimistic Concurrency Control (OCC).
        """
        max_retries = 5
        for _ in range(max_retries):
            trip = self.get_trip(trip_id)
            driver, distance_km, eta_min = self.matching_service.match_driver_for_trip(
                pickup=trip.origin, max_search_radius_km=max_search_radius_km
            )

            expected_version = driver.version
            driver.assign_to_trip(trip.trip_id)

            # Atomic CAS
            if self.driver_repo.atomic_compare_and_swap(driver.driver_id, expected_version, driver):
                trip.assign_driver(driver.driver_id)
                self.trip_repo.save(trip)
                return trip, driver, eta_min

        raise NoDriverAvailableError("Failed to lock driver due to concurrent dispatch contention")

    def driver_arrived_at_pickup(self, trip_id: str) -> Trip:
        """Use case: Driver arrived at pickup location."""
        trip = self.get_trip(trip_id)
        trip.driver_arrived()
        self.trip_repo.save(trip)
        return trip

    def start_trip(self, trip_id: str) -> Trip:
        """Use case: Passenger onboard; trip starts transit."""
        trip = self.get_trip(trip_id)
        driver = self.driver_repo.get_by_id(trip.driver_id) if trip.driver_id else None
        if driver:
            driver.mark_busy()
            self.driver_repo.update(driver)

        trip.start_trip()
        self.trip_repo.save(trip)
        return trip

    def update_telemetry(
        self, trip_id: str, lat: float, lon: float, distance_delta_km: float, time_delta_sec: float
    ) -> Trip:
        """Use case: Ingest vehicle GPS ping and update journey telemetry."""
        trip = self.get_trip(trip_id)
        trip.update_telemetry(lat, lon, distance_delta_km, time_delta_sec)
        
        # Also update driver's current physical position
        if trip.driver_id:
            driver = self.driver_repo.get_by_id(trip.driver_id)
            if driver:
                driver.update_location(GeoCoordinate(lat=lat, lon=lon))
                self.driver_repo.update(driver)

        self.trip_repo.save(trip)
        return trip

    def add_waypoint(self, trip_id: str, waypoint: GeoCoordinate) -> Trip:
        """Use case: Add intermediate detour stop."""
        trip = self.get_trip(trip_id)
        trip.add_waypoint(waypoint)
        self.trip_repo.save(trip)
        return trip

    def reach_waypoint(self, trip_id: str, waypoint_index: int) -> Trip:
        """Use case: Vehicle arrives at detour stop."""
        trip = self.get_trip(trip_id)
        trip.reach_waypoint(waypoint_index)
        self.trip_repo.save(trip)
        return trip

    def drop_off_rider(self, trip_id: str) -> Trip:
        """Use case: Driver drops off rider at destination."""
        trip = self.get_trip(trip_id)
        trip.drop_off()
        self.trip_repo.save(trip)
        return trip

    def complete_trip(self, trip_id: str, surge_multiplier: Optional[float] = None) -> Trip:
        """Use case: Complete trip, settle fare with surge pricing, and release driver back to IDLE."""
        trip = self.get_trip(trip_id)
        multiplier = surge_multiplier if surge_multiplier is not None else 1.0
        final_fare = self.pricing_engine.calculate_fare(
            distance_km=trip.distance_km,
            duration_seconds=trip.duration_seconds,
            surge_multiplier=multiplier,
        )
        trip.complete_trip(final_fare)

        if trip.driver_id:
            driver = self.driver_repo.get_by_id(trip.driver_id)
            if driver:
                driver.release()
                self.driver_repo.update(driver)

        self.trip_repo.save(trip)
        return trip

    def cancel_trip(self, trip_id: str, reason: str) -> Trip:
        """Use case: Cancel trip and release driver if assigned."""
        trip = self.get_trip(trip_id)
        if trip.driver_id:
            driver = self.driver_repo.get_by_id(trip.driver_id)
            if driver:
                driver.release()
                self.driver_repo.update(driver)

        trip.cancel(reason)
        self.trip_repo.save(trip)
        return trip

    def get_trip(self, trip_id: str) -> Trip:
        trip = self.trip_repo.get_by_id(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip not found: {trip_id}")
        return trip
