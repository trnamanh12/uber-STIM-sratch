"""
main.py - Runnable CLI demonstration for Milestone 3: Hardening Against 4 Failure Modes
"""

from core import (
    GeoCoordinate,
    InMemoryTripRepository,
    PoisonPayloadError,
    TripRequestPayload,
    TripState,
)


def main() -> None:
    print("=" * 80)
    print("UBER MOBILITY ENGINE - MILESTONE 3: HARDENING AGAINST THE 4 FATAL QUESTIONS")
    print("=" * 80)

    repo = InMemoryTripRepository()

    # --------------------------------------------------------------------------
    # Q1: The Poison Pill Test
    # --------------------------------------------------------------------------
    print("\n[Q1: The Poison Pill] Testing boundary validation against malformed payload...")
    try:
        # Invalid coordinate (lat = 95.0, out of [-90, 90])
        bad_coord = GeoCoordinate(lat=95.0, lon=106.66)
    except PoisonPayloadError as exc:
        print(f"  [✓] Poison Pill Neutralized at Boundary: {exc}")

    # --------------------------------------------------------------------------
    # Q3: The Double Strike (Idempotency) Test
    # --------------------------------------------------------------------------
    print("\n[Q3: The Double Strike] Testing idempotent ride request deduplication...")
    valid_payload = TripRequestPayload(
        idempotency_key="idempotency-key-alpha-999",
        rider_id="rider-bob",
        origin=GeoCoordinate(lat=10.762622, lon=106.660172),
        destination=GeoCoordinate(lat=10.776530, lon=106.700980),
        passenger_count=2,
    )

    trip_1, is_dup_1 = repo.request_trip_idempotent(valid_payload)
    print(f"  --> Strike 1 (Initial Request): Trip ID={trip_1.trip_id}, Duplicate={is_dup_1}")

    trip_2, is_dup_2 = repo.request_trip_idempotent(valid_payload)
    print(f"  --> Strike 2 (Network Retry):   Trip ID={trip_2.trip_id}, Duplicate={is_dup_2}")
    assert trip_1.trip_id == trip_2.trip_id, "Idempotency violated!"
    print("  [✓] Double Strike Neutralized: Duplicate request recognized; zero side-effects.")

    # Mutate trip state
    trip_1.assign_driver("driver-hcm-01")
    trip_1.driver_arrived()
    trip_1.start_trip()
    trip_1.update_telemetry(lat=10.7690, lon=106.6800, distance_delta_km=1.8, time_delta_sec=180.0)

    # --------------------------------------------------------------------------
    # Q2: The Sudden Death (Crash Recovery) Test
    # --------------------------------------------------------------------------
    print("\n[Q2: The Sudden Death] Simulating crash and atomic state recovery...")
    snapshot = repo.create_snapshot()
    print(f"  --> Created atomic in-memory snapshot with {len(snapshot['trips'])} trip(s)")

    # Simulate crash by wiping memory
    crashed_repo = InMemoryTripRepository()
    print("  --> Process crashed! Memory wiped to zero.")
    assert crashed_repo.get(trip_1.trip_id) is None

    # Recover state
    crashed_repo.restore_from_snapshot(snapshot)
    recovered_trip = crashed_repo.get(trip_1.trip_id)
    assert recovered_trip is not None
    print(f"  [✓] State Recovered! Trip={recovered_trip.trip_id}, State={recovered_trip.state.value}, "
          f"Dist={recovered_trip.distance_km}km, Events={len(recovered_trip.events)}")

    # --------------------------------------------------------------------------
    # Q4: The Silent Bleed (Structured Observability) Test
    # --------------------------------------------------------------------------
    print("\n[Q4: The Silent Bleed] Inspecting structured domain event ledger...")
    for idx, event in enumerate(recovered_trip.events, 1):
        print(f"  Event #{idx:02d} [{event.event_type:<18}] CorrID={event.correlation_id} Payload={event.payload}")

    print("\n[✓] Milestone 3 Hardening Fully Operational & Verified.")
    print("=" * 80)


if __name__ == "__main__":
    main()
