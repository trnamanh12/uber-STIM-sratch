"""
tests/test_pricing_and_detour.py - Unit & Benchmark tests for Surge Pricing and Detour Routing.
"""

import time
import pytest
from internal.domain.driver import Driver, GeoCoordinate
from internal.domain.pricing import PricingConfig, SurgePricingEngine
from internal.domain.trip import InvariantViolationError, Trip, TripState
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.service.matching import MatchingService


# ==============================================================================
# SURGE PRICING ENGINE TESTS
# ==============================================================================

def test_surge_pricing_supply_demand_bounds():
    engine = SurgePricingEngine(PricingConfig(min_surge_multiplier=1.0, max_surge_multiplier=3.0, surge_sensitivity=0.5))

    # Balanced supply/demand -> minimum multiplier (1.0x)
    assert engine.calculate_surge_multiplier(active_demand=10, available_supply=10) == 1.0
    assert engine.calculate_surge_multiplier(active_demand=5, available_supply=20) == 1.0

    # Moderate demand imbalance: 15 demand vs 5 supply -> surge = 1.0 + 0.5 * (10 / 5) = 2.0x
    assert engine.calculate_surge_multiplier(active_demand=15, available_supply=5) == 2.0

    # Extreme demand imbalance: clamped to ceiling (3.0x)
    assert engine.calculate_surge_multiplier(active_demand=100, available_supply=2) == 3.0

    # Zero supply with active demand -> capped at max surge (3.0x)
    assert engine.calculate_surge_multiplier(active_demand=5, available_supply=0) == 3.0

    # Rejection of negative values
    with pytest.raises(InvariantViolationError):
        engine.calculate_surge_multiplier(active_demand=-1, available_supply=5)


def test_fare_calculation_formula():
    engine = SurgePricingEngine(PricingConfig(base_fare=2.50, per_km_rate=1.20, per_minute_rate=0.30))
    # Distance = 10km ($12.00), Duration = 10 min = 600s ($3.00), Base = $2.50 -> Subtotal = $17.50
    # With surge 1.5x -> $26.25
    fare = engine.calculate_fare(distance_km=10.0, duration_seconds=600.0, surge_multiplier=1.5)
    assert fare == 26.25


# ==============================================================================
# MULTI-STOP DETOUR ROUTING & INVARIANT A INTEGRITY TESTS
# ==============================================================================

def test_detour_routing_preserves_destination_integrity():
    origin = GeoCoordinate(lat=10.7600, lon=106.6600)
    final_dest = GeoCoordinate(lat=10.8200, lon=106.7500)
    trip = Trip("TRIP-DETOUR", "RIDER-MULTI", origin=origin, destination=final_dest)

    # Invariant A: Original Destination is locked
    assert trip.destination == final_dest

    # Add intermediate detour stop
    stop1 = GeoCoordinate(lat=10.7800, lon=106.6900)
    trip.add_waypoint(stop1)
    assert len(trip.waypoints) == 1
    assert trip.waypoints[0] == stop1

    # Invariant A check: Destination MUST remain unchanged after detour insertion
    assert trip.destination == final_dest

    # Progress trip
    trip.assign_driver("D-DETOUR")
    trip.driver_arrived()
    trip.start_trip()
    trip.update_telemetry(lat=10.7800, lon=106.6900, distance_delta_km=3.0, time_delta_sec=300.0)

    # Invariant: Cannot drop off at final destination before visiting all waypoints
    with pytest.raises(InvariantViolationError, match="Cannot drop off at destination before visiting all waypoints"):
        trip.drop_off()

    # Reach intermediate stop
    trip.reach_waypoint(0)
    assert len(trip.visited_waypoints) == 1

    # Now drive to final destination and drop off
    trip.update_telemetry(lat=10.8200, lon=106.7500, distance_delta_km=4.5, time_delta_sec=400.0)
    trip.drop_off()
    assert trip.state == TripState.DROPPED_OFF
    assert trip.current_lat == final_dest.lat
    assert trip.current_lon == final_dest.lon


# ==============================================================================
# BENCHMARK: DISPATCH ENGINE LATENCY UNDER FLEET LOAD
# ==============================================================================

def test_benchmark_dispatch_latency_under_fleet_load():
    """
    Stress test dispatch engine across 100 driver candidates.
    Asserts dispatch latency is strictly under 5 milliseconds (budget).
    """
    driver_repo = InMemoryDriverRepository()
    center_lat = 10.7760
    center_lon = 106.7000

    # Seed 100 drivers distributed around city center
    for i in range(100):
        offset_lat = (i % 10) * 0.005 - 0.025
        offset_lon = (i // 10) * 0.005 - 0.025
        d = Driver(
            driver_id=f"D-BENCH-{i:03d}",
            name=f"Driver #{i}",
            location=GeoCoordinate(lat=center_lat + offset_lat, lon=center_lon + offset_lon),
        )
        driver_repo.register(d)

    dispatcher = MatchingService(driver_repo, default_search_radius_km=15.0)
    pickup = GeoCoordinate(lat=center_lat, lon=center_lon)

    # Warmup
    dispatcher.match_driver_for_trip(pickup)

    # Benchmark 200 consecutive dispatch calls
    start_time = time.perf_counter()
    iterations = 200
    for _ in range(iterations):
        matched, dist, eta = dispatcher.match_driver_for_trip(pickup)
        assert matched is not None
        assert dist >= 0.0
    elapsed_total = time.perf_counter() - start_time

    avg_latency_ms = (elapsed_total / iterations) * 1000.0
    print(f"\n[BENCHMARK] Average dispatch latency across 100 drivers: {avg_latency_ms:.3f} ms / query")

    # Assert sub-millisecond or well within 5ms budget
    assert avg_latency_ms < 5.0, f"Dispatch latency exceeded budget: {avg_latency_ms} ms"
