"""
internal/domain/spatial_index.py - Uber H3 Hexagonal Spatial Index.

Provides O(1) local radius spatial partitioning and K-Ring candidate lookup.
"""

from typing import Dict, List, Optional, Set
import h3
from internal.domain.trip import GeoCoordinate


class H3SpatialIndex:
    """
    In-memory spatial index partitioning geographic space into Uber H3 hexagons.
    Replaces O(N) linear scans with O(1) K-Ring topological expansion.
    """

    def __init__(self, resolution: int = 8) -> None:
        """
        Resolution 8 corresponds to ~460m average hexagon edge length (approx 0.737 sq km),
        matching urban city blocks perfectly.
        """
        self.resolution = resolution
        self._driver_to_cell: Dict[str, str] = {}
        self._cell_to_drivers: Dict[str, Set[str]] = {}

    def coord_to_cell(self, coord: GeoCoordinate) -> str:
        """Encodes GPS (lat, lon) into an H3 hexagonal cell index."""
        return h3.latlng_to_cell(coord.lat, coord.lon, self.resolution)

    def get_k_ring_cells(self, cell: str, k: int = 1) -> List[str]:
        """
        Returns all hexagonal cells within distance k of the origin cell.
        k=1 returns 7 cells (center + 6 neighbors).
        k=2 returns 19 cells.
        """
        return list(h3.grid_disk(cell, k))

    def update_driver_position(self, driver_id: str, new_location: GeoCoordinate) -> str:
        """
        Atomically updates a driver's H3 spatial partition.
        Returns the new H3 cell index.
        """
        new_cell = self.coord_to_cell(new_location)
        old_cell = self._driver_to_cell.get(driver_id)

        if old_cell and old_cell != new_cell:
            # Remove from old cell
            if old_cell in self._cell_to_drivers:
                self._cell_to_drivers[old_cell].discard(driver_id)
                if not self._cell_to_drivers[old_cell]:
                    del self._cell_to_drivers[old_cell]

        # Add to new cell
        self._driver_to_cell[driver_id] = new_cell
        self._cell_to_drivers.setdefault(new_cell, set()).add(driver_id)
        return new_cell

    def remove_driver(self, driver_id: str) -> None:
        """Removes a driver from the spatial index."""
        old_cell = self._driver_to_cell.pop(driver_id, None)
        if old_cell and old_cell in self._cell_to_drivers:
            self._cell_to_drivers[old_cell].discard(driver_id)
            if not self._cell_to_drivers[old_cell]:
                del self._cell_to_drivers[old_cell]

    def get_drivers_in_cell(self, cell: str) -> Set[str]:
        """Returns all driver IDs currently indexed in a single H3 cell."""
        return set(self._cell_to_drivers.get(cell, set()))

    def find_driver_ids_in_k_ring(self, coord: GeoCoordinate, k: int = 1) -> List[str]:
        """
        O(1) Spatial Search:
        Retrieves all driver IDs located in the hexagon containing coord and its k rings.
        """
        center_cell = self.coord_to_cell(coord)
        ring_cells = self.get_k_ring_cells(center_cell, k=k)

        matched_drivers: Set[str] = set()
        for c in ring_cells:
            drivers_in_c = self._cell_to_drivers.get(c)
            if drivers_in_c:
                matched_drivers.update(drivers_in_c)

        return list(matched_drivers)

    def get_cell_boundary_coordinates(self, cell: str) -> List[Dict[str, float]]:
        """Returns the 6 vertex coordinates forming the boundary of the H3 hexagon."""
        boundary = h3.cell_to_boundary(cell)
        return [{"lat": lat, "lon": lon} for lat, lon in boundary]
