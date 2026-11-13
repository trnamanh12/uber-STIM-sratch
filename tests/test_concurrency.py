"""
tests/test_concurrency.py - Concurrency & Atomic Dispatch Lock Tests (TDD).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pytest
from internal.domain.driver import Driver, DriverState
from internal.domain.trip import DomainError, GeoCoordinate, Trip
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.matching import MatchingService, NoDriverAvailableError
from internal.service.trip_service import TripService


def test_driver_version_increments_on_mutation():
    loc = GeoCoordinate(lat=10.7720, lon=106.6980)
    driver = Driver("D-OCC-1", "Nguyen Van A", loc)
    initial_version = driver.version
    assert initial_version == 1

    driver.assign_to_trip("trip-101")
    assert driver.state == DriverState.ASSIGNED
    assert driver.version == initial_version + 1


def test_atomic_compare_and_swap_version_mismatch():
    repo = InMemoryDriverRepository()
    loc = GeoCoordinate(lat=10.7720, lon=106.6980)
    driver = Driver("D-CAS-1", "Tran Van B", loc)
    repo.register(driver)

    # Correct expected version -> CAS succeeds
    driver.assign_to_trip("trip-202")
    success = repo.atomic_compare_and_swap(
        driver_id="D-CAS-1",
        expected_version=1,
        updated_driver=driver,
    )
    assert success is True
    assert repo.get_by_id("D-CAS-1").version == 2

    # Stale expected version -> CAS fails!
    stale_driver = Driver("D-CAS-1", "Tran Van B", loc)
    stale_driver.assign_to_trip("trip-303")
    stale_success = repo.atomic_compare_and_swap(
        driver_id="D-CAS-1",
        expected_version=1,  # Version in repo is now 2!
        updated_driver=stale_driver,
    )
    assert stale_success is False
    # State must remain from the first successful mutation
    assert repo.get_by_id("D-CAS-1").assigned_trip_id == "trip-202"


def test_concurrent_dispatch_race_prevents_double_booking():
    """
    CRITICAL RACE CONDITION TEST:
    10 concurrent threads attempt to match the EXACT SAME single idle driver simultaneously.
    INVARIANT: Exactly 1 thread must succeed. The other 9 must fail with NoDriverAvailableError.
    The driver must NEVER be double-booked.
    """
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    # Only ONE driver exists in the entire city
    lone_driver = Driver("D-LONE", "The Only Driver", GeoCoordinate(lat=10.7760, lon=106.7000))
    driver_repo.register(lone_driver)

    matching_service = MatchingService(driver_repo, default_search_radius_km=10.0)
    trip_service = TripService(trip_repo, driver_repo, matching_service)

    # 10 riders create trips at the same time
    num_riders = 10
    trip_ids = []
    for i in range(num_riders):
        t, _ = trip_service.request_trip(
            idempotency_key=f"race-key-{i}",
            rider_id=f"rider-race-{i}",
            origin=GeoCoordinate(lat=10.7760 + i * 0.0001, lon=106.7000),
            destination=GeoCoordinate(lat=10.8000, lon=106.7200),
        )
        trip_ids.append(t.trip_id)

    successful_matches = []
    failed_matches = []
    lock = threading.Lock()

    def attempt_match(t_id: str):
        try:
            matched_trip, matched_driver, eta = trip_service.match_and_assign_driver(t_id)
            with lock:
                successful_matches.append((t_id, matched_driver.driver_id))
        except NoDriverAvailableError as exc:
            with lock:
                failed_matches.append((t_id, str(exc)))

    # Execute all 10 matching attempts in parallel
    with ThreadPoolExecutor(max_workers=num_riders) as executor:
        futures = [executor.submit(attempt_match, t_id) for t_id in trip_ids]
        for f in as_completed(futures):
            f.result()

    # INVARIANT VERIFICATION:
    # 1. Exactly 1 rider was matched
    assert len(successful_matches) == 1, f"Expected 1 winner, got {len(successful_matches)}!"
    # 2. Exactly 9 riders failed because the driver was atomically locked
    assert len(failed_matches) == num_riders - 1
    # 3. The driver state in repository is ASSIGNED to the single winner
    winner_trip_id, winner_driver_id = successful_matches[0]
    final_driver = driver_repo.get_by_id("D-LONE")
    assert final_driver.state == DriverState.ASSIGNED
    assert final_driver.assigned_trip_id == winner_trip_id
    assert final_driver.version > 1
