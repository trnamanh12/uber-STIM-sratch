"""
main.py - Runnable CLI demonstration for Milestone 2: Formal State Machine
"""

import time
from core import Trip, TripState, IllegalStateTransitionError


def main() -> None:
    print("=" * 75)
    print("UBER MOBILITY ENGINE - MILESTONE 2: FORMAL TRIP STATE MACHINE & INVARIANTS")
    print("=" * 75)

    trip = Trip(
        trip_id="trip-202",
        rider_id="rider-88",
        origin=0.0,
        destination=100.0,
    )

    print(f"[*] Trip Created: ID={trip.trip_id}, Rider={trip.rider_id}")
    print(f"[*] Initial State: {trip.state.value} | Destination Locked at: {trip.destination}m")
    print("\n[-] Executing Simulated Trip Lifecycle with Invariant Verification...\n")

    for snapshot in trip.run_simulated_trip(driver_id="driver-007", step_size=25.0, time_step_sec=5.0):
        print(
            f"    [{snapshot['state']:<15}] "
            f"Pos: {snapshot['current_position']:>5.1f}m / {snapshot['destination']:>5.1f}m | "
            f"Dist: {snapshot['distance']:>5.1f}m | "
            f"Fare: ${snapshot['fare']:>5.2f} | "
            f"{snapshot['message']}"
        )

    print(f"\n[✓] Final Trip State: {trip.state.value}")
    print(f"[✓] Fare Settled: ${trip.fare:.2f}")

    # Demonstrate Invariant B: Terminal Lock
    print("\n[-] Verifying Invariant B (Terminal Lock): Attempting illegal mutation...")
    try:
        trip.transition_to(TripState.IN_TRANSIT)
        print("[!] ERROR: Terminal lock failed!")
    except IllegalStateTransitionError as exc:
        print(f"[✓] Invariant B Preserved! System rejected transition with error:\n    --> {exc}")

    print("=" * 75)


if __name__ == "__main__":
    main()
