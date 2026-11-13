"""
test_core.py - Unit tests for Milestone 3: Hardening Against the 4 Fatal Questions.
"""

import math
import pytest
from core import (
    DomainEvent,
    GeoCoordinate,
    IllegalStateTransitionError,
    InMemoryTripRepository,
    InvariantViolationError,
    PoisonPayloadError,
    Trip,
    TripRequestPayload,
    TripState,
)


# ==============================================================================
# Q1: THE POISON PILL TESTS
# ==============================================================================

def test_poison_pill_rejects_nan_and_inf():
    with pytest.raises(PoisonPayloadError, match="NaN or Inf"):
        GeoCoordinate(lat=float("nan"), lon=106.7)

    with pytest.raises(PoisonPayloadError, match="NaN or Inf"):
        GeoCoordinate(lat=10.7, lon=float("inf"))


def test_poison_pill_rejects_out_of_bounds_coordinates():
    with pytest.raises(PoisonPayloadError, match="Latitude out of bounds"):
        GeoCoordinate(lat=91.0, lon=10.0)

    with pytest.raises(PoisonPayloadError, match="Latitude out of bounds"):
        GeoCoordinate(lat=-90.5, lon=10.0)

    with pytest.raises(PoisonPayloadError, match="Longitude out of bounds"):
        GeoCoordinate(lat=10.0, lon=180.1)

    with pytest.raises(PoisonPayloadError, match="Longitude out of bounds"):
        GeoCoordinate(lat=10.0, lon=-185.0)


def test_poison_pill_rejects_invalid_passenger_count():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.78, lon=106.70)

    for bad_count in [0, -1, 7, 100]:
        with pytest.raises(PoisonPayloadError, match="Passenger count must be an integer between 1 and 6"):
            TripRequestPayload(
                idempotency_key="key-1",
                rider_id="rider-1",
                origin=origin,
                destination=dest,
                passenger_count=bad_count,
            )


def test_poison_pill_rejects_identical_origin_and_destination():
    coord = GeoCoordinate(lat=10.76, lon=106.66)
    with pytest.raises(PoisonPayloadError, match="Origin and Destination coordinates cannot be identical"):
        TripRequestPayload(
            idempotency_key="key-2",
            rider_id="rider-1",
            origin=coord,
            destination=coord,
            passenger_count=1,
        )


def test_poison_pill_rejects_empty_ids():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.78, lon=106.70)

    with pytest.raises(PoisonPayloadError, match="Idempotency key cannot be empty"):
        TripRequestPayload(
            idempotency_key="   ",
            rider_id="rider-1",
            origin=origin,
            destination=dest,
        )

    with pytest.raises(PoisonPayloadError, match="Rider ID cannot be empty"):
        TripRequestPayload(
            idempotency_key="key-valid",
            rider_id="   ",
            origin=origin,
            destination=dest,
        )


# ==============================================================================
# Q2: THE SUDDEN DEATH (CRASH RECOVERY) TESTS
# ==============================================================================

def test_sudden_death_snapshot_and_recovery():
    repo = InMemoryTripRepository()
    payload = TripRequestPayload(
        idempotency_key="idem-crash-test",
        rider_id="rider-resilient",
        origin=GeoCoordinate(lat=10.76, lon=106.66),
        destination=GeoCoordinate(lat=10.80, lon=106.70),
        passenger_count=2,
    )
    trip, is_dup = repo.request_trip_idempotent(payload)
    assert not is_dup

    # Progress trip
    trip.assign_driver("driver-99")
    trip.driver_arrived()
    trip.start_trip()
    trip.update_telemetry(lat=10.78, lon=106.68, distance_delta_km=2.5, time_delta_sec=120.0)

    # Simulate snapshot write to disk/WAL
    snapshot = repo.create_snapshot()

    # Simulate Sudden Death (process killed, memory wiped)
    recovered_repo = InMemoryTripRepository()
    recovered_repo.restore_from_snapshot(snapshot)

    recovered_trip = recovered_repo.get(trip.trip_id)
    assert recovered_trip is not None
    assert recovered_trip.trip_id == trip.trip_id
    assert recovered_trip.rider_id == "rider-resilient"
    assert recovered_trip.driver_id == "driver-99"
    assert recovered_trip.state == TripState.IN_TRANSIT
    assert recovered_trip.current_lat == 10.78
    assert recovered_trip.current_lon == 106.68
    assert recovered_trip.distance_km == 2.5
    assert recovered_trip.duration_seconds == 120.0
    assert len(recovered_trip.events) == len(trip.events)

    # Continue trip from restored state
    recovered_trip.drop_off()
    recovered_trip.complete_trip(15.0)
    assert recovered_trip.state == TripState.COMPLETED


