"""
tests/test_dispatch_offer.py - Unit & Integration tests for Driver Offer & Cascading Dispatch (TDD).
"""

import time
import pytest
from internal.domain.driver import Driver, DriverState, GeoCoordinate
from internal.domain.offer import (
    DispatchOffer,
    OfferExpiredError,
    OfferIllegalStateError,
    OfferState,
)
from internal.domain.trip import Trip, TripState
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.cascading_dispatch import CascadingDispatchService
from internal.service.matching import NoDriverAvailableError


@pytest.fixture
def cascading_setup():
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    # 3 drivers in increasing distance from rider pickup (10.7760, 106.7000)
    d1 = Driver("D-NEAR", "Nearest Driver", GeoCoordinate(lat=10.7770, lon=106.7010))    # ~ 0.15 km
    d2 = Driver("D-MID", "Middle Driver", GeoCoordinate(lat=10.7850, lon=106.7100))      # ~ 1.45 km
    d3 = Driver("D-FAR", "Furthest Driver", GeoCoordinate(lat=10.8100, lon=106.7400))    # ~ 5.7 km

    driver_repo.register(d1)
    driver_repo.register(d2)
    driver_repo.register(d3)

    trip = Trip(
        trip_id="T-OFFER-1",
        rider_id="rider-offer-test",
        origin=GeoCoordinate(lat=10.7760, lon=106.7000),
        destination=GeoCoordinate(lat=10.8000, lon=106.7200),
    )
    trip_repo.save(trip)

    dispatch_service = CascadingDispatchService(trip_repo, driver_repo, default_ttl_seconds=15.0)
    return dispatch_service, trip_repo, driver_repo, trip, d1, d2, d3


def test_offer_happy_path_driver_accepts(cascading_setup):
    service, trip_repo, driver_repo, trip, d1, d2, d3 = cascading_setup

    # 1. Initiate dispatch -> sends offer to nearest driver (D-NEAR)
    offer = service.dispatch_next_candidate(trip.trip_id)
    assert offer.driver_id == "D-NEAR"
    assert offer.state == OfferState.PENDING

    # 2. Driver D-NEAR accepts offer
    trip, accepted_offer = service.respond_to_offer(offer.offer_id, action="ACCEPT")
    assert accepted_offer.state == OfferState.ACCEPTED
    assert trip.state == TripState.MATCHED
    assert trip.driver_id == "D-NEAR"
    assert driver_repo.get_by_id("D-NEAR").state == DriverState.ASSIGNED


def test_cascading_dispatch_on_driver_decline(cascading_setup):
    service, trip_repo, driver_repo, trip, d1, d2, d3 = cascading_setup

    # 1. Offer sent to D-NEAR
    offer_1 = service.dispatch_next_candidate(trip.trip_id)
    assert offer_1.driver_id == "D-NEAR"

    # 2. D-NEAR declines offer
    next_offer = service.respond_to_offer(offer_1.offer_id, action="DECLINE")
    assert next_offer is not None
    # Cascades automatically to next nearest driver (D-MID)!
    assert next_offer.driver_id == "D-MID"
    assert next_offer.state == OfferState.PENDING

    # D-NEAR is released back to IDLE
    assert driver_repo.get_by_id("D-NEAR").state == DriverState.IDLE

    # 3. D-MID accepts
    trip, accepted_offer = service.respond_to_offer(next_offer.offer_id, action="ACCEPT")
    assert trip.state == TripState.MATCHED
    assert trip.driver_id == "D-MID"


def test_cascading_dispatch_on_offer_timeout(cascading_setup):
    service, trip_repo, driver_repo, trip, d1, d2, d3 = cascading_setup

    # Offer with simulated 1-second TTL
    offer_1 = service.dispatch_next_candidate(trip.trip_id, ttl_seconds=0.1)
    assert offer_1.driver_id == "D-NEAR"

    # Wait for TTL to expire
    time.sleep(0.15)

    # Process timeouts -> Cascades to D-MID
    cascaded_offer = service.process_timeout_and_cascade(offer_1.offer_id)
    assert cascaded_offer is not None
    assert cascaded_offer.driver_id == "D-MID"


def test_cascading_exhaustion_raises_no_driver_error(cascading_setup):
    service, trip_repo, driver_repo, trip, d1, d2, d3 = cascading_setup

    # D-NEAR declines
    o1 = service.dispatch_next_candidate(trip.trip_id)
    o2 = service.respond_to_offer(o1.offer_id, action="DECLINE")

    # D-MID declines
    o3 = service.respond_to_offer(o2.offer_id, action="DECLINE")
    assert o3.driver_id == "D-FAR"

    # D-FAR declines -> all 3 drivers have declined
    with pytest.raises(NoDriverAvailableError, match="All available candidate drivers have declined or timed out"):
        service.respond_to_offer(o3.offer_id, action="DECLINE")
