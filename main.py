"""
main.py - Runnable CLI entry point for Milestone 1: Walking Skeleton
"""

from core import WalkingSkeletonTrip


def main() -> None:
    print("=" * 70)
    print("UBER MOBILITY ENGINE - MILESTONE 1: WALKING SKELETON (1D SIMULATION)")
    print("=" * 70)

    trip = WalkingSkeletonTrip(
        trip_id="trip-101",
        rider_id="rider-42",
        origin=0.0,
        destination=100.0,
        step_size=20.0,
    )

    print(f"[*] Trip Requested: ID={trip.trip_id}, Rider={trip.rider_id}")
    print(f"[*] Origin: x={trip.origin}m -> Destination: x={trip.destination}m")
    print("[-] Starting Vehicle Telemetry Loop...\n")

    for telemetry in trip.run_simulation():
        print(
            f"    [Tick {telemetry['tick']:02d}] "
            f"Pos: {telemetry['position']:>5.1f}m / {telemetry['destination']:>5.1f}m | "
            f"Remaining: {telemetry['remaining']:>5.1f}m | "
            f"State: {telemetry['state']}"
        )

    print(f"\n[✓] Trip Terminated Successfully: Final State = {trip.state}")
    print("=" * 70)


if __name__ == "__main__":
    main()
