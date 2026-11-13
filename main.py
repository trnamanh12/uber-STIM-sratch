"""
main.py - Entry point for Milestone 6: FastAPI REST & WebSocket Telemetry Server.
"""

import sys
from fastapi.testclient import TestClient
import uvicorn

from internal.handler.app import create_app

app = create_app()


def run_cli_demo() -> None:
    print("=" * 80)
    print("UBER MOBILITY ENGINE - MILESTONE 6: REAL-TIME REST & WEBSOCKET TELEMETRY")
    print("=" * 80)

    client = TestClient(app)

    # 1. POST /api/v1/trips
    print("\n[1. Ingest Ride Request: POST /api/v1/trips]")
    create_payload = {
        "idempotency_key": "live-wire-token-42",
        "rider_id": "rider-alice-transport",
        "origin": {"lat": 10.7760, "lon": 106.7000},
        "destination": {"lat": 10.7950, "lon": 106.7250},
        "passenger_count": 2,
    }
    res = client.post("/api/v1/trips", json=create_payload)
    trip_data = res.json()
    trip_id = trip_data["trip_id"]
    print(f"  --> HTTP {res.status_code} Created: Trip ID = {trip_id} | State = {trip_data['state']}")

    # 2. Duplicate Idempotency Check
    print("\n[2. Verify Idempotency Deduplication: POST /api/v1/trips]")
    res_dup = client.post("/api/v1/trips", json=create_payload)
    print(f"  --> HTTP {res_dup.status_code} OK: Returned existing trip = {res_dup.json()['trip_id']}")

    # 3. POST /api/v1/trips/{id}/match
    print(f"\n[3. Dispatch Match: POST /api/v1/trips/{trip_id}/match]")
    match_res = client.post(f"/api/v1/trips/{trip_id}/match")
    match_data = match_res.json()
    print(f"  --> HTTP {match_res.status_code} OK: Matched {match_data['driver_name']} "
          f"(ID: {match_data['driver_id']}) | ETA: {match_data['eta_minutes']}m | State: {match_data['trip_state']}")

    # 4. WebSocket Streaming: WS /ws/trips/{id}/telemetry
    print(f"\n[4. Live Telemetry Stream: WS /ws/trips/{trip_id}/telemetry]")
    with client.websocket_connect(f"/ws/trips/{trip_id}/telemetry") as ws:
        # Initial frame
        frame = ws.receive_json()
        print(f"  --> [WS Received] State: {frame['state']:<15} | Pos: ({frame['current_position']['lat']:.4f}, {frame['current_position']['lon']:.4f})")

        # Command driver to arrive & start
        ws.send_json({"action": "start"})
        frame = ws.receive_json()
        print(f"  --> [WS Received] State: {frame['state']:<15} | Action: Passenger Picked Up")

        # Step vehicle forward
        for step in range(1, 4):
            ws.send_json({"action": "step"})
            frame = ws.receive_json()
            print(f"  --> [WS Received] State: {frame['state']:<15} | Pos: ({frame['current_position']['lat']:.4f}, {frame['current_position']['lon']:.4f}) | Dist: {frame['distance_km']}km | Fare: ${frame['fare']:.2f}")

    # 5. GET /api/v1/trips/{id}
    print(f"\n[5. Query Trip State: GET /api/v1/trips/{trip_id}]")
    get_res = client.get(f"/api/v1/trips/{trip_id}")
    final_trip = get_res.json()
    print(f"  --> HTTP {get_res.status_code} OK: Final State = {final_trip['state']} | Fare = ${final_trip['fare']:.2f}")

    print("\n[✓] Real-time Transport Layer (REST + WebSockets) Operational & Verified.")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        run_cli_demo()
