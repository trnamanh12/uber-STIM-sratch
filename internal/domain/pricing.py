"""
internal/domain/pricing.py - Dynamic Surge Pricing Engine & Invariants.

Zero external dependencies. Pure domain logic and economic modeling.
"""

from dataclasses import dataclass
from internal.domain.trip import InvariantViolationError


@dataclass(frozen=True)
class PricingConfig:
    base_fare: float = 2.50
    per_km_rate: float = 1.20
    per_minute_rate: float = 0.25
    min_surge_multiplier: float = 1.0
    max_surge_multiplier: float = 3.0
    surge_sensitivity: float = 0.5


class SurgePricingEngine:
    """
    Computes dynamic surge multiplier based on local supply vs. demand.
    Surge Multiplier S = clamp(1.0, 3.0, 1.0 + alpha * (demand - supply) / supply)
    """

    def __init__(self, config: PricingConfig = PricingConfig()) -> None:
        self.config = config

    def calculate_surge_multiplier(self, active_demand: int, available_supply: int) -> float:
        """
        Calculates dynamic surge multiplier based on demand and supply.
        Enforces invariant: min_surge <= multiplier <= max_surge.
        """
        if active_demand < 0:
            raise InvariantViolationError(f"Demand cannot be negative: {active_demand}")
        if available_supply < 0:
            raise InvariantViolationError(f"Supply cannot be negative: {available_supply}")

        if available_supply == 0:
            # Maximum scarcity ceiling
            return self.config.max_surge_multiplier if active_demand > 0 else self.config.min_surge_multiplier

        imbalance = max(0, active_demand - available_supply)
        surge = 1.0 + self.config.surge_sensitivity * (imbalance / available_supply)
        
        # Enforce bounding invariant
        clamped_surge = max(
            self.config.min_surge_multiplier,
            min(self.config.max_surge_multiplier, surge)
        )
        return round(clamped_surge, 2)

    def calculate_fare(
        self,
        distance_km: float,
        duration_seconds: float,
        surge_multiplier: float = 1.0,
    ) -> float:
        """Computes total trip fare with surge multiplier."""
        if distance_km < 0.0 or duration_seconds < 0.0:
            raise InvariantViolationError("Distance and duration must be non-negative")
        if surge_multiplier < self.config.min_surge_multiplier:
            raise InvariantViolationError(
                f"Surge multiplier cannot be below {self.config.min_surge_multiplier}"
            )

        duration_minutes = duration_seconds / 60.0
        base = self.config.base_fare
        distance_cost = distance_km * self.config.per_km_rate
        time_cost = duration_minutes * self.config.per_minute_rate

        raw_fare = (base + distance_cost + time_cost) * surge_multiplier
        return round(raw_fare, 2)
