"""
core.py - Domain State Machine & Safety Invariants

Enforces:
1. Formal Trip Lifecycle State Machine
2. Invariant A: Destination Integrity (destination is locked upon instantiation)
3. Invariant B: Terminal Lock (COMPLETED and CANCELLED states are strictly final)
4. Invariant C: Non-Negative Metrics (distance, duration, fare >= 0)
"""

from enum import Enum
from typing import Any, Dict, Generator, Optional, Set


class DomainError(Exception):
    """Base exception for all domain logic violations."""
    pass


class IllegalStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    pass


class InvariantViolationError(DomainError):
    """Raised when a core system invariant is broken."""
    pass


class TripState(str, Enum):
    """Explicit lifecycle states for a mobility trip."""
    REQUESTED = "REQUESTED"
    MATCHED = "MATCHED"
    DRIVER_ARRIVING = "DRIVER_ARRIVING"
    IN_TRANSIT = "IN_TRANSIT"
    DROPPED_OFF = "DROPPED_OFF"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# Invariant B enforcement: Allowed transition graph.
# Terminal states (COMPLETED, CANCELLED) have empty allowed sets.
ALLOWED_TRANSITIONS: Dict[TripState, Set[TripState]] = {
    TripState.REQUESTED: {TripState.MATCHED, TripState.CANCELLED},
    TripState.MATCHED: {TripState.DRIVER_ARRIVING, TripState.CANCELLED},
    TripState.DRIVER_ARRIVING: {TripState.IN_TRANSIT, TripState.CANCELLED},
    TripState.IN_TRANSIT: {TripState.DROPPED_OFF, TripState.CANCELLED},
    TripState.DROPPED_OFF: {TripState.COMPLETED},
    TripState.COMPLETED: set(),  # Terminal Lock
    TripState.CANCELLED: set(),  # Terminal Lock
}


