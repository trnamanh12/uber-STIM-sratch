"""
main.py - Runnable CLI demonstration for Milestone 4: Spatial Matching & Dispatch
"""

from core import (
    DispatchEngine,
    Driver,
    DriverPool,
    GeoCoordinate,
    NoDriverAvailableError,
    haversine_distance_km,
)


def main() -> None:
    print("=" * 80)
    print("UBER MOBILITY ENGINE - MILESTONE 4: SPATIAL DRIVER MATCHING & DISPATCH")
    print("=" * 80)

    # 1. Initialize Fleet & Driver Pool
    pool = DriverPool()
    drivers = [
        Driver("D-01", "Alex Chen", GeoCoordinate(lat=10.7720, lon=106.6980)),      # Dist ~ 0.5 km
        Driver("D-02", "Bao Nguyen", GeoCoordinate(lat=10.7850, lon=106.7120)),     # Dist ~ 2.1 km
        Driver("D-03", "Carlos Silva", GeoCoordinate(lat=10.8200, lon=106.7500)),   # Dist ~ 7.8 km
    ]
    for d in drivers:
        pool.register_driver(d)

    print(f"[*] Registered {len(drivers)} drivers in active fleet pool.")

    # 2. Rider request comes in at Central Pickup
    pickup = GeoCoordinate(lat=10.7760, lon=106.7000)
    print(f"[*] Rider Pickup Location: ({pickup.lat:.4f}, {pickup.lon:.4f})")

    # 3. Dispatch: Find nearest available driver
    dispatcher = DispatchEngine(pool, default_search_radius_km=10.0)
    matched_driver, dist_km, eta_min = dispatcher.match_nearest_driver(pickup)

    print("\n[-] Executing Spatial Dispatch Engine (Haversine Metric)...")
    for d in drivers:
        d_dist = haversine_distance_km(d.location, pickup)
        status_tag = "MATCHED (Nearest)" if d.driver_id == matched_driver.driver_id else "AVAILABLE"
        print(f"    Driver {d.driver_id:<5} ({d.name:<13}) | Pos: ({d.location.lat:.4f}, {d.location.lon:.4f}) | "
              f"Distance: {d_dist:5.2f} km | Status: {status_tag}")

    print(f"\n[✓] Dispatch Decision:")
    print(f"    --> Assigned Driver: {matched_driver.name} (ID: {matched_driver.driver_id})")
    print(f"    --> Geodesic Distance: {dist_km:.2f} km")
    print(f"    --> Estimated Pickup ETA: {eta_min:.1f} minutes")

    # 4. Demonstrate Edge Case: Graceful Backoff when all drivers are busy/out of radius
    print("\n[-] Testing Edge Case: Exhausted Fleet / No Drivers Available...")
    for d in drivers:
        d.mark_busy()

    try:
        dispatcher.match_nearest_driver(pickup)
    except NoDriverAvailableError as exc:
        print(f"  [✓] Graceful Backoff Triggered: {exc}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
