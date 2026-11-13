"""
main.py - Entry point demonstrating Milestones 0 through 10.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import threading
import time
from fastapi.testclient import TestClient
import uvicorn

from internal.domain.driver import Driver, DriverState, GeoCoordinate
from internal.domain.pricing import PricingConfig, SurgePricingEngine
from internal.domain.offer import OfferState
from internal.domain.trip import Trip
from internal.handler.app import create_app
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.cascading_dispatch import CascadingDispatchService
from internal.service.matching import MatchingService, NoDriverAvailableError
from internal.service.trip_service import TripService

app = create_app()


def run_cli_demo() -> None:
    print("=" * 85)
    print("UBER MOBILITY ENGINE - MILESTONES 9 & 10: CONCURRENCY LOCK & CASCADING DISPATCH")
    print("=" * 85)

    # --------------------------------------------------------------------------
    # 1. Milestone 9: Optimistic Concurrency Control (OCC) Race Condition Test
    # --------------------------------------------------------------------------
    print("\n[Milestone 9: Concurrency Control - 10 Threads Competing for 1 Lone Driver]")
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    lone_driver = Driver("D-LONE", "Alex Lone", GeoCoordinate(lat=10.7760, lon=106.7000))
    driver_repo.register(lone_driver)
    matching = MatchingService(driver_repo)
    trip_svc = TripService(trip_repo, driver_repo, matching)

    # 10 riders request at the exact same moment
    trip_ids = []
    for i in range(10):
        t, _ = trip_svc.request_trip(
            idempotency_key=f"race-key-{i}",
            rider_id=f"rider-{i}",
            origin=GeoCoordinate(lat=10.7760, lon=106.7000),
            destination=GeoCoordinate(lat=10.8000, lon=106.7200),
        )
        trip_ids.append(t.trip_id)

    winners = []
    lock = threading.Lock()

    def attempt_book(tid: str):
        try:
            _, d, _ = trip_svc.match_and_assign_driver(tid)
            with lock:
                winners.append((tid, d.driver_id))
        except NoDriverAvailableError:
            pass

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(attempt_book, trip_ids))

    print(f"  --> Spawned 10 concurrent threads targeting Driver {lone_driver.driver_id}.")
    print(f"  --> Total successful atomic assignments: {len(winners)}")
    assert len(winners) == 1, "Concurrency invariant violated! Double booking occurred."
    print(f"  [✓] INVARIANT PRESERVED: Exactly 1 thread matched (Trip: {winners[0][0]}). Zero double-bookings.")

    # --------------------------------------------------------------------------
    # 2. Milestone 10: Driver Offer Negotiation & Cascading Dispatch Ring
    # --------------------------------------------------------------------------
    print("\n[Milestone 10: Driver Offer Negotiation & Cascading Dispatch Ring]")
    cascade_trip_repo = InMemoryTripRepository()
    cascade_driver_repo = InMemoryDriverRepository()

    d_near = Driver("D-01", "Driver Alpha (Near)", GeoCoordinate(lat=10.7765, lon=106.7005))
    d_mid = Driver("D-02", "Driver Beta (Mid)", GeoCoordinate(lat=10.7850, lon=106.7120))
    cascade_driver_repo.register(d_near)
    cascade_driver_repo.register(d_mid)

    cascade_svc = CascadingDispatchService(cascade_trip_repo, cascade_driver_repo, default_ttl_seconds=15.0)

    # Rider requests ride
    c_trip = Trip(
        trip_id="TRIP-CASCADE-1",
        rider_id="rider-negotiator",
        origin=GeoCoordinate(lat=10.7760, lon=106.7000),
        destination=GeoCoordinate(lat=10.8000, lon=106.7300),
    )
    cascade_trip_repo.save(c_trip)

    # Step 1: System sends Offer #1 to nearest driver (D-01)
    offer_1 = cascade_svc.dispatch_next_candidate(c_trip.trip_id)
    print(f"  --> Step 1 (Offer Dispatched): Offer ID={offer_1.offer_id} sent to Nearest Candidate: {offer_1.driver_id}")
    print(f"      Offer State: {offer_1.state.value} | Expires in: {offer_1.expires_at - offer_1.created_at:.0f}s")

    # Step 2: Driver D-01 declines
    print(f"  --> Step 2 (Driver Action): Driver {offer_1.driver_id} DECLINES offer!")
    offer_2 = cascade_svc.respond_to_offer(offer_1.offer_id, action="DECLINE")
    print(f"  --> Step 3 (Cascading Triggered): Offer automatically cascaded to Next Candidate: {offer_2.driver_id}")
    assert offer_2.driver_id == "D-02"

    # Step 3: Driver D-02 accepts
    print(f"  --> Step 4 (Driver Action): Driver {offer_2.driver_id} ACCEPTS offer!")
    matched_trip, accepted_offer = cascade_svc.respond_to_offer(offer_2.offer_id, action="ACCEPT")
    print(f"  [✓] Dispatch Cycle Complete! Trip State: {matched_trip.state.value} | Driver Bound: {matched_trip.driver_id}")

    print("\n[✓] Milestones 9 & 10 Fully Operational, Tested & Verified.")
    print("=" * 85)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        run_cli_demo()