class Trip:
    """
    Trip Aggregate Root.
    Guarantees domain invariants across all state mutations.
    """

    def __init__(
        self,
        trip_id: str,
        rider_id: str,
        origin: float = 0.0,
        destination: float = 100.0,
    ) -> None:
        if not trip_id:
            raise InvariantViolationError("Trip ID cannot be empty")
        if not rider_id:
            raise InvariantViolationError("Rider ID cannot be empty")
        if destination <= origin:
            raise InvariantViolationError(
                f"Destination ({destination}) must be strictly greater than origin ({origin})"
            )

        self.trip_id = trip_id
        self.rider_id = rider_id
        self.origin = origin

        # Invariant A: Destination Integrity
        self._locked_destination: float = destination

        self.driver_id: Optional[str] = None
        self.current_position: float = origin
        self.state: TripState = TripState.REQUESTED

        # Invariant C: Non-negative metrics
        self.distance: float = 0.0
        self.duration_seconds: float = 0.0
        self.fare: float = 0.0
        self.cancel_reason: Optional[str] = None

        self._verify_invariants()

    @property
    def destination(self) -> float:
        """Destination is immutable once locked."""
        return self._locked_destination

    def _verify_invariants(self) -> None:
        """Enforce domain invariants."""
        # Invariant A: Destination Integrity
        if self._locked_destination <= self.origin:
            raise InvariantViolationError("Destination mutated below origin!")

        # Invariant C: Non-Negative Metrics
        if self.distance < 0.0:
            raise InvariantViolationError(f"Negative distance violation: {self.distance}")
        if self.duration_seconds < 0.0:
            raise InvariantViolationError(f"Negative duration violation: {self.duration_seconds}")
        if self.fare < 0.0:
            raise InvariantViolationError(f"Negative fare violation: {self.fare}")

    def transition_to(self, target_state: TripState) -> None:
        """
        Transition trip to a new lifecycle state.
        Validates transition legality and invariants before and after.
        """
        self._verify_invariants()

        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if target_state not in allowed:
            raise IllegalStateTransitionError(
                f"Illegal transition: Cannot transition from {self.state.value} to {target_state.value}. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )

        self.state = target_state
        self._verify_invariants()

    def assign_driver(self, driver_id: str) -> None:
        """Assign driver and transition to MATCHED."""
        if not driver_id:
            raise InvariantViolationError("Cannot assign empty driver ID")
        self.driver_id = driver_id
        self.transition_to(TripState.MATCHED)

    def driver_arrived(self) -> None:
        """Signal that driver has arrived at pickup."""
        if not self.driver_id:
            raise InvariantViolationError("Cannot arrive without an assigned driver")
        self.transition_to(TripState.DRIVER_ARRIVING)

    def start_trip(self) -> None:
        """Rider picked up; trip is in transit."""
        self.transition_to(TripState.IN_TRANSIT)

    def update_telemetry(self, position: float, time_delta: float) -> None:
        """Update vehicle position and progress during transit."""
        if self.state != TripState.IN_TRANSIT:
            raise IllegalStateTransitionError(
                f"Cannot update transit telemetry while trip is in state {self.state.value}"
            )
        if time_delta < 0:
            raise InvariantViolationError("Time delta cannot be negative")
        if position < self.current_position:
            raise InvariantViolationError("Vehicle position cannot move backwards")

        added_distance = position - self.current_position
        self.current_position = min(self.destination, position)
        self.distance += added_distance
        self.duration_seconds += time_delta
        self._verify_invariants()

    def drop_off(self) -> None:
        """Vehicle reached destination; drop off rider."""
        if self.current_position < self.destination:
            raise InvariantViolationError(
                f"Cannot drop off rider before reaching destination: {self.current_position} < {self.destination}"
            )
        self.transition_to(TripState.DROPPED_OFF)

    def complete_trip(self, final_fare: float) -> None:
        """Finalize trip and apply final fare calculation."""
        if final_fare < 0.0:
            raise InvariantViolationError("Final fare must be non-negative")
        self.fare = final_fare
        self.transition_to(TripState.COMPLETED)

    def cancel(self, reason: str) -> None:
        """Cancel trip with reason if not in terminal state."""
        if not reason:
            raise InvariantViolationError("Cancellation reason must be provided")
        self.cancel_reason = reason
        self.transition_to(TripState.CANCELLED)

    def run_simulated_trip(
        self, driver_id: str, step_size: float = 25.0, time_step_sec: float = 10.0
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Executes a complete trip lifecycle yielding telemetry updates.
        """
        # Step 1: Matching
        self.assign_driver(driver_id)
        yield self._snapshot("Driver matched to rider")

        # Step 2: Arriving
        self.driver_arrived()
        yield self._snapshot("Driver arrived at pickup location")

        # Step 3: Start In Transit
        self.start_trip()
        yield self._snapshot("Rider picked up. In transit")

        # Step 4: Progress telemetry ticks
        tick = 1
        while self.current_position < self.destination:
            next_pos = min(self.destination, self.current_position + step_size)
            self.update_telemetry(position=next_pos, time_delta=time_step_sec)
            yield self._snapshot(f"In-transit telemetry tick {tick}")
            tick += 1

        # Step 5: Dropped off
        self.drop_off()
        yield self._snapshot("Destination reached. Rider dropped off")

        # Step 6: Completed with fare ($2.50 base + $1.50/km)
        computed_fare = 2.50 + (self.distance * 0.05)
        self.complete_trip(final_fare=round(computed_fare, 2))
        yield self._snapshot("Trip completed and fare settled")

    def _snapshot(self, message: str) -> Dict[str, Any]:
        """Generates an immutable telemetry snapshot."""
        return {
            "trip_id": self.trip_id,
            "rider_id": self.rider_id,
            "driver_id": self.driver_id,
            "state": self.state.value,
            "current_position": self.current_position,
            "destination": self.destination,
            "distance": round(self.distance, 2),
            "duration_seconds": round(self.duration_seconds, 1),
            "fare": round(self.fare, 2),
            "message": message,
        }