# ==============================================================================
# Q3: THE DOUBLE STRIKE (IDEMPOTENCY) TESTS
# ==============================================================================

def test_double_strike_idempotent_deduplication():
    repo = InMemoryTripRepository()
    payload = TripRequestPayload(
        idempotency_key="network-retry-token-888",
        rider_id="rider-alice",
        origin=GeoCoordinate(lat=10.76, lon=106.66),
        destination=GeoCoordinate(lat=10.80, lon=106.70),
        passenger_count=1,
    )

    # Strike 1: Initial trip request
    trip_1, is_dup_1 = repo.request_trip_idempotent(payload)
    assert not is_dup_1
    assert trip_1.state == TripState.REQUESTED

    # Strike 2: Network retry storm with identical key
    trip_2, is_dup_2 = repo.request_trip_idempotent(payload)
    assert is_dup_2
    assert trip_2.trip_id == trip_1.trip_id

    # Strike 3: Another retry
    trip_3, is_dup_3 = repo.request_trip_idempotent(payload)
    assert is_dup_3
    assert trip_3.trip_id == trip_1.trip_id


# ==============================================================================
# Q4: THE SILENT BLEED (OBSERVABILITY & INVARIANTS) TESTS
# ==============================================================================

def test_silent_bleed_structured_event_stream():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.80, lon=106.70)
    trip = Trip(trip_id="T-SILENT", rider_id="R-SILENT", origin=origin, destination=dest)

    trip.assign_driver("D-1")
    trip.driver_arrived()
    trip.start_trip()
    trip.update_telemetry(lat=10.78, lon=106.68, distance_delta_km=1.2, time_delta_sec=60.0)
    trip.drop_off()
    trip.complete_trip(8.50)

    # Verify structured event ledger
    event_types = [e.event_type for e in trip.events]
    assert event_types == [
        "TRIP_CREATED",
        "STATE_TRANSITIONED",  # MATCHED
        "STATE_TRANSITIONED",  # DRIVER_ARRIVING
        "STATE_TRANSITIONED",  # IN_TRANSIT
        "TELEMETRY_UPDATED",
        "STATE_TRANSITIONED",  # DROPPED_OFF
        "STATE_TRANSITIONED",  # COMPLETED
    ]

    # Verify all events share the exact correlation_id
    for event in trip.events:
        assert event.correlation_id == trip.trip_id
        assert event.timestamp > 0
        assert isinstance(event.payload, dict)


def test_silent_bleed_rejects_negative_delta_and_poison_telemetry():
    origin = GeoCoordinate(lat=10.76, lon=106.66)
    dest = GeoCoordinate(lat=10.80, lon=106.70)
    trip = Trip(trip_id="T-EDGE", rider_id="R-EDGE", origin=origin, destination=dest)
    trip.assign_driver("D-1")
    trip.driver_arrived()
    trip.start_trip()

    # Reject negative distance delta
    with pytest.raises(InvariantViolationError, match="Distance delta cannot be negative"):
        trip.update_telemetry(lat=10.77, lon=106.67, distance_delta_km=-0.5, time_delta_sec=10.0)

    # Reject negative time delta
    with pytest.raises(InvariantViolationError, match="Time delta cannot be negative"):
        trip.update_telemetry(lat=10.77, lon=106.67, distance_delta_km=0.5, time_delta_sec=-5.0)

    # Reject NaN coordinate inside telemetry update
    with pytest.raises(PoisonPayloadError, match="NaN or Inf"):
        trip.update_telemetry(lat=float("nan"), lon=106.67, distance_delta_km=0.5, time_delta_sec=10.0)
