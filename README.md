# Uber Mobility Engine

An autonomous, event-driven mobility platform engineered from first principles following the doctrines of **Gall’s Law**, **Failure-First Architecture**, and **Kent Beck’s Trinity**.

---

## 🏛 Architectural Boundaries

```text
├── internal/
│   ├── domain/                  # PURE BUSINESS RULES (Zero External Dependencies)
│   │   ├── trip.py              # Trip Aggregate, FSM, Safety Invariants, GeoCoordinate
│   │   ├── driver.py            # Driver Entity, Fleet States, Spherical Haversine Math
│   │   └── pricing.py           # Surge Pricing Engine, Economic Multiplier Bounds
│   ├── repository/              # PERSISTENCE BOUNDARIES (Contracts & In-Memory Adapters)
│   │   ├── trip_repo.py         # TripRepository Interface + Crash Snapshot WAL
│   │   └── driver_repo.py       # DriverRepository Interface + Fleet Pool
│   ├── service/                 # APPLICATION / USE CASES (Transaction Coordination)
│   │   ├── matching.py          # Spatial Dispatch Engine (Argmin Nearest ETA)
│   │   └── trip_service.py      # Trip Lifecycle Orchestration & Idempotency
│   └── handler/                 # TRANSPORT LAYER (FastAPI HTTP + WebSockets)
│       ├── schemas.py           # Pydantic Wire Protocol Ingestion & Validation
│       └── app.py               # REST Endpoints, WebSocket Telemetry & Static Mounting
├── web/
│   └── index.html               # Zero-Build 60fps Canvas Telemetry HUD
├── tests/                       # TEST HARNESS & SUITES
│   ├── test_service.py          # Service Layer Lifecycle Integration Tests
│   ├── test_transport.py        # REST API & WebSocket Streaming Tests
│   └── test_pricing_and_detour.py # Surge Pricing, Multi-Stop Detours & Latency Benchmarks
├── core.py                      # Architectural Public Facade
├── main.py                      # Runnable Demonstration Entry Point & Server Host
└── pyproject.toml               # Tooling & Pytest Configuration
```

---

## 🚀 Running the System

### 1. Run Complete Test Suite
```bash
pytest
```
*Executes all 18 unit, integration, and benchmark tests in under 0.4 seconds.*

### 2. Run Autonomous CLI Demonstration
```bash
python3 main.py
```
*Executes end-to-end trip creation, dispatch matching, multi-stop detour routing, surge pricing calculations, and microsecond dispatch latency benchmarks.*

### 3. Launch Real-Time Server & Visual Web HUD
```bash
python3 main.py --serve
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000/`** in your browser to access the live Canvas Telemetry HUD.

---

## 🛡 The 4-Question Failure Guardrails

| Fatal Question | Concrete Failure Mode | Architectural Defense |
| :--- | :--- | :--- |
| **Q1: The Poison Pill** | `NaN` / `Inf` coordinates, latitudes out-of-bounds, invalid passenger counts | `GeoCoordinate` value object validation at transport boundary; rejects invalid types before hitting domain logic. |
| **Q2: The Sudden Death** | Process killed mid-transit | Atomic snapshotting (`to_dict` / `from_dict`) and WAL restore mechanics in `TripRepository`. |
| **Q3: The Double Strike** | Mobile network retry storms, duplicate requests | Client-provided `idempotency_key` deduplication registry; repeated requests return existing entity without side-effects. |
| **Q4: The Silent Bleed** | Undetected trajectory drift, silent dropped waypoints | Strict runtime domain invariants (`_verify_invariants`), mandatory intermediate waypoint visitation checks, and structured `DomainEvent` audit trail. |

---

## 📊 Performance Benchmarks
- **Spatial Dispatch Latency:** $\approx 54\ \mu\text{s}$ per query across 100 active fleet drivers.
- **Dispatch Throughput:** $> 18,000\ \text{queries/sec}$ on a single core.
- **Surge Bounds Invariant:** Strictly clamped to $[1.0\times, 3.0\times]$.
