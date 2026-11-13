"""
internal/service/router.py - A* (A-Star) Pathfinding & Kinematic Route Generator.

Computes optimal shortest path along directed road networks using Haversine heuristic.
"""

import heapq
from typing import Dict, List, Optional, Tuple
from internal.domain.driver import haversine_distance_km
from internal.domain.routing import (
    IntersectionNode,
    KinematicPath,
    NoPathFoundError,
    RoadEdge,
    RoadGraph,
)
from internal.domain.trip import GeoCoordinate


class AStarRouter:
    """
    A* Shortest Path Routing Engine with Admissible Haversine Heuristic.
    Guarantees optimal route along directed road networks respecting one-way constraints.
    """

    def __init__(self, road_graph: RoadGraph) -> None:
        self.road_graph = road_graph

    def find_shortest_path(
        self,
        origin: GeoCoordinate,
        destination: GeoCoordinate,
    ) -> KinematicPath:
        start_node_id = self.road_graph.find_nearest_node(origin)
        target_node_id = self.road_graph.find_nearest_node(destination)

        target_node = self.road_graph.get_node(target_node_id)
        if not target_node:
            raise NoPathFoundError(f"Target node not found: {target_node_id}")

        # Priority queue storing: (f_score, tie_breaker, node_id)
        tie_breaker = 0
        open_set: List[Tuple[float, int, str]] = []
        heapq.heappush(open_set, (0.0, tie_breaker, start_node_id))

        came_from: Dict[str, str] = {}
        edge_used: Dict[str, RoadEdge] = {}
        g_score: Dict[str, float] = {start_node_id: 0.0}

        def heuristic(node_id: str) -> float:
            node = self.road_graph.get_node(node_id)
            if not node:
                return 0.0
            return haversine_distance_km(node.location, target_node.location)

        found = False
        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == target_node_id:
                found = True
                break

            for edge in self.road_graph.get_outgoing_edges(current):
                neighbor = edge.to_node
                tentative_g = g_score[current] + edge.distance_km

                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    edge_used[neighbor] = edge
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor)
                    tie_breaker += 1
                    heapq.heappush(open_set, (f, tie_breaker, neighbor))

        if not found and start_node_id != target_node_id:
            raise NoPathFoundError(f"No navigable path found between {start_node_id} and {target_node_id}")

        # Reconstruct path nodes
        path_nodes: List[str] = [target_node_id]
        curr = target_node_id
        while curr in came_from:
            curr = came_from[curr]
            path_nodes.append(curr)
        path_nodes.reverse()

        # Build waypoints along road network
        waypoints: List[GeoCoordinate] = []
        total_dist_km = 0.0
        total_seconds = 0.0

        for nid in path_nodes:
            n = self.road_graph.get_node(nid)
            if n:
                waypoints.append(n.location)

        for i in range(len(path_nodes) - 1):
            edge = edge_used.get(path_nodes[i + 1])
            if edge:
                total_dist_km += edge.distance_km
                hours = edge.distance_km / max(10.0, edge.speed_limit_kmh)
                total_seconds += hours * 3600.0

        return KinematicPath(
            nodes=path_nodes,
            waypoints=waypoints,
            total_distance_km=round(total_dist_km, 3),
            estimated_duration_seconds=round(total_seconds, 1),
        )
