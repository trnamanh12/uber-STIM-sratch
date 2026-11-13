"""
test_core.py - Unit tests for the 15-Minute Walking Skeleton trip loop.
"""

import pytest
from core import WalkingSkeletonTrip


def test_walking_skeleton_reaches_destination():
    trip = WalkingSkeletonTrip(
        trip_id="trip-001",
        rider_id="rider-abc",
        origin=0.0,
        destination=100.0,
        step_size=20.0,
    )
    ticks = list(trip.run_simulation())

    assert len(ticks) == 6  # tick 0 (pos 0), tick 1 (20), 2 (40), 3 (60), 4 (80), 5 (100)
    assert ticks[0]["state"] == "IN_TRANSIT"
    assert ticks[0]["position"] == 0.0
    assert ticks[-1]["state"] == "COMPLETED"
    assert ticks[-1]["position"] == 100.0
    assert ticks[-1]["remaining"] == 0.0
    assert trip.state == "COMPLETED"


def test_walking_skeleton_monotonic_progress():
    trip = WalkingSkeletonTrip(
        trip_id="trip-002",
        rider_id="rider-xyz",
        origin=10.0,
        destination=50.0,
        step_size=15.0,
    )
    positions = [tick["position"] for tick in trip.run_simulation()]

    # Assert strictly non-decreasing positions
    assert positions == sorted(positions)
    assert positions[-1] == 50.0
    assert trip.current_x == 50.0


def test_walking_skeleton_rejects_invalid_bounds():
    with pytest.raises(
        ValueError, match="Destination must be strictly greater than origin"
    ):
        WalkingSkeletonTrip(
            trip_id="trip-003",
            rider_id="rider-bad",
            origin=100.0,
            destination=50.0,
        )


def test_walking_skeleton_rejects_non_positive_step():
    with pytest.raises(ValueError, match="Step size must be strictly positive"):
        WalkingSkeletonTrip(
            trip_id="trip-004",
            rider_id="rider-bad",
            origin=0.0,
            destination=50.0,
            step_size=0.0,
        )
