"""
tests/test_service.py - Integration tests for decoupled Application Services and Repositories.
"""

import pytest
from internal.domain.driver import Driver, DriverState
from internal.domain.trip import GeoCoordinate, TripState
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.matching import MatchingService, NoDriverAvailableError
from internal.service.trip_service import TripNotFoundError, TripService


@pytest.fixture
def service_fixture():
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    # Seed drivers
    d1 = Driver("D-FAST", "Le Van Fast", GeoCoordinate(lat=10.7720, lon=106.6980))
    d2 = Driver("D-SLOW", "Tran Van Slow", GeoCoordinate(lat=10.8200, lon=106.7500))
    driver_repo.register(d1)
    driver_repo.register(d2)

    matching_service = MatchingService(driver_repo, default_search_radius_km=10.0)
    trip_service = TripService(trip_repo, driver_repo, matching_service)

    return trip_service, trip_repo, driver_repo, d1, d2


def test_service_complete_trip_lifecycle(service_fixture):
    trip_service, trip_repo, driver_repo, d1, d2 = service_fixture

    origin = GeoCoordinate(lat=10.7760, lon=106.7000)
    destination = GeoCoordinate(lat=10.8000, lon=106.7200)

    # 1. Request trip
    trip, is_dup = trip_service.request_trip(
        idempotency_key="idem-srv-1",
        rider_id="rider-integration",
        origin=origin,
        destination=destination,
        passenger_count=1,
    )
    assert not is_dup
    assert trip.state == TripState.REQUESTED

    # Idempotency re-test via service layer
    trip_dup, is_dup_2 = trip_service.request_trip(
        idempotency_key="idem-srv-1",
        rider_id="rider-integration",
        origin=origin,
        destination=destination,
    )
    assert is_dup_2
    assert trip_dup.trip_id == trip.trip_id

    # 2. Match nearest driver
    trip, matched_driver, eta = trip_service.match_and_assign_driver(trip.trip_id)
    assert matched_driver.driver_id == "D-FAST"
    assert trip.state == TripState.MATCHED
    assert matched_driver.state == DriverState.ASSIGNED

    # 3. Driver arrives
    trip = trip_service.driver_arrived_at_pickup(trip.trip_id)
    assert trip.state == TripState.DRIVER_ARRIVING

    # 4. Start trip (driver marks busy)
    trip = trip_service.start_trip(trip.trip_id)
    assert trip.state == TripState.IN_TRANSIT
    refreshed_d1 = driver_repo.get_by_id("D-FAST")
    assert refreshed_d1.state == DriverState.BUSY

    # 5. Telemetry update
    trip = trip_service.update_telemetry(
        trip_id=trip.trip_id,
        lat=10.7850,
        lon=106.7100,
        distance_delta_km=1.5,
        time_delta_sec=120.0,
    )
    assert trip.distance_km == 1.5
    assert trip.duration_seconds == 120.0
    refreshed_d1 = driver_repo.get_by_id("D-FAST")
    assert refreshed_d1.location.lat == 10.7850

    # 6. Drop off
    trip = trip_service.drop_off_rider(trip.trip_id)
    assert trip.state == TripState.DROPPED_OFF

    # 7. Complete trip (settles fare, releases driver to IDLE)
    trip = trip_service.complete_trip(trip.trip_id)
    assert trip.state == TripState.COMPLETED
    assert trip.fare > 0
    refreshed_d1 = driver_repo.get_by_id("D-FAST")
    assert refreshed_d1.state == DriverState.IDLE


def test_service_cancel_trip_releases_assigned_driver(service_fixture):
    trip_service, trip_repo, driver_repo, d1, d2 = service_fixture

    origin = GeoCoordinate(lat=10.7760, lon=106.7000)
    dest = GeoCoordinate(lat=10.8000, lon=106.7200)

    trip, _ = trip_service.request_trip(
        idempotency_key="idem-cancel-test",
        rider_id="rider-cancel",
        origin=origin,
        destination=dest,
    )
    trip, driver, _ = trip_service.match_and_assign_driver(trip.trip_id)
    assert driver.state == DriverState.ASSIGNED

    # Cancel trip
    trip = trip_service.cancel_trip(trip.trip_id, reason="Rider no longer needs ride")
    assert trip.state == TripState.CANCELLED

    # Driver must be released back to IDLE
    assert driver_repo.get_by_id("D-FAST").state == DriverState.IDLE


def test_service_trip_not_found(service_fixture):
    trip_service, _, _, _, _ = service_fixture
    with pytest.raises(TripNotFoundError):
        trip_service.get_trip("non-existent-id")
