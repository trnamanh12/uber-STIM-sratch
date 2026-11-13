"""
core.py - Naive Domain Engine & 15-Minute Walking Skeleton

Adheres to Gall's Law:
"A complex system that works is invariably found to have evolved from a simple
system that worked."

Zero external frameworks, zero databases, zero speculative abstractions.
Models a single 1D trip loop connecting ingest to egress.
"""

from typing import Any, Dict, Generator


class WalkingSkeletonTrip:
    """Minimal representation of a 1D scalar mobility trip."""

    def __init__(
        self,
        trip_id: str,
        rider_id: str,
        origin: float = 0.0,
        destination: float = 100.0,
        step_size: float = 20.0,
    ) -> None:
        if destination <= origin:
            raise ValueError("Destination must be strictly greater than origin")
        if step_size <= 0:
            raise ValueError("Step size must be strictly positive")
        self.trip_id = trip_id
        self.rider_id = rider_id
        self.origin = origin
        self.destination = destination
        self.step_size = step_size
        self.current_x = origin
        self.state = "REQUESTED"

    def run_simulation(self) -> Generator[Dict[str, Any], None, None]:
        """Simulates trip execution in 1D space, yielding telemetry ticks until arrival."""
        self.state = "IN_TRANSIT"
        tick = 0

        # Initial telemetry tick at origin
        yield {
            "tick": tick,
            "trip_id": self.trip_id,
            "rider_id": self.rider_id,
            "position": self.current_x,
            "destination": self.destination,
            "remaining": self.destination - self.current_x,
            "state": self.state,
        }

        while self.current_x < self.destination:
            tick += 1
            self.current_x = min(self.destination, self.current_x + self.step_size)
            if self.current_x >= self.destination:
                self.state = "COMPLETED"

            yield {
                "tick": tick,
                "trip_id": self.trip_id,
                "rider_id": self.rider_id,
                "position": self.current_x,
                "destination": self.destination,
                "remaining": self.destination - self.current_x,
                "state": self.state,
            }
