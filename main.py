"""
main.py - Runnable CLI demonstration for Milestone 5: Decoupled Service Layer
"""

from internal.domain.driver import Driver
from internal.domain.trip import GeoCoordinate
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.matching import MatchingService
from internal.service.trip_service import TripService


def main() -> None:
    print("=" * 80)
    print("UBER MOBILITY ENGINE - MILESTONE 5: DECOUPLED SERVICE & REPOSITORY ARCHITECTURE")
    print("=" * 80)

    # 1. Instantiate persistence adapters
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    # 2. Register fleet drivers
    d1 = Driver("D-01", "Alex Chen", GeoCoordinate(lat=10.7720, lon=106.6980))
    d2 = Driver("D-02", "Bao Nguyen", GeoCoordinate(lat=10.7850, lon=106.7120))
    driver_repo.register(d1)
    driver_repo.register(d2)
    print(f"[*] Repositories initialized: {len(driver_repo.list_all())} fleet driver(s) registered.")

    # 3. Instantiate domain services
    matching_service = MatchingService(driver_repo, default_search_radius_km=10.0)
    trip_service = TripService(trip_repo, driver_repo, matching_service)

    # 4. Use Case: Request Trip
    origin = GeoCoordinate(lat=10.7760, lon=106.7000)
    destination = GeoCoordinate(lat=10.8000, lon=106.7300)
    trip, is_dup = trip_service.request_trip(
        idempotency_key="req-uber-live-01",
        rider_id="rider-maria",
        origin=origin,
        destination=destination,
        passenger_count=1,
    )
    print(f"\n[1. Request Trip] Created Trip ID: {trip.trip_id} | State: {trip.state.value} | Duplicate: {is_dup}")

    # 5. Use Case: Match Driver
    trip, driver, eta_min = trip_service.match_and_assign_driver(trip.trip_id)
    print(f"[2. Match Driver] Matched: {driver.name} (ID: {driver.driver_id}) | ETA: {eta_min:.1f} min | Trip State: {trip.state.value}")

    # 6. Use Case: Driver Arrives & Start Transit
    trip = trip_service.driver_arrived_at_pickup(trip.trip_id)
    print(f"[3. Arrive Pickup] Driver at pickup | Trip State: {trip.state.value}")

    trip = trip_service.start_trip(trip.trip_id)
    print(f"[4. Start Transit] Passenger onboard | Trip State: {trip.state.value} | Driver State: {driver.state.value}")

    # 7. Use Case: Telemetry Update
    trip = trip_service.update_telemetry(
        trip_id=trip.trip_id,
        lat=10.7880,
        lon=106.7150,
        distance_delta_km=2.4,
        time_delta_sec=300.0,
    )
    print(f"[5. Telemetry] Position: ({trip.current_lat:.4f}, {trip.current_lon:.4f}) | Distance: {trip.distance_km:.1f} km | Duration: {trip.duration_seconds:.0f}s")

    # 8. Use Case: Drop-Off & Complete Trip
    trip = trip_service.drop_off_rider(trip.trip_id)
    print(f"[6. Drop-off] Destination reached | Trip State: {trip.state.value}")

    trip = trip_service.complete_trip(trip.trip_id, base_fare=2.50, per_km_rate=1.20)
    print(f"[7. Complete Trip] Final State: {trip.state.value} | Settled Fare: ${trip.fare:.2f} | Driver State: {driver.state.value}")

    print("\n[✓] Complete Use-Case Workflow Verified Across Architectural Boundaries.")
    print("=" * 80)


if __name__ == "__main__":
    main()
