"""
internal/service/cascading_dispatch.py - Driver Offer Negotiation & Cascading Dispatch Service.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from internal.domain.driver import Driver, DriverState, haversine_distance_km
from internal.domain.offer import (
    DispatchOffer,
    OfferExpiredError,
    OfferIllegalStateError,
    OfferState,
)
from internal.domain.trip import Trip, TripState
from internal.repository.driver_repo import DriverRepository
from internal.repository.trip_repo import TripRepository
from internal.service.matching import NoDriverAvailableError


class CascadingDispatchService:
    """
    Coordinates asynchronous driver offer negotiation, timeouts,
    and automatic cascading dispatch rings.
    """

    def __init__(
        self,
        trip_repo: TripRepository,
        driver_repo: DriverRepository,
        default_search_radius_km: float = 15.0,
        default_ttl_seconds: float = 15.0,
    ) -> None:
        self.trip_repo = trip_repo
        self.driver_repo = driver_repo
        self.default_search_radius_km = default_search_radius_km
        self.default_ttl_seconds = default_ttl_seconds

        self._offers: Dict[str, DispatchOffer] = {}
        self._declined_candidates: Dict[str, Set[str]] = {}  # trip_id -> set(driver_ids)
        self._lock = threading.Lock()

    def dispatch_next_candidate(
        self,
        trip_id: str,
        ttl_seconds: Optional[float] = None,
        max_search_radius_km: Optional[float] = None,
    ) -> DispatchOffer:
        """
        Finds the nearest available driver who has NOT yet declined this trip,
        and generates an ephemeral dispatch offer.
        """
        trip = self.trip_repo.get_by_id(trip_id)
        if not trip:
            raise ValueError(f"Trip not found: {trip_id}")

        radius = max_search_radius_km or self.default_search_radius_km
        ttl = ttl_seconds or self.default_ttl_seconds

        with self._lock:
            declined = self._declined_candidates.setdefault(trip_id, set())
            available_drivers = self.driver_repo.list_available()

            # Filter out drivers who already declined or timed out for this trip
            candidates = [d for d in available_drivers if d.driver_id not in declined]
            if not candidates:
                raise NoDriverAvailableError(
                    f"All available candidate drivers have declined or timed out for trip {trip_id}"
                )

            # Sort candidate drivers by Haversine distance from rider pickup
            ranked_candidates = []
            for d in candidates:
                dist = haversine_distance_km(d.location, trip.origin)
                if dist <= radius:
                    ranked_candidates.append((dist, d))

            ranked_candidates.sort(key=lambda x: x[0])
            if not ranked_candidates:
                raise NoDriverAvailableError(
                    f"All candidate drivers are outside the search radius of {radius}km"
                )

            best_dist, best_driver = ranked_candidates[0]

            # Generate new offer
            offer_id = f"offer-{uuid.uuid4().hex[:8]}"
            offer = DispatchOffer(
                offer_id=offer_id,
                trip_id=trip_id,
                driver_id=best_driver.driver_id,
                ttl_seconds=ttl,
            )
            self._offers[offer_id] = offer
            return offer

    def respond_to_offer(self, offer_id: str, action: str) -> Any:
        """
        Processes driver response:
        - ACCEPT: Matches trip, assigns driver, finishes dispatch.
        - DECLINE: Marks declined, immediately cascades to NEXT nearest driver.
        """
        with self._lock:
            offer = self._offers.get(offer_id)
            if not offer:
                raise ValueError(f"Offer not found: {offer_id}")

            trip = self.trip_repo.get_by_id(offer.trip_id)
            driver = self.driver_repo.get_by_id(offer.driver_id)
            normalized_action = action.upper().strip()

            if normalized_action == "ACCEPT":
                offer.accept()
                driver.assign_to_trip(trip.trip_id)
                trip.assign_driver(driver.driver_id)

                self.driver_repo.update(driver)
                self.trip_repo.save(trip)
                return trip, offer

            elif normalized_action == "DECLINE":
                offer.decline()
                self._declined_candidates.setdefault(offer.trip_id, set()).add(offer.driver_id)
                # Driver remains IDLE or is released back
                if driver.state == DriverState.ASSIGNED:
                    driver.release()
                    self.driver_repo.update(driver)

        # Cascading dispatch outside the lock to prevent deadlock
        return self.dispatch_next_candidate(offer.trip_id)

    def process_timeout_and_cascade(
        self, offer_id: str, current_time: Optional[float] = None
    ) -> DispatchOffer:
        """
        Expires timed-out offer and cascades to the next candidate.
        """
        with self._lock:
            offer = self._offers.get(offer_id)
            if not offer:
                raise ValueError(f"Offer not found: {offer_id}")

            offer.expire_if_timed_out(current_time)
            self._declined_candidates.setdefault(offer.trip_id, set()).add(offer.driver_id)

        return self.dispatch_next_candidate(offer.trip_id)

    def get_offer(self, offer_id: str) -> Optional[DispatchOffer]:
        with self._lock:
            return self._offers.get(offer_id)
