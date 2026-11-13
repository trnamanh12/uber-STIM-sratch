"""
test_core.py - Unit tests for Milestone 4: Spatial Driver Matching & Dispatch Algorithm.
"""

import math
import pytest
from core import (
    DispatchEngine,
    DomainEvent,
    Driver,
    DriverPool,
    DriverState,
    GeoCoordinate,
    IllegalStateTransitionError,
    InMemoryTripRepository,
    InvariantViolationError,
    NoDriverAvailableError,
    PoisonPayloadError,
    Trip,
    TripRequestPayload,
    TripState,
    haversine_distance_km,
)


# ==============================================================================
# HAVERSINE DISTANCE ACCURACY TESTS
# ==============================================================================

def test_haversine_zero_distance_for_same_point():
    p = GeoCoordinate(lat=10.762622, lon=106.660172)
    assert haversine_distance_km(p, p) == 0.0


def test_haversine_known_geographic_distance():
    # Ho Chi Minh City (Ben Thanh Market) to (Notre Dame Cathedral) ~ 1.1 km
    ben_thanh = GeoCoordinate(lat=10.7725, lon=106.6980)
    notre_dame = GeoCoordinate(lat=10.7798, lon=106.6990)
    dist = haversine_distance_km(ben_thanh, notre_dame)
    assert 0.7 <= dist <= 1.2


# ==============================================================================
# DRIVER POOL & STATE TESTS
# ==============================================================================

def test_driver_lifecycle_and_assignment_invariants():
    loc = GeoCoordinate(lat=10.76, lon=106.66)
    driver = Driver(driver_id="D-1", name="Nguyen Van A", location=loc)
    assert driver.state == DriverState.IDLE

    # Assign to trip
    driver.assign_to_trip("trip-100")
    assert driver.state == DriverState.ASSIGNED
    assert driver.assigned_trip_id == "trip-100"

    # Cannot assign an already assigned driver
    with pytest.raises(IllegalStateTransitionError, match="cannot be assigned"):
        driver.assign_to_trip("trip-101")

    # Release back to IDLE
    driver.release()
    assert driver.state == DriverState.IDLE
    assert driver.assigned_trip_id is None


# ==============================================================================
# SPATIAL DISPATCH ENGINE MATCHING TESTS
# ==============================================================================

def test_dispatch_engine_selects_nearest_available_driver():
    """
    Scenario:
    Rider pickup at (10.770, 106.700).
    Driver 1: 0.5 km away (IDLE)
    Driver 2: 2.1 km away (IDLE)
    Driver 3: 5.4 km away (IDLE)
    Assert Driver 1 is selected.
    """
    pickup = GeoCoordinate(lat=10.7700, lon=106.7000)
    pool = DriverPool()

    d1 = Driver("D-CLOSE", "Fast Driver", GeoCoordinate(lat=10.7740, lon=106.7020))
    d2 = Driver("D-MID", "Medium Driver", GeoCoordinate(lat=10.7850, lon=106.7100))
    d3 = Driver("D-FAR", "Far Driver", GeoCoordinate(lat=10.8100, lon=106.7400))

    pool.register_driver(d1)
    pool.register_driver(d2)
    pool.register_driver(d3)

    dispatcher = DispatchEngine(pool, default_search_radius_km=10.0)
    matched_driver, dist, eta = dispatcher.match_nearest_driver(pickup)

    assert matched_driver.driver_id == "D-CLOSE"
    assert dist < 1.0
    assert eta >= 1.0


def test_dispatch_skips_busy_driver_for_next_nearest():
    """
    Driver 1 is closest (0.5 km) but BUSY.
    Driver 2 is next closest (2.1 km) and IDLE.
    Assert Driver 2 is selected.
    """
    pickup = GeoCoordinate(lat=10.7700, lon=106.7000)
    pool = DriverPool()

    d1 = Driver("D-BUSY", "Busy Driver", GeoCoordinate(lat=10.7740, lon=106.7020))
    d1.mark_busy()  # Driver is busy with another ride
    d2 = Driver("D-AVAILABLE", "Available Driver", GeoCoordinate(lat=10.7850, lon=106.7100))

    pool.register_driver(d1)
    pool.register_driver(d2)

    dispatcher = DispatchEngine(pool, default_search_radius_km=10.0)
    matched_driver, dist, eta = dispatcher.match_nearest_driver(pickup)

    assert matched_driver.driver_id == "D-AVAILABLE"


def test_dispatch_graceful_backoff_when_no_driver_in_radius():
    pickup = GeoCoordinate(lat=10.7700, lon=106.7000)
    pool = DriverPool()

    # Driver is 25 km away
    d_far = Driver("D-VERY-FAR", "Remote Driver", GeoCoordinate(lat=10.9500, lon=106.9000))
    pool.register_driver(d_far)

    dispatcher = DispatchEngine(pool, default_search_radius_km=5.0)

    with pytest.raises(NoDriverAvailableError, match="No idle drivers found within search radius"):
        dispatcher.match_nearest_driver(pickup, max_search_radius_km=5.0)


def test_dispatch_raises_when_fleet_empty():
    pickup = GeoCoordinate(lat=10.7700, lon=106.7000)
    pool = DriverPool()
    dispatcher = DispatchEngine(pool)

    with pytest.raises(NoDriverAvailableError, match="No available idle drivers found in fleet"):
        dispatcher.match_nearest_driver(pickup)
