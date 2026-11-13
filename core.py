"""
core.py - High-Level Facade re-exporting decoupled domain, repository, and service boundaries.
"""

from internal.domain.trip import (
    DomainError,
    IllegalStateTransitionError,
    InvariantViolationError,
    PoisonPayloadError,
    TripState,
    GeoCoordinate,
    DomainEvent,
    Trip,
    ALLOWED_TRANSITIONS,
)
from internal.domain.driver import (
    DriverState,
    Driver,
    haversine_distance_km,
)
from internal.repository.driver_repo import (
    DriverRepository,
    InMemoryDriverRepository,
)
from internal.repository.trip_repo import (
    TripRepository,
    InMemoryTripRepository,
)
from internal.service.matching import (
    MatchingService,
    NoDriverAvailableError,
)
from internal.service.trip_service import (
    TripService,
    TripNotFoundError,
)
from internal.domain.pricing import (
    PricingConfig,
    SurgePricingEngine,
)
from internal.domain.offer import (
    DispatchOffer,
    OfferState,
    OfferExpiredError,
)
from internal.service.cascading_dispatch import (
    CascadingDispatchService,
)
from internal.domain.spatial_index import (
    H3SpatialIndex,
)
from internal.domain.heatmap import (
    H3SurgeHeatmap,
)
from internal.domain.ledger import (
    Account,
    AccountType,
    Posting,
    PostingDirection,
    JournalEntry,
    DoubleEntryLedgerError,
    UnbalancedJournalEntryError,
    InsufficientFundsError,
)
from internal.service.billing_service import (
    BillingService,
)
from internal.domain.routing import (
    RoadGraph,
    IntersectionNode,
    RoadEdge,
    KinematicPath,
    NoPathFoundError,
)
from internal.service.router import (
    AStarRouter,
)

__all__ = [
    "DomainError",
    "IllegalStateTransitionError",
    "InvariantViolationError",
    "PoisonPayloadError",
    "TripState",
    "GeoCoordinate",
    "DomainEvent",
    "Trip",
    "ALLOWED_TRANSITIONS",
    "DriverState",
    "Driver",
    "haversine_distance_km",
    "DriverRepository",
    "InMemoryDriverRepository",
    "TripRepository",
    "InMemoryTripRepository",
    "MatchingService",
    "NoDriverAvailableError",
    "TripService",
    "TripNotFoundError",
    "PricingConfig",
    "SurgePricingEngine",
    "DispatchOffer",
    "OfferState",
    "OfferExpiredError",
    "CascadingDispatchService",
    "H3SpatialIndex",
    "H3SurgeHeatmap",
    "Account",
    "AccountType",
    "Posting",
    "PostingDirection",
    "JournalEntry",
    "DoubleEntryLedgerError",
    "UnbalancedJournalEntryError",
    "InsufficientFundsError",
    "BillingService",
    "RoadGraph",
    "IntersectionNode",
    "RoadEdge",
    "KinematicPath",
    "NoPathFoundError",
    "AStarRouter",
]
