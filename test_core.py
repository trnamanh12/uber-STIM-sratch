"""
test_core.py - Domain core unit tests asserting state machines, invariants, and failure protections.
"""

import math
import pytest
from core import (
    DomainError,
    DomainEvent,
    Driver,
    DriverState,
    GeoCoordinate,
    IllegalStateTransitionError,
    InMemoryDriverRepository,
    InMemoryTripRepository,
    InvariantViolationError,
    MatchingService,
    NoDriverAvailableError,
    PoisonPayloadError,
    Trip,
    TripState,
    haversine_distance_km,
)


def test_domain_state_transitions():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.80, lon=106.70)
    trip = Trip("T-DOMAIN", "R-1", origin=origin, destination=dest)

    assert trip.state == TripState.REQUESTED
    trip.assign_driver("D-1")
    assert trip.state == TripState.MATCHED
    trip.driver_arrived()
    assert trip.state == TripState.DRIVER_ARRIVING
    trip.start_trip()
    assert trip.state == TripState.IN_TRANSIT
    trip.update_telemetry(lat=10.78, lon=106.68, distance_delta_km=2.0, time_delta_sec=100.0)
    trip.drop_off()
    assert trip.state == TripState.DROPPED_OFF
    trip.complete_trip(10.0)
    assert trip.state == TripState.COMPLETED

    # Terminal lock check
    with pytest.raises(IllegalStateTransitionError):
        trip.transition_to(TripState.REQUESTED)


def test_domain_invariants_destination_locked():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.80, lon=106.70)
    trip = Trip("T-INV", "R-1", origin=origin, destination=dest)

    with pytest.raises(AttributeError):
        trip.destination = GeoCoordinate(lat=10.90, lon=106.90)  # type: ignore


def test_domain_poison_coordinate_rejection():
    with pytest.raises(PoisonPayloadError):
        GeoCoordinate(lat=float("nan"), lon=106.0)

    with pytest.raises(PoisonPayloadError):
        GeoCoordinate(lat=10.0, lon=190.0)


def test_domain_haversine_accuracy():
    p1 = GeoCoordinate(lat=10.7725, lon=106.6980)
    p2 = GeoCoordinate(lat=10.7798, lon=106.6990)
    dist = haversine_distance_km(p1, p2)
    assert 0.7 <= dist <= 1.2


def test_matching_service_with_repository():
    driver_repo = InMemoryDriverRepository()
    d1 = Driver("D1", "Driver 1", GeoCoordinate(lat=10.7740, lon=106.7020))
    d2 = Driver("D2", "Driver 2", GeoCoordinate(lat=10.8500, lon=106.7800))
    driver_repo.register(d1)
    driver_repo.register(d2)

    matcher = MatchingService(driver_repo, default_search_radius_km=10.0)
    matched, dist, eta = matcher.match_driver_for_trip(GeoCoordinate(lat=10.7700, lon=106.7000))
    assert matched.driver_id == "D1"
    assert dist < 1.0
