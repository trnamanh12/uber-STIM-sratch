"""
tests/test_routing.py - Unit & Benchmark tests for Directed Road Graph & A* Routing Engine.
"""

import time
import pytest
from internal.domain.driver import GeoCoordinate
from internal.domain.routing import (
    IntersectionNode,
    NoPathFoundError,
    RoadEdge,
    RoadGraph,
)
from internal.service.router import AStarRouter


@pytest.fixture
def city_road_graph():
    """
    Creates a realistic 3x3 city grid representing central Saigon streets:
    N00 -- N01 -- N02   (Nguyen Hue St)
     |      |      |
    N10 -- N11 -- N12   (Dong Khoi St)
     |      |      |
    N20 -- N21 -- N22   (Le Loi Ave)
    With a ONE-WAY restriction: N11 -> N01 (cannot drive N01 -> N11 against traffic).
    """
    graph = RoadGraph()

    # Create 9 intersection nodes
    nodes = {
        "N00": GeoCoordinate(lat=10.7760, lon=106.7000),
        "N01": GeoCoordinate(lat=10.7760, lon=106.7050),
        "N02": GeoCoordinate(lat=10.7760, lon=106.7100),

        "N10": GeoCoordinate(lat=10.7720, lon=106.7000),
        "N11": GeoCoordinate(lat=10.7720, lon=106.7050),
        "N12": GeoCoordinate(lat=10.7720, lon=106.7100),

        "N20": GeoCoordinate(lat=10.7680, lon=106.7000),
        "N21": GeoCoordinate(lat=10.7680, lon=106.7050),
        "N22": GeoCoordinate(lat=10.7680, lon=106.7100),
    }
    for nid, coord in nodes.items():
        graph.add_intersection(IntersectionNode(nid, coord, f"Junction {nid}"))

    # Horizontal streets (Two-way)
    for r in range(3):
        graph.add_road_segment(f"N{r}0", f"N{r}1", "Eastbound Ave", is_one_way=False)
        graph.add_road_segment(f"N{r}1", f"N{r}2", "Eastbound Ave", is_one_way=False)

    # Vertical streets (Two-way, EXCEPT N11 -> N01 is ONE-WAY Northbound)
    graph.add_road_segment("N20", "N10", "St 1", is_one_way=False)
    graph.add_road_segment("N10", "N00", "St 1", is_one_way=False)

    graph.add_road_segment("N21", "N11", "St 2", is_one_way=False)
    # ONE-WAY: Can drive from N11 to N01, but NOT N01 to N11!
    graph.add_road_segment("N11", "N01", "One-Way St", is_one_way=True)

    graph.add_road_segment("N22", "N12", "St 3", is_one_way=False)
    graph.add_road_segment("N12", "N02", "St 3", is_one_way=False)

    return graph


def test_astar_finds_optimal_path(city_road_graph):
    router = AStarRouter(city_road_graph)
    start_coord = GeoCoordinate(lat=10.7680, lon=106.7000)  # N20
    dest_coord = GeoCoordinate(lat=10.7760, lon=106.7100)   # N02

    path = router.find_shortest_path(start_coord, dest_coord)

    assert len(path.nodes) >= 4
    assert path.nodes[0] == "N20"
    assert path.nodes[-1] == "N02"
    assert path.total_distance_km > 0.0
    assert len(path.waypoints) >= 4


def test_astar_respects_one_way_street_invariant(city_road_graph):
    router = AStarRouter(city_road_graph)
    # Start at N01, target N11
    # Recall: N11 -> N01 is ONE-WAY northbound!
    # Moving from N01 to N11 MUST NOT go directly down. It must detour via N00 or N02!
    start = GeoCoordinate(lat=10.7760, lon=106.7050)  # N01
    dest = GeoCoordinate(lat=10.7720, lon=106.7050)   # N11

    path = router.find_shortest_path(start, dest)

    # Path must NOT be directly ["N01", "N11"]
    assert path.nodes != ["N01", "N11"], "A* violated one-way street constraint!"
    # It must take a legal detour: N01 -> N00 -> N10 -> N11 OR N01 -> N02 -> N12 -> N11
    assert "N00" in path.nodes or "N02" in path.nodes


def test_astar_no_path_found_raises_error():
    graph = RoadGraph()
    graph.add_intersection(IntersectionNode("A", GeoCoordinate(10.0, 106.0)))
    graph.add_intersection(IntersectionNode("B", GeoCoordinate(10.1, 106.1)))
    # No edges between A and B
    router = AStarRouter(graph)

    with pytest.raises(NoPathFoundError):
        router.find_shortest_path(GeoCoordinate(10.0, 106.0), GeoCoordinate(10.1, 106.1))


def test_benchmark_astar_pathfinding_latency(city_road_graph):
    router = AStarRouter(city_road_graph)
    start = GeoCoordinate(lat=10.7680, lon=106.7000)
    dest = GeoCoordinate(lat=10.7760, lon=106.7100)

    start_bench = time.perf_counter()
    n_iters = 500
    for _ in range(n_iters):
        router.find_shortest_path(start, dest)
    avg_latency_ms = (time.perf_counter() - start_bench) / n_iters * 1000.0

    print(f"\n[BENCHMARK] A* Routing Latency: {avg_latency_ms:.4f} ms / route")
    assert avg_latency_ms < 0.5, f"A* latency exceeded 0.5ms: {avg_latency_ms}ms"
