"""
test_core.py - Exhaustive unit tests for Trip state machine and domain invariants.
"""

import pytest
from core import (
    Trip,
    TripState,
    IllegalStateTransitionError,
    InvariantViolationError,
)


def test_trip_happy_path_lifecycle():
    trip = Trip(trip_id="T1", rider_id="R1", origin=0.0, destination=100.0)
    assert trip.state == TripState.REQUESTED
    assert trip.destination == 100.0

    # 1. Match
    trip.assign_driver("D1")
    assert trip.state == TripState.MATCHED
    assert trip.driver_id == "D1"

    # 2. Arriving
    trip.driver_arrived()
    assert trip.state == TripState.DRIVER_ARRIVING

    # 3. In Transit
    trip.start_trip()
    assert trip.state == TripState.IN_TRANSIT

    # 4. Telemetry update
    trip.update_telemetry(position=50.0, time_delta=10.0)
    assert trip.current_position == 50.0
    assert trip.distance == 50.0
    assert trip.duration_seconds == 10.0

    trip.update_telemetry(position=100.0, time_delta=15.0)
    assert trip.current_position == 100.0
    assert trip.distance == 100.0
    assert trip.duration_seconds == 25.0

    # 5. Dropped off
    trip.drop_off()
    assert trip.state == TripState.DROPPED_OFF

    # 6. Complete
    trip.complete_trip(final_fare=18.50)
    assert trip.state == TripState.COMPLETED
    assert trip.fare == 18.50


def test_invariant_a_destination_integrity():
    trip = Trip(trip_id="T2", rider_id="R2", origin=0.0, destination=100.0)
    # destination property has no setter
    with pytest.raises(AttributeError):
        trip.destination = 200.0  # type: ignore

    # Attempting to construct with destination <= origin
    with pytest.raises(InvariantViolationError, match="must be strictly greater than origin"):
        Trip(trip_id="T2", rider_id="R2", origin=100.0, destination=50.0)


def test_invariant_b_terminal_lock_on_completed():
    trip = Trip(trip_id="T3", rider_id="R3", origin=0.0, destination=10.0)
    trip.assign_driver("D3")
    trip.driver_arrived()
    trip.start_trip()
    trip.update_telemetry(position=10.0, time_delta=5.0)
    trip.drop_off()
    trip.complete_trip(final_fare=5.0)
    assert trip.state == TripState.COMPLETED

    # Invariant B: Cannot transition out of COMPLETED
    for target in TripState:
        with pytest.raises(IllegalStateTransitionError):
            trip.transition_to(target)


def test_invariant_b_terminal_lock_on_cancelled():
    trip = Trip(trip_id="T4", rider_id="R4", origin=0.0, destination=50.0)
    trip.cancel("Rider changed plans")
    assert trip.state == TripState.CANCELLED

    # Invariant B: Cannot transition out of CANCELLED
    for target in TripState:
        with pytest.raises(IllegalStateTransitionError):
            trip.transition_to(target)


def test_invariant_c_non_negative_metrics():
    trip = Trip(trip_id="T5", rider_id="R5", origin=0.0, destination=100.0)
    trip.assign_driver("D5")
    trip.driver_arrived()
    trip.start_trip()

    # Backwards movement rejected
    trip.update_telemetry(position=40.0, time_delta=5.0)
    with pytest.raises(InvariantViolationError, match="cannot move backwards"):
        trip.update_telemetry(position=30.0, time_delta=5.0)

    # Negative time delta rejected
    with pytest.raises(InvariantViolationError, match="cannot be negative"):
        trip.update_telemetry(position=60.0, time_delta=-1.0)

    # Negative fare rejected
    trip.update_telemetry(position=100.0, time_delta=10.0)
    trip.drop_off()
    with pytest.raises(InvariantViolationError, match="non-negative"):
        trip.complete_trip(final_fare=-10.0)


def test_illegal_state_skips():
    trip = Trip(trip_id="T6", rider_id="R6", origin=0.0, destination=100.0)
    
    # Cannot jump straight from REQUESTED to IN_TRANSIT
    with pytest.raises(IllegalStateTransitionError):
        trip.start_trip()

    # Cannot jump straight from REQUESTED to COMPLETED
    with pytest.raises(IllegalStateTransitionError):
        trip.complete_trip(20.0)

    # Cannot drop off before reaching destination
    trip.assign_driver("D6")
    trip.driver_arrived()
    trip.start_trip()
    trip.update_telemetry(position=50.0, time_delta=5.0)
    with pytest.raises(InvariantViolationError, match="Cannot drop off rider before reaching destination"):
        trip.drop_off()


def test_cancellation_from_active_states():
    # Cancellation allowed from REQUESTED, MATCHED, DRIVER_ARRIVING, IN_TRANSIT
    for state_seq in [
        lambda t: None,
        lambda t: t.assign_driver("D"),
        lambda t: (t.assign_driver("D"), t.driver_arrived()),
        lambda t: (t.assign_driver("D"), t.driver_arrived(), t.start_trip()),
    ]:
        t = Trip(trip_id="TC", rider_id="RC", origin=0.0, destination=100.0)
        state_seq(t)
        t.cancel("Test cancellation")
        assert t.state == TripState.CANCELLED


def test_simulated_trip_execution():
    trip = Trip(trip_id="TSIM", rider_id="RSIM", origin=0.0, destination=100.0)
    snapshots = list(trip.run_simulated_trip(driver_id="DSIM", step_size=25.0, time_step_sec=5.0))

    assert len(snapshots) >= 7
    assert snapshots[0]["state"] == "MATCHED"
    assert snapshots[1]["state"] == "DRIVER_ARRIVING"
    assert snapshots[2]["state"] == "IN_TRANSIT"
    assert snapshots[-2]["state"] == "DROPPED_OFF"
    assert snapshots[-1]["state"] == "COMPLETED"
    assert snapshots[-1]["fare"] > 0
    assert trip.state == TripState.COMPLETED
