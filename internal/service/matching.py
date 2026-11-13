"""
internal/service/matching.py - Spatial Driver Matching Use Case.
"""

from typing import Optional, Tuple
from internal.domain.driver import Driver, haversine_distance_km
from internal.domain.trip import DomainError, GeoCoordinate
from internal.repository.driver_repo import DriverRepository


class NoDriverAvailableError(DomainError):
    """Raised when matching service cannot find an eligible driver."""
    pass


class MatchingService:
    """
    Coordinates spatial driver matching across driver repository.
    Enforces maximum search radius and minimum ETA dispatch rules.
    """

    def __init__(self, driver_repo: DriverRepository, default_search_radius_km: float = 10.0) -> None:
        self.driver_repo = driver_repo
        self.default_search_radius_km = default_search_radius_km

    def match_driver_for_trip(
        self, pickup: GeoCoordinate, max_search_radius_km: Optional[float] = None
    ) -> Tuple[Driver, float, float]:
        """
        Matches nearest IDLE driver to pickup coordinate.
        Returns: (Driver, distance_km, eta_minutes)
        """
        radius = max_search_radius_km or self.default_search_radius_km
        available_drivers = self.driver_repo.list_available()
        if not available_drivers:
            raise NoDriverAvailableError("No available idle drivers found in fleet")

        best_driver: Optional[Driver] = None
        min_distance = float("inf")

        for driver in available_drivers:
            dist = haversine_distance_km(driver.location, pickup)
            if dist < min_distance and dist <= radius:
                min_distance = dist
                best_driver = driver

        if best_driver is None:
            raise NoDriverAvailableError(
                f"No idle drivers found within search radius of {radius:.1f} km"
            )

        # Average urban speed 30 km/h
        eta_minutes = round((min_distance / 30.0) * 60.0, 1)
        return best_driver, round(min_distance, 3), max(1.0, eta_minutes)
