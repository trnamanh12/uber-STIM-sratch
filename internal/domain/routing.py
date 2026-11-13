"""
internal/domain/routing.py - Directed Road Network Graph & Kinematic Data Structures.

Zero external dependencies. Pure domain graph algorithms.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from internal.domain.driver import haversine_distance_km
from internal.domain.trip import DomainError, GeoCoordinate


class NoPathFoundError(DomainError):
    """Raised when no navigable path exists between two locations."""
    pass


@dataclass(frozen=True)
class IntersectionNode:
    """Represents a physical road intersection or road junction."""
    node_id: str
    location: GeoCoordinate
    name: str = ""


@dataclass(frozen=True)
class RoadEdge:
    """Represents a directed roadway segment connecting two intersections."""
    from_node: str
    to_node: str
    distance_km: float
    road_name: str = "Street"
    speed_limit_kmh: float = 40.0
    is_one_way: bool = False


@dataclass(frozen=True)
class KinematicPath:
    """The computed shortest route and generated waypoints along road edges."""
    nodes: List[str]
    waypoints: List[GeoCoordinate]
    total_distance_km: float
    estimated_duration_seconds: float


class RoadGraph:
    """
    Directed Weighted Road Network Graph G = (V, E).
    Enforces one-way street constraints and intersection connectivity.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, IntersectionNode] = {}
        self._adjacency: Dict[str, List[RoadEdge]] = {}

    def add_intersection(self, node: IntersectionNode) -> None:
        self._nodes[node.node_id] = node
        self._adjacency.setdefault(node.node_id, [])

    def add_road_segment(
        self,
        from_node: str,
        to_node: str,
        road_name: str = "Street",
        speed_limit_kmh: float = 40.0,
        is_one_way: bool = False,
    ) -> None:
        if from_node not in self._nodes or to_node not in self._nodes:
            raise ValueError(f"Nodes must exist in graph: {from_node}, {to_node}")

        dist = haversine_distance_km(self._nodes[from_node].location, self._nodes[to_node].location)
        edge_forward = RoadEdge(
            from_node=from_node,
            to_node=to_node,
            distance_km=dist,
            road_name=road_name,
            speed_limit_kmh=speed_limit_kmh,
            is_one_way=is_one_way,
        )
        self._adjacency[from_node].append(edge_forward)

        if not is_one_way:
            edge_backward = RoadEdge(
                from_node=to_node,
                to_node=from_node,
                distance_km=dist,
                road_name=road_name,
                speed_limit_kmh=speed_limit_kmh,
                is_one_way=False,
            )
            self._adjacency[to_node].append(edge_backward)

    def get_node(self, node_id: str) -> Optional[IntersectionNode]:
        return self._nodes.get(node_id)

    def get_outgoing_edges(self, node_id: str) -> List[RoadEdge]:
        return self._adjacency.get(node_id, [])

    def all_nodes(self) -> List[IntersectionNode]:
        return list(self._nodes.values())

    def find_nearest_node(self, coord: GeoCoordinate) -> str:
        """Finds the closest intersection node to an arbitrary GPS coordinate."""
        if not self._nodes:
            raise NoPathFoundError("Road graph has no intersections")

        best_node: Optional[str] = None
        min_dist = float("inf")
        for nid, node in self._nodes.items():
            d = haversine_distance_km(node.location, coord)
            if d < min_dist:
                min_dist = d
                best_node = nid

        return best_node  # type: ignore
