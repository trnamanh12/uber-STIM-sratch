"""
internal/handler/app.py - FastAPI Application Factory, REST Endpoints & WebSocket Telemetry.
"""

import asyncio
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from internal.domain.driver import Driver, GeoCoordinate
from internal.domain.trip import (
    IllegalStateTransitionError,
    InvariantViolationError,
    PoisonPayloadError,
    Trip,
    TripState,
)
from internal.handler.schemas import (
    CancelTripRequest,
    GeoCoordinateSchema,
    MatchDriverResponse,
    TripCreateRequest,
    TripResponse,
)
from internal.repository.driver_repo import DriverRepository, InMemoryDriverRepository
from internal.repository.trip_repo import InMemoryTripRepository, TripRepository
from internal.service.matching import MatchingService, NoDriverAvailableError
from internal.service.trip_service import TripNotFoundError, TripService


def create_app(
    trip_service: Optional[TripService] = None,
    trip_repo: Optional[TripRepository] = None,
    driver_repo: Optional[DriverRepository] = None,
) -> FastAPI:
    """FastAPI Application Factory with explicit dependency injection."""
    app = FastAPI(
        title="Uber Mobility Platform API",
        version="1.0.0",
        description="Autonomous Uber Mobility Engine REST & WebSocket Telemetry API",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize default dependencies if not injected
    _trip_repo = trip_repo or InMemoryTripRepository()
    _driver_repo = driver_repo or InMemoryDriverRepository()

    # Pre-seed some default drivers if repository is empty
    if not _driver_repo.list_all():
        _driver_repo.register(Driver("D-01", "Alex Chen", GeoCoordinate(lat=10.7720, lon=106.6980)))
        _driver_repo.register(Driver("D-02", "Bao Nguyen", GeoCoordinate(lat=10.7850, lon=106.7120)))
        _driver_repo.register(Driver("D-03", "Carlos Silva", GeoCoordinate(lat=10.8200, lon=106.7500)))

    matching_service = MatchingService(_driver_repo, default_search_radius_km=15.0)
    _trip_service = trip_service or TripService(_trip_repo, _driver_repo, matching_service)

    # Store in app state
    app.state.trip_service = _trip_service
    app.state.trip_repo = _trip_repo
    app.state.driver_repo = _driver_repo

    # --------------------------------------------------------------------------
    # Exception Handlers: Domain Exceptions -> Standard HTTP Status Codes
    # --------------------------------------------------------------------------
    @app.exception_handler(PoisonPayloadError)
    async def poison_payload_handler(request: Request, exc: PoisonPayloadError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "PoisonPayloadError", "detail": str(exc)},
        )

    @app.exception_handler(TripNotFoundError)
    async def trip_not_found_handler(request: Request, exc: TripNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "TripNotFoundError", "detail": str(exc)},
        )

    @app.exception_handler(NoDriverAvailableError)
    async def no_driver_handler(request: Request, exc: NoDriverAvailableError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "NoDriverAvailableError", "detail": str(exc)},
        )

    @app.exception_handler(IllegalStateTransitionError)
    async def illegal_state_handler(request: Request, exc: IllegalStateTransitionError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "IllegalStateTransitionError", "detail": str(exc)},
        )

    @app.exception_handler(InvariantViolationError)
    async def invariant_violation_handler(request: Request, exc: InvariantViolationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "InvariantViolationError", "detail": str(exc)},
        )

    # --------------------------------------------------------------------------
    # Helper to map Domain Trip to Pydantic Response Schema
    # --------------------------------------------------------------------------
    def to_trip_response(t: Trip) -> TripResponse:
        return TripResponse(
            trip_id=t.trip_id,
            rider_id=t.rider_id,
            driver_id=t.driver_id,
            state=t.state.value,
            origin=GeoCoordinateSchema(lat=t.origin.lat, lon=t.origin.lon),
            destination=GeoCoordinateSchema(lat=t.destination.lat, lon=t.destination.lon),
            current_position=GeoCoordinateSchema(lat=t.current_lat, lon=t.current_lon),
            distance_km=round(t.distance_km, 3),
            duration_seconds=round(t.duration_seconds, 1),
            fare=round(t.fare, 2),
            cancel_reason=t.cancel_reason,
        )

    # --------------------------------------------------------------------------
    # REST Endpoints
    # --------------------------------------------------------------------------
    @app.post("/api/v1/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
    def request_trip(req: TripCreateRequest):
        svc: TripService = app.state.trip_service
        origin_coord = GeoCoordinate(lat=req.origin.lat, lon=req.origin.lon)
        dest_coord = GeoCoordinate(lat=req.destination.lat, lon=req.destination.lon)

        trip, is_dup = svc.request_trip(
            idempotency_key=req.idempotency_key,
            rider_id=req.rider_id,
            origin=origin_coord,
            destination=dest_coord,
            passenger_count=req.passenger_count,
        )
        return to_trip_response(trip)

    @app.get("/api/v1/trips/{trip_id}", response_model=TripResponse)
    def get_trip(trip_id: str):
        svc: TripService = app.state.trip_service
        trip = svc.get_trip(trip_id)
        return to_trip_response(trip)

    @app.post("/api/v1/trips/{trip_id}/match", response_model=MatchDriverResponse)
    def match_driver(trip_id: str):
        svc: TripService = app.state.trip_service
        trip, driver, eta_min = svc.match_and_assign_driver(trip_id)
        return MatchDriverResponse(
            trip_id=trip.trip_id,
            driver_id=driver.driver_id,
            driver_name=driver.name,
            eta_minutes=eta_min,
            trip_state=trip.state.value,
        )

    @app.post("/api/v1/trips/{trip_id}/cancel", response_model=TripResponse)
    def cancel_trip(trip_id: str, req: CancelTripRequest):
        svc: TripService = app.state.trip_service
        trip = svc.cancel_trip(trip_id, reason=req.reason)
        return to_trip_response(trip)

    # --------------------------------------------------------------------------
    # Real-Time WebSocket Telemetry Stream (1Hz / State Streaming)
    # --------------------------------------------------------------------------
    @app.websocket("/ws/trips/{trip_id}/telemetry")
    async def trip_telemetry_stream(websocket: WebSocket, trip_id: str):
        await websocket.accept()
        svc: TripService = app.state.trip_service

        try:
            trip = svc.get_trip(trip_id)
        except TripNotFoundError:
            await websocket.send_json({"error": "TripNotFoundError", "trip_id": trip_id})
            await websocket.close()
            return

        try:
            # Send initial state snapshot
            await websocket.send_json(to_trip_response(trip).model_dump())

            # If trip is not started or already matched, auto-simulate transit forward if requested
            while True:
                # Refresh trip from repository
                trip = svc.get_trip(trip_id)

                # Send live snapshot
                await websocket.send_json(to_trip_response(trip).model_dump())

                if trip.state in {TripState.COMPLETED, TripState.CANCELLED}:
                    # Reached terminal state
                    break

                # Check if client sent any command (non-blocking with timeout)
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    cmd = data.get("action")
                    if cmd == "start":
                        if trip.state == TripState.MATCHED:
                            svc.driver_arrived_at_pickup(trip_id)
                            trip = svc.start_trip(trip_id)
                    elif cmd == "step":
                        if trip.state == TripState.IN_TRANSIT:
                            # Advance driver closer to destination
                            dlat = (trip.destination.lat - trip.current_lat) * 0.25
                            dlon = (trip.destination.lon - trip.current_lon) * 0.25
                            new_lat = trip.current_lat + dlat
                            new_lon = trip.current_lon + dlon
                            if abs(new_lat - trip.destination.lat) < 0.001:
                                trip = svc.drop_off_rider(trip_id)
                                trip = svc.complete_trip(trip_id)
                            else:
                                trip = svc.update_telemetry(trip_id, new_lat, new_lon, 0.5, 30.0)
                except asyncio.TimeoutError:
                    # 1Hz Heartbeat tick if no client input
                    pass

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await websocket.send_json({"error": str(exc)})
            except Exception:
                pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    # Mount static client UI at root
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")
    if os.path.exists(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app
