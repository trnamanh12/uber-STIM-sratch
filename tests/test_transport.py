"""
tests/test_transport.py - Integration tests for FastAPI REST Endpoints & WebSocket Telemetry.
"""

from fastapi.testclient import TestClient
import pytest
from internal.domain.driver import Driver, GeoCoordinate
from internal.handler.app import create_app
from internal.repository.driver_repo import InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository
from internal.service.matching import MatchingService
from internal.service.trip_service import TripService


@pytest.fixture
def client_fixture():
    trip_repo = InMemoryTripRepository()
    driver_repo = InMemoryDriverRepository()

    # Seed test driver
    d1 = Driver("D-HCM-01", "Nguyen Van Fast", GeoCoordinate(lat=10.7720, lon=106.6980))
    driver_repo.register(d1)

    matching_service = MatchingService(driver_repo, default_search_radius_km=10.0)
    trip_service = TripService(trip_repo, driver_repo, matching_service)

    app = create_app(trip_service=trip_service, trip_repo=trip_repo, driver_repo=driver_repo)
    client = TestClient(app)
    return client, trip_service


def test_post_trip_success_and_idempotency(client_fixture):
    client, _ = client_fixture

    payload = {
        "idempotency_key": "api-idem-key-100",
        "rider_id": "rider-endpoint-test",
        "origin": {"lat": 10.7760, "lon": 106.7000},
        "destination": {"lat": 10.8000, "lon": 106.7200},
        "passenger_count": 2,
    }

    # First request
    res1 = client.post("/api/v1/trips", json=payload)
    assert res1.status_code == 201
    data1 = res1.json()
    assert "trip_id" in data1
    assert data1["state"] == "REQUESTED"
    assert data1["rider_id"] == "rider-endpoint-test"

    # Second request with identical idempotency key (deduplication)
    res2 = client.post("/api/v1/trips", json=payload)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["trip_id"] == data1["trip_id"]


def test_post_trip_poison_payload_error(client_fixture):
    client, _ = client_fixture

    # Out of bounds latitude: 95.0
    bad_payload = {
        "idempotency_key": "bad-key",
        "rider_id": "rider-bad",
        "origin": {"lat": 95.0, "lon": 106.7000},
        "destination": {"lat": 10.8000, "lon": 106.7200},
        "passenger_count": 1,
    }

    res = client.post("/api/v1/trips", json=bad_payload)
    # FastAPI schema validation catches out-of-bounds at HTTP boundary
    assert res.status_code in {400, 422}


def test_get_trip_and_404_not_found(client_fixture):
    client, _ = client_fixture

    # Query non-existent trip
    res = client.get("/api/v1/trips/trip-does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"] == "TripNotFoundError"


def test_match_driver_and_cancel_trip(client_fixture):
    client, _ = client_fixture

    # 1. Create trip
    payload = {
        "idempotency_key": "match-cancel-key",
        "rider_id": "rider-match",
        "origin": {"lat": 10.7760, "lon": 106.7000},
        "destination": {"lat": 10.8000, "lon": 106.7200},
        "passenger_count": 1,
    }
    trip_data = client.post("/api/v1/trips", json=payload).json()
    trip_id = trip_data["trip_id"]

    # 2. Match driver
    match_res = client.post(f"/api/v1/trips/{trip_id}/match")
    assert match_res.status_code == 200
    match_data = match_res.json()
    assert match_data["driver_id"] == "D-HCM-01"
    assert match_data["trip_state"] == "MATCHED"

    # 3. Cancel trip
    cancel_res = client.post(
        f"/api/v1/trips/{trip_id}/cancel",
        json={"reason": "Changed my mind"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCELLED"

    # 4. Attempt to cancel again (Terminal lock conflict: 409 Conflict)
    cancel_res_2 = client.post(
        f"/api/v1/trips/{trip_id}/cancel",
        json={"reason": "Cancel again"},
    )
    assert cancel_res_2.status_code == 409
    assert cancel_res_2.json()["error"] == "IllegalStateTransitionError"


def test_websocket_telemetry_stream(client_fixture):
    client, _ = client_fixture

    # Create trip
    payload = {
        "idempotency_key": "ws-test-trip",
        "rider_id": "rider-ws",
        "origin": {"lat": 10.7760, "lon": 106.7000},
        "destination": {"lat": 10.8000, "lon": 106.7200},
    }
    trip_id = client.post("/api/v1/trips", json=payload).json()["trip_id"]

    # Connect WebSocket
    with client.websocket_connect(f"/ws/trips/{trip_id}/telemetry") as websocket:
        initial_frame = websocket.receive_json()
        assert initial_frame["trip_id"] == trip_id
        assert initial_frame["state"] == "REQUESTED"


def test_static_web_hud_served(client_fixture):
    client, _ = client_fixture
    res = client.get("/")
    assert res.status_code == 200
    assert "UBER MOBILITY ENGINE" in res.text
    assert "<canvas id=\"mapCanvas\"" in res.text


def test_static_assets_served(client_fixture):
    client, _ = client_fixture
    res_css = client.get("/styles.css")
    assert res_css.status_code == 200
    assert "bottom-sheet" in res_css.text

    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    assert "UberMapEngine" in res_js.text

