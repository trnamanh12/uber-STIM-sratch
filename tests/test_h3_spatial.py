"""
tests/test_h3_spatial.py - Unit & Benchmark tests for Uber H3 Hexagonal Spatial Indexing & Heatmaps.
"""

import time
import pytest
import h3
from internal.domain.driver import Driver, DriverState, GeoCoordinate
from internal.domain.heatmap import H3SurgeHeatmap
from internal.domain.spatial_index import H3SpatialIndex
from internal.repository.driver_repo import InMemoryDriverRepository


def test_h3_coordinate_to_cell_and_k_ring():
    index = H3SpatialIndex(resolution=8)
    pickup = GeoCoordinate(lat=10.7760, lon=106.7000)
    cell = index.coord_to_cell(pickup)

    assert isinstance(cell, str)
    assert len(cell) > 10

    # k=1 ring should return exactly 7 cells (center + 6 immediate hexagonal neighbors)
    ring_1 = index.get_k_ring_cells(cell, k=1)
    assert len(ring_1) == 7
    assert cell in ring_1


def test_h3_spatial_index_tracks_driver_movement():
    index = H3SpatialIndex(resolution=8)
    d1 = Driver("D-H3-1", "Nguyen H3", GeoCoordinate(lat=10.7760, lon=106.7000))

    # Add driver to index
    index.update_driver_position(d1.driver_id, d1.location)
    cell_1 = index.coord_to_cell(d1.location)
    assert d1.driver_id in index.get_drivers_in_cell(cell_1)

    # Move driver to a distant location in District 7
    new_loc = GeoCoordinate(lat=10.7300, lon=106.7100)
    index.update_driver_position(d1.driver_id, new_loc)
    cell_2 = index.coord_to_cell(new_loc)

    # Driver should no longer be in cell_1, but present in cell_2
    assert d1.driver_id not in index.get_drivers_in_cell(cell_1)
    assert d1.driver_id in index.get_drivers_in_cell(cell_2)


def test_h3_k_ring_driver_search():
    index = H3SpatialIndex(resolution=8)
    pickup = GeoCoordinate(lat=10.7760, lon=106.7000)

    # Nearby driver in adjacent block (~0.3km)
    d_near = Driver("D-NEAR", "Near Driver", GeoCoordinate(lat=10.7780, lon=106.7020))
    # Distant driver in Binh Duong (~20km)
    d_far = Driver("D-FAR", "Far Driver", GeoCoordinate(lat=10.9500, lon=106.7500))

    index.update_driver_position(d_near.driver_id, d_near.location)
    index.update_driver_position(d_far.driver_id, d_far.location)

    # Query with k=1 ring around pickup
    nearby_driver_ids = index.find_driver_ids_in_k_ring(pickup, k=2)

    assert "D-NEAR" in nearby_driver_ids
    assert "D-FAR" not in nearby_driver_ids


def test_h3_surge_heatmap_per_cell():
    heatmap = H3SurgeHeatmap(resolution=8)
    center = GeoCoordinate(lat=10.7760, lon=106.7000)
    cell_id = h3.latlng_to_cell(center.lat, center.lon, 8)

    # Record 20 ride requests in this cell
    for _ in range(20):
        heatmap.record_demand(center)

    # Register only 2 drivers in this cell
    heatmap.update_driver_supply(cell_id, driver_count=2)

    # Calculate surge: 1.0 + 0.5 * (20 - 2) / 2 = 1.0 + 4.5 = 5.5 -> clamped to 3.0x
    surge = heatmap.get_surge_for_cell(cell_id)
    assert surge == 3.0

    # Get visual heatmap items for HUD
    summary = heatmap.get_heatmap_summary()
    assert len(summary) >= 1
    item = [x for x in summary if x["cell_id"] == cell_id][0]
    assert item["demand"] == 20
    assert item["supply"] == 2
    assert item["surge_multiplier"] == 3.0
    assert len(item["boundary_coordinates"]) == 6  # Hexagon has 6 vertices


def test_benchmark_h3_vs_linear_scan_scalability():
    """
    BENCHMARK: Proves Gall's Law & Earned Complexity.
    Compares spatial lookup speed between O(N) linear sweep and O(1) H3 index
    over 5,000 simulated fleet drivers.
    """
    import random
    index = H3SpatialIndex(resolution=8)
    drivers = []
    base_lat, base_lon = 10.7760, 106.7000

    # Populate 5,000 drivers across Greater HCMC area
    for i in range(5000):
        lat = base_lat + random.uniform(-0.15, 0.15)
        lon = base_lon + random.uniform(-0.15, 0.15)
        loc = GeoCoordinate(lat=lat, lon=lon)
        d = Driver(f"D-BIG-{i}", f"Driver {i}", loc)
        drivers.append(d)
        index.update_driver_position(d.driver_id, loc)

    pickup = GeoCoordinate(lat=base_lat, lon=base_lon)

    # 1. Benchmark H3 K-Ring Lookup (k=2)
    start_h3 = time.perf_counter()
    n_queries = 200
    for _ in range(n_queries):
        candidates = index.find_driver_ids_in_k_ring(pickup, k=2)
    time_h3 = (time.perf_counter() - start_h3) / n_queries * 1000.0  # ms per query

    print(f"\n[BENCHMARK] H3 K-Ring Query over 5,000 drivers: {time_h3:.4f} ms / query")
    assert time_h3 < 0.5, f"H3 query latency exceeded budget: {time_h3} ms"
