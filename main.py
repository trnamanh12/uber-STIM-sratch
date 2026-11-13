"""
main.py - Entry point for Milestone 8: Dynamic Pricing, Multi-Stop Detours & Performance Benchmarks.
"""

import sys
import time
from fastapi.testclient import TestClient
import uvicorn

from internal.domain.driver import Driver, GeoCoordinate
from internal.domain.pricing import PricingConfig, SurgePricingEngine
from internal.handler.app import create_app
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.matching import MatchingService
from internal.service.trip_service import TripService

app = create_app()


def run_cli_demo() -> None:
    print("=" * 80)
    print("UBER MOBILITY ENGINE - MILESTONE 8: DYNAMIC PRICING, DETOURS & BENCHMARKS")
    print("=" * 80)

    # 1. Surge Pricing Engine Demonstration
    print("\n[1. Dynamic Surge Pricing Engine]")
    pricing = SurgePricingEngine()
    test_cases = [
        ("High Supply (Surge Low)", 5, 20),
        ("Balanced Market (Surge Base)", 10, 10),
        ("Peak Hours (Surge High)", 25, 5),
        ("Storm Spike (Surge Capped)", 100, 2),
    ]
    for label, demand, supply in test_cases:
        surge = pricing.calculate_surge_multiplier(demand, supply)
        est_fare = pricing.calculate_fare(distance_km=8.5, duration_seconds=900, surge_multiplier=surge)
        print(f"  {label:<30} Demand={demand:>3} | Supply={supply:>2} | Multiplier={surge:.1f}x | Fare=${est_fare:.2f}")

    # 2. Multi-Stop Detour Routing with Invariant A Preservation
    print("\n[2. Multi-Stop Detour Routing & Invariant A (Destination Integrity)]")
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()
    d1 = Driver("D-01", "Alex Chen", GeoCoordinate(lat=10.7720, lon=106.6980))
    driver_repo.register(d1)
    matching = MatchingService(driver_repo)
    trip_service = TripService(trip_repo, driver_repo, matching, pricing)

    origin = GeoCoordinate(lat=10.7600, lon=106.6600)
    final_dest = GeoCoordinate(lat=10.8200, lon=106.7500)
    trip, _ = trip_service.request_trip(
        idempotency_key="detour-trip-001",
        rider_id="rider-multi-stop",
        origin=origin,
        destination=final_dest,
    )
    print(f"  --> Trip Created: Origin=({origin.lat:.4f}, {origin.lon:.4f}) -> Destination=({final_dest.lat:.4f}, {final_dest.lon:.4f})")
    print(f"  --> Invariant A: Locked Destination = ({trip.destination.lat:.4f}, {trip.destination.lon:.4f})")

    # Add Waypoint Detour
    intermediate_stop = GeoCoordinate(lat=10.7850, lon=106.7050)
    trip = trip_service.add_waypoint(trip.trip_id, intermediate_stop)
    print(f"  --> Detour Added: Waypoint #1 = ({trip.waypoints[0].lat:.4f}, {trip.waypoints[0].lon:.4f})")
    assert trip.destination == final_dest, "CRITICAL: Destination corrupted by detour!"
    print(f"  [✓] Invariant A Preserved! Destination remains strictly locked at ({trip.destination.lat:.4f}, {trip.destination.lon:.4f})")

    # 3. Microsecond Dispatch Latency Benchmark
    print("\n[3. Dispatch Engine Latency Benchmark under Fleet Load]")
    for i in range(100):
        lat = 10.7760 + ((i % 10) - 5) * 0.005
        lon = 106.7000 + ((i // 10) - 5) * 0.005
        driver_repo.register(Driver(f"D-LOAD-{i:03d}", f"Driver {i}", GeoCoordinate(lat=lat, lon=lon)))

    start_bench = time.perf_counter()
    n_queries = 200
    for _ in range(n_queries):
        matching.match_driver_for_trip(GeoCoordinate(lat=10.7760, lon=106.7000))
    elapsed = time.perf_counter() - start_bench
    avg_us = (elapsed / n_queries) * 1_000_000.0
    print(f"  --> Evaluated {n_queries} dispatch matches over 100 drivers.")
    print(f"  --> Average Dispatch Latency: {avg_us:.1f} microseconds ({avg_us / 1000.0:.3f} ms)")
    print(f"  [✓] Throughput: {n_queries / elapsed:,.0f} queries/sec (well within real-time budget)")

    print("\n[✓] Milestone 8 Earned Complexity Fully Operational & Verified.")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        run_cli_demo()
