"""
internal/domain/heatmap.py - Cell-Level Supply & Demand Spatial Heatmap.

Calculates granular dynamic surge multipliers across Uber H3 hexagonal partitions.
"""

from typing import Any, Dict, List, Optional
import h3
from internal.domain.pricing import PricingConfig, SurgePricingEngine
from internal.domain.trip import GeoCoordinate


class H3SurgeHeatmap:
    """
    Maintains spatial supply and demand counters across H3 hexagonal partitions.
    Computes local surge multipliers per cell.
    """

    def __init__(
        self,
        resolution: int = 8,
        pricing_engine: Optional[SurgePricingEngine] = None,
    ) -> None:
        self.resolution = resolution
        self.pricing_engine = pricing_engine or SurgePricingEngine()

        self._cell_demand: Dict[str, int] = {}
        self._cell_supply: Dict[str, int] = {}

    def coord_to_cell(self, coord: GeoCoordinate) -> str:
        return h3.latlng_to_cell(coord.lat, coord.lon, self.resolution)

    def record_demand(self, coord: GeoCoordinate) -> str:
        """Increments demand counter for the cell containing the pickup location."""
        cell = self.coord_to_cell(coord)
        self._cell_demand[cell] = self._cell_demand.get(cell, 0) + 1
        return cell

    def update_driver_supply(self, cell_id: str, driver_count: int) -> None:
        """Updates available supply count in a specific H3 cell."""
        self._cell_supply[cell_id] = max(0, driver_count)

    def get_surge_for_cell(self, cell_id: str) -> float:
        """Calculates dynamic surge multiplier for an individual H3 cell."""
        demand = self._cell_demand.get(cell_id, 0)
        supply = self._cell_supply.get(cell_id, 0)
        return self.pricing_engine.calculate_surge_multiplier(
            active_demand=demand,
            available_supply=supply,
        )

    def get_surge_for_coord(self, coord: GeoCoordinate) -> float:
        """Returns surge multiplier for the H3 cell containing coord."""
        cell = self.coord_to_cell(coord)
        return self.get_surge_for_cell(cell)

    def get_heatmap_summary(self) -> List[Dict[str, Any]]:
        """
        Returns serializable polygon metadata for all active cells.
        Ready for Canvas / MapLibre / Leaflet rendering.
        """
        all_cells = set(self._cell_demand.keys()).union(self._cell_supply.keys())
        summary = []

        for cell in all_cells:
            demand = self._cell_demand.get(cell, 0)
            supply = self._cell_supply.get(cell, 0)
            surge = self.get_surge_for_cell(cell)
            center_lat, center_lon = h3.cell_to_latlng(cell)
            boundary = h3.cell_to_boundary(cell)

            summary.append({
                "cell_id": cell,
                "center": {"lat": center_lat, "lon": center_lon},
                "boundary_coordinates": [{"lat": lat, "lon": lon} for lat, lon in boundary],
                "demand": demand,
                "supply": supply,
                "surge_multiplier": surge,
            })

        return summary
