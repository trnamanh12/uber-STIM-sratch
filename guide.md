# The Evolutionary Architecture Playbook
### How to Grow Complex Systems from First Principles Without Analysis Paralysis

> *"A complex system that works is invariably found to have evolved from a simple system that worked. A complex system designed from scratch never works and cannot be patched up to make it work. You have to start over with a working simple system."*  
> — **John Gall (Gall’s Law)**

---

## Executive Summary & Purpose

This guide is an end-to-end operational blueprint for **software engineers** and **autonomous AI agents**. It bridges the gap between high-level system requirements and ground-level execution, teaching you:
1. **The Psychology of Architecture:** How to eliminate the "Architect’s Illusion" and avoid mental shutdown when confronted with massive PRDs.
2. **The First-Principles Model of Computing:** Why all systems reduce to four elementary operations, and why modern tooling (caches, message queues, microservices) are merely earned band-aids.
3. **Failure-First Engineering:** How to design resilient systems by following a single packet through its lifecycle and asking four fatal questions.
4. **The Agent Execution Protocol:** An invariant-driven, step-by-step methodology to grow any software system incrementally from a 15-minute "walking skeleton" to a production-grade platform.

---

# Part I: The Psychology of Systems Design

```
   ┌────────────────────────────────────────────────────────┐
   │                  THE ARCHITECT'S ILLUSION              │
   │  "I must design the entire 900-line PRD upfront:      │
   │   H3 indexing, WebSockets, Dijkstra, ISO 26262..."     │
   └───────────────────────────┬────────────────────────────┘
                               │ Triggers
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │             COGNITIVE OVERLOAD (7±2 SLOTS)             │
   │  Working memory exhausts. Fear of making mistakes.     │
   └───────────────────────────┬────────────────────────────┘
                               │ Leads to
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                  ANALYSIS PARALYSIS                    │
   │  Endless reading, diagramming, and zero running code.   │
   └───────────────────────────┬────────────────────────────┘
                               │ THE CURE: Gall's Law
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │               THE 15-MINUTE WALKING SKELETON           │
   │  A crude, running loop with zero dependencies.         │
   │  Defeats the blank page. Fog of war clears.           │
   └────────────────────────────────────────────────────────┘
```

## 1. The Three Traps of the Developing Architect

When confronted with complex projects—such as autonomous navigation engines, high-throughput trading systems, or distributed databases—engineers frequently stall. This is not an intellectual deficiency; it is an evolutionary response to unbounded complexity.

### Trap A: The "Architect’s Illusion" (Needing a Master Plan First)
* **The Illusion:** You inspect a polished, battle-tested system (e.g., `direction-eval` with its kinematic look-ahead filters, H3 spatial corridors, ISO 26262 ASIL-B safety invariants, and binary WebSocket streaming) and subconsciously hallucinate that a senior architect sat down on Day 1 and drafted the entire architecture from top to bottom.
* **The Reality:** **Nobody does that.** World-class systems start as embarrassingly naive, single-file scripts. They evolve through continuous pressure, unit tests, bug fixes, and refactoring.
* **The Rule:** Architecture is not an immutable blueprint etched in stone; it is an **empirical hypothesis**. Your first milestone is not elegance; it is **observable existence**.

### Trap B: Swallowing the Ocean (Cognitive Bandwidth Overload)
* Human working memory can hold only **4 to 7 distinct concepts** simultaneously (Miller's Law / Cowan's limit).
* If you attempt to juggle geospatial geodesics (Haversine, Vincenty), edge-expanded graph routing, 1Hz WebSocket heartbeat reconnection, ASIL-B fail-safe constraints, and frontend UI timers in your active memory at once, your prefrontal cortex triggers a hard shutdown: **avoidance and exhaustion**.
* **The Antidote:** Partition the domain. Discard 90% of the requirements on Day 1. Work only on what can fit into a single mental function.

### Trap C: Conflating "Learning" with "Consuming Information"
* Binge-reading whitepapers, PRDs, and documentation creates a dopamine surge that mimics progress. However, it generates an accumulation of **untested, speculative knowledge**.
* Architectural mastery is not gained by staring at the map. It is gained by **clearing the fog of war one tile at a time with code that executes, fails, and passes**.

---

# Part II: First Principles of Computing Systems

Strip away the framework hype, vendor marketing, and technical buzzwords. At the silicon and network layer, **every single software system on Earth does only four things**:

```
 ┌──────────────┐      ┌─────────────────────────┐      ┌──────────────┐
 │ 1. INGEST    │ ───► │ 2. ENFORCE & TRANSFORM  │ ───► │ 3. PERSIST   │
 │ Raw Input    │      │ Invariants & Domain Ops │      │ State Storage│
 └──────────────┘      └─────────────────────────┘      └──────────────┘
                               │
                               ▼
                       ┌──────────────┐
                       │ 4. EGRESS    │
                       │ Response/Out │
                       └──────────────┘
```

1. **Ingest (Data In):** Accepts raw bytes or payloads from an untrusted external entity (HTTP request, WebSocket frame, sensor packet, CLI arg).
2. **Enforce & Transform (Business Invariants):** Validates the payload structure, enforces inviolable rules, and computes transitions.
3. **Persist (State):** Records state changes to durable medium (disk, database, append-only log, memory cell) so state survives termination.
4. **Egress (Data Out):** Dispatches a deterministic signal back to the environment (JSON response, binary frame, motor command, terminal log).

## The Band-Aid Fallacy: Earn Your Complexity

Every other layer you encounter—caches, message brokers, worker pools, microservices, container orchestrators—is not primary architecture. They are **band-aids** introduced to solve two engineering bottlenecks:
1. **Running out of speed** (Latency / Throughput saturation).
2. **Things crashing** (Fault domains / Hardware instability).

| Fancy Tool | The Core Problem It Band-Aids | When to Adopt It |
| :--- | :--- | :--- |
| **Redis / Memcached** | Database disk queries are too slow. | When DB queries measurably exceed latency budgets under load. |
| **RabbitMQ / Kafka / Celery** | Main thread blocks waiting for I/O (emails, video rendering). | When synchronous request-response times out or chokes throughput. |
| **Microservices** | Engineering team coordination overhead / blast radius. | When 50+ engineers collide on a single deploy pipeline. |
| **H3 / Spatial Indexing** | $O(N)$ brute-force distance scans scale terribly. | When coordinate array scans exceed the tick budget ($>10\text{ms}$). |

> [!IMPORTANT]
> **The Golden Law of Complexity:** Never add an architectural dependency to solve a problem you have not yet measured in running code. Keep the system aggressively dumb until reality demands sophistication.

---

# Part III: The 4-Question Data Lifecycle

To architect a feature or system, do not sketch 15 microservices. Take **one single packet of data** (e.g., a driver location ping, a checkout request, a search term) and trace its complete journey from entry to rest. Interrogate it with the **Four Fatal Questions**:

```
                       [ Incoming Data Packet ]
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────┐
         │ Q1: WHAT IF THE PACKET IS POISON?                │
         │ - Null bytes, negative timestamps, NaN values    │
         │ -> Action: Parse at border, don't validate deep  │
         └────────────────────────┬─────────────────────────┘
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────┐
         │ Q2: WHAT IF THE SERVER DIES HALFWAY?             │
         │ - DB wrote, but notification did not fire        │
         │ -> Action: Atomic transitions, WAL, Crash-only   │
         └────────────────────────┬─────────────────────────┘
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────┐
         │ Q3: WHAT IF THIS PACKET ARRIVES TWICE?           │
         │ - Network retry storm, double-click payment      │
         │ -> Action: Idempotency keys, state transition locks│
         └────────────────────────┬─────────────────────────┘
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────┐
         │ Q4: HOW WILL I KNOW WHEN IT BREAKS IN SILENCE?   │
         │ - Corrupted state, drift, silent drops           │
         │ -> Action: Invariant assertions, structured logs │
         └──────────────────────────────────────────────────┘
```

### 1. What if incoming data is poison?
* **Problem:** Attackers and buggy clients send malformed data: strings where floats belong, coordinates in Antarctica, negative prices, empty bodies.
* **Defense:** **Parse, don't validate.** Strip away structural uncertainty at the transport boundary (via Pydantic, Zod, or Protobuf). Do not allow untyped dictionaries into your domain core.

### 2. What if the machine dies halfway through?
* **Problem:** The server writes a booking to the database, but loses power before emitting the dispatch event. Upon reboot, the system is in an inconsistent state.
* **Defense:** Design for **Crash-Only Software**. Transactions must be atomic. If a multi-step operation fails halfway, the system must recover state purely by inspecting its persistent log upon startup.

### 3. Can this run twice by accident?
* **Problem:** A mobile app loses cellular signal after sending a payment request. The client retries automatically. Did you charge the user twice?
* **Defense:** **Idempotency.** Every mutation must carry an idempotency key or be guarded by a state machine where `STATE_A -> STATE_B` can happen only once. Repeated identical requests must yield identical results without side-effects.

### 4. How will I know when it breaks in silence?
* **Problem:** The code does not throw an exception, but vehicle coordinates are drifting, or waypoints are being dropped silently.
* **Defense:** **Invariants & Observability.** Embed runtime invariants (`assert target_destination == original_destination`). Emit structured logs containing correlation IDs and domain states at every transition.

---

# Part IV: The 4-Step Mental Algorithm

When standing before any new project, feature, or assignment, apply this deterministic algorithm:

```
  [ Big Scary PRD / Architecture Problem ]
                     │
                     ▼
  ┌──────────────────────────────────────┐
  │ Step 1: Ruthlessly De-scope          │ ──► Cut scope until embarrassingly simple
  └──────────────────┬───────────────────┘
                     ▼
  ┌──────────────────────────────────────┐
  │ Step 2: Build a Walking Skeleton     │ ──► Thin wire end-to-end (Terminal loop)
  └──────────────────┬───────────────────┘
                     ▼
  ┌──────────────────────────────────────┐
  │ Step 3: Kent Beck's Trinity          │
  │   1. Make it WORK (Naive code)       │ ──► First test green
  │   2. Make it RIGHT (Clean boundaries)│ ──► Enforce invariants, decouple layers
  │   3. Make it FAST (Only if profiled) │ ──► Spatial indices, caches, concurrency
  └──────────────────┬───────────────────┘
                     ▼
  ┌──────────────────────────────────────┐
  │ Step 4: Anchor in Invariants         │ ──► Preserve domain rules, ignore plumbing
  └──────────────────────────────────────┘
```

### Step 1: Ruthlessly De-scope Until It Feels "Too Simple"
If you don't know where to begin, **the task is too large**.
* Cut it in half.
* Cut it in half again.
* Cut until you feel slightly embarrassed by how trivial it looks.
* *Wrong starting point:* "I will build a dynamic multi-leg navigation routing engine with WebSockets, turn penalties, and React UI."
* *Right starting point:* "Can I write a 10-line Python script where a scalar $x=0$ moves toward $x=100$ in a `while` loop and prints 'Arrived'?"

### Step 2: Build the "Walking Skeleton" (The Tracer Bullet)
A Walking Skeleton is a minimal implementation that connects the ultimate inputs to the ultimate outputs with zero flesh on its bones:
1. No database (use an in-memory dictionary or list).
2. No framework (use a plain function or terminal loop).
3. No external APIs (hardcode dummy values).
4. No UI (use `print()` or standard output).

> **Why this works:** Once the skeleton lives, you have crossed the chasm from *speculation* to *iteration*. You are no longer creating from scratch; you are refactoring an existing, working program.

### Step 3: Follow Kent Beck's Trinity
Never attempt all three at once:
1. **Make it Work:** Write the simplest, ugliest code that satisfies the test. Hardcode constants, write inline `if/else`, skip abstractions.
2. **Make it Right:** Refactor. Extract domain classes, decouple transport from business rules, establish strict type signatures, and add invariants.
3. **Make it Fast:** Profile with real workloads. Only introduce caches, indexes, or asynchronous workers where measurements prove a bottleneck.

### Step 4: Anchor in Invariants, Not Technologies
Technologies (FastAPI, Redis, PostgreSQL, Kafka, React) are ephemeral plumbing. They change across years and projects.
To maintain absolute mental clarity, anchor your design strictly in:
1. **What is the Current State?** (e.g., `EN_ROUTE`, `AT_WAYPOINT`, `COMPLETED`).
2. **What Event Occurred?** (e.g., `GPS_PING_RECEIVED`, `WAYPOINT_MISSED`).
3. **What Invariant Must Never Break?** (e.g., "The vehicle must never arrive at the destination before visiting all mandatory intermediate waypoints").

---

# Part V: Architectural Boundaries (Clean Layering)

To build software that does not rot into spaghetti, maintain strict boundaries based on business capability:

```
  [ External World / Client / Browser ]
                    │
                    ▼
  ┌──────────────────────────────────────┐
  │ 1. TRANSPORT / HANDLER LAYER         │
  │    - FastAPI, WebSockets, CLI        │
  │    - Request deserialization         │
  │    - Status code / Error mapping     │
  └──────────────────┬───────────────────┘
                     │ (Calls)
                     ▼
  ┌──────────────────────────────────────┐
  │ 2. APPLICATION / SERVICE LAYER       │
  │    - Workflow orchestration          │
  │    - Coordinates domain & storage    │
  │    - Transaction boundaries          │
  └──────────┬───────────────────┬───────┘
             │ (Invokes)         │ (Uses)
             ▼                   ▼
  ┌───────────────────┐ ┌────────────────┐
  │ 3. DOMAIN CORE    │ │ 4. PERSISTENCE │
  │    - Pure Logic   │ │    & ADAPTERS  │
  │    - State Machine│ │    - DB repos  │
  │    - Invariants   │ │    - 3rd party │
  │    (Zero 3P Deps) │ │      APIs      │
  └───────────────────┘ └────────────────┘
```

### Boundary Responsibilities

| Layer | Primary Duty | Absolute Prohibition |
| :--- | :--- | :--- |
| **Domain Core** | Business rules, state transitions, mathematical invariants. | **Never** import database drivers, HTTP frameworks, or UI libraries. Must run in pure Python/Go/TS. |
| **Application / Service** | Orchestrates use cases: fetches entities from storage, invokes domain logic, commits transactions. | **Never** parse HTTP headers directly or execute raw SQL outside repository abstractions. |
| **Transport / Handler** | Translates wire protocols (JSON, Protobuf) into typed requests, calls services, formats responses. | **Never** enforce business rules or make algorithmic decisions here. |
| **Persistence / Adapter** | Implements domain storage contracts against real infrastructure (PostgreSQL, Redis, OSM API). | **Never** dictate business policies. |

---

# Part VI: Step-by-Step Case Study: Building a Mobility Navigation Engine

To see this playbook in action, let us trace how a production-grade system (inspired by `direction-eval`) is built over 6 iterative stages without panic.

```
  Day 1: Scalar Loop ────► Day 2: Waypoint State ────► Day 3: Destination Invariant
        │                         │                           │
        ▼                         ▼                           ▼
  Day 6: Web Canvas  ◄──── Day 5: WebSocket API  ◄──── Day 4: Missed-Waypoint Recovery
```

---

### Day 1: The 15-Minute Walking Skeleton
* **Goal:** A running loop that updates position toward a target and terminates correctly.
* **Flesh:** Zero. No map, no Leaflet, no network, no database. Just pure logic in a terminal.

```python
# day1_skeleton.py
import time

def run_trip():
    state = "NAVIGATING"
    car_x = 0
    dest_x = 100

    print(f"[*] Trip started. Origin: {car_x}, Destination: {dest_x}")
    while car_x < dest_x:
        car_x += 20
        time.sleep(0.1)
        print(f"    -> Telemetry: Car at {car_x} | State: {state}")

    state = "COMPLETED"
    print(f"[✓] {state}: Car arrived at {dest_x}")

if __name__ == "__main__":
    run_trip()
```
*Takeaway:* The blank page is conquered. You have a runnable baseline.

---

### Day 2: Introduce Multi-Leg State Transitions
* **Goal:** Introduce an intermediate waypoint without corrupting the trip structure.
* **Mechanism:** Model a minimal explicit state machine.

```python
# day2_state_machine.py
from enum import Enum

class TripState(str, Enum):
    LEG_1 = "NAVIGATING_TO_WAYPOINT"
    AT_WAYPOINT = "DWELLING_AT_WAYPOINT"
    LEG_2 = "NAVIGATING_TO_DESTINATION"
    COMPLETED = "COMPLETED"

def run_multi_leg_trip():
    car_x = 0
    waypoint_x = 40
    dest_x = 100
    state = TripState.LEG_1

    print(f"[*] Multi-leg trip initiated. Target 1: {waypoint_x}, Final: {dest_x}")

    while state != TripState.COMPLETED:
        if state == TripState.LEG_1:
            car_x += 15
            if car_x >= waypoint_x:
                car_x = waypoint_x
                state = TripState.AT_WAYPOINT
                print(f"    [!] Arrived at Waypoint ({car_x}). Switching state: {state}")
        elif state == TripState.AT_WAYPOINT:
            print("    [!] Loading passengers / package...")
            state = TripState.LEG_2
        elif state == TripState.LEG_2:
            car_x += 20
            if car_x >= dest_x:
                car_x = dest_x
                state = TripState.COMPLETED
                print(f"    [✓] Arrived at Final Destination ({car_x}).")

if __name__ == "__main__":
    run_multi_leg_trip()
```

---

### Day 3: Invariant Hardening (The Safety Net)
* **Goal:** Guarantee that dynamic changes (e.g. adding or modifying stops) can never overwrite or corrupt the final destination.
* **Mechanism:** Introduce Domain Invariant checks.

```python
# day3_invariants.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TripTarget:
    destination_x: float
    waypoint_x: float

class NavigationEngine:
    def __init__(self, target: TripTarget):
        self._target = target
        self._car_x = 0.0
        # Invariant: Waypoint must lie between origin and destination
        assert 0 < target.waypoint_x < target.destination_x, "Invariant Broken: Waypoint out of corridor bounds!"

    def step(self, delta: float):
        # Invariant verification before mutation
        self._verify_invariants()
        self._car_x += delta
        self._verify_invariants()

    def _verify_invariants(self):
        # Destination integrity assertion: Destination can NEVER mutate
        assert self._target.destination_x == 100.0, "FATAL: Destination corrupted during trip execution!"
        assert self._car_x >= 0.0, "FATAL: Negative coordinate anomaly!"

    @property
    def position(self) -> float:
        return self._car_x
```
*Takeaway:* Invariants prevent subtle, silent regressions. You don't need a 20-page safety spec to write your first safety invariant.

---

### Day 4: Handling Edge Cases (Missed Waypoint Recovery)
* **Goal:** What if the car drives past the waypoint without stopping?
* **Mechanism:** Add kinematic distance monitoring and dynamic recalculation.

```python
# day4_recovery.py
def evaluate_waypoint_progress(car_x: float, waypoint_x: float, threshold: float = 15.0):
    """
    If the vehicle has passed the waypoint and distance is increasing,
    trigger automatic waypoint pruning and re-route to destination.
    """
    overshoot = car_x - waypoint_x
    if overshoot > threshold:
        print(f"[WARN] Waypoint at {waypoint_x} missed by {overshoot}m! Pruning stop...")
        return "PRUNE_AND_REROUTE"
    return "CONTINUE"
```

---

### Day 5: Wrap in Transport (FastAPI / WebSocket Streaming)
* **Goal:** Expose the engine to the outside world without coupling domain logic to network protocols.
* **Mechanism:** The domain engine remains pure. A FastAPI handler wraps it and yields serialized telemetry.

```python
# day5_transport.py
from fastapi import FastAPI, WebSocket
import asyncio

app = FastAPI()

@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket):
    await websocket.accept()
    car_x = 0.0
    dest_x = 100.0
    
    try:
        while car_x < dest_x:
            car_x += 10.0
            payload = {
                "car_x": car_x,
                "dest_x": dest_x,
                "status": "NAVIGATING" if car_x < dest_x else "ARRIVED"
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.5)
    except Exception as exc:
        print(f"Client disconnected or stream error: {exc}")
    finally:
        await websocket.close()
```

---

### Day 6: Connect an Explorable Client UI
* **Goal:** Render the streaming state visually to verify user behavior.
* **Mechanism:** A single lightweight HTML/Canvas page that connects to `/ws/telemetry` and renders a moving dot.

```html
<!-- day6_index.html -->
<!DOCTYPE html>
<html>
<head><title>Vehicle Telemetry HUD</title></head>
<body style="font-family: monospace; background: #111; color: #eee; padding: 20px;">
  <h2>Vehicle Navigation Stream</h2>
  <div id="status">Connecting...</div>
  <canvas id="track" width="600" height="80" style="border: 1px solid #444; margin-top: 10px;"></canvas>
  <script>
    const canvas = document.getElementById("track");
    const ctx = canvas.getContext("2d");
    const ws = new WebSocket("ws://localhost:8000/ws/telemetry");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      document.getElementById("status").innerText = `Pos: ${data.car_x} / ${data.dest_x} | Status: ${data.status}`;
      
      // Render
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const px = (data.car_x / data.dest_x) * (canvas.width - 40) + 20;
      ctx.fillStyle = "#00ff88";
      ctx.beginPath();
      ctx.arc(px, 40, 12, 0, 2 * Math.PI);
      ctx.fill();
    };
  </script>
</body>
</html>
```

---

### Day 7+: Earning Complexity
Only now—when you have an end-to-end working system—do you consider:
1. **Spatial Corridors:** Replacing simple 1D scalars with 2D coordinates and H3 hexagon indices.
2. **Graph Routing:** Replacing straight-line delta steps with edge-expanded Dijkstra or A*.
3. **High-Load Telemetry:** Replacing JSON WebSockets with Protobuf binary streams.

Each upgrade is applied to a **healthy, running system** where tests immediately alert you if an invariant breaks.

---

# Part VII: The Autonomous Agent Operational Protocol

When an AI agent is instructed to build a feature or an entire project, it must adhere to this strict step-by-step operational protocol:

### Directive 1: Never Generate Multi-File Scaffolding First
* **Violation:** Generating 12 empty files (`models/`, `services/`, `controllers/`, `schemas/`, `config/`) before a single executable line runs.
* **Rule:** The agent’s first deliverable must be a single runnable file or a focused unit test proving the fundamental loop.

### Directive 2: The 3-File Day 1 Sandbox
On Day 1 of any project, limit the workspace to at most three files:
1. `core.py` (The naive domain engine and state transitions).
2. `test_core.py` (The domain unit test asserting invariants).
3. `main.py` (The executable entry point demonstrating the loop).

### Directive 3: The 4-Question Gate for Every Feature
Before opening a pull request or declaring a feature complete, the agent must verify:
* [ ] **Poison Input Test:** Did I feed invalid, boundary, or null data to the entry point and verify it fails gracefully without crashing the runtime?
* [ ] **Partial Failure Test:** If an exception occurs in the middle of execution, is persistent state clean or safely recoverable?
* [ ] **Idempotency Test:** If this function or endpoint is called twice with the exact same payload, does it preserve invariant integrity?
* [ ] **Silent Failure Check:** Are there broad `except: pass` or unlogged branches hiding runtime defects?

### Directive 4: Bounded Step Verification Loop
Follow the feedback sequence:
$$\text{Typecheck / Lint} \longrightarrow \text{Focused Unit Test} \longrightarrow \text{Integration Wire} \longrightarrow \text{Commit}$$
Never jump straight to end-to-end testing before verifying structural correctness at the cheapest possible layer.

---

# Part VIII: Learning From Real-World Breakages

Tutorials are dangerous because they teach exclusively through "happy paths"—scenarios where the network never hiccups, users never enter garbage, and disks never fill up. Real-world architecture begins where tutorials end.

### The 5 Essential Research Queries
Whenever you are about to adopt a new technology or architecture pattern, run these five targeted queries first:
1. `"postmortem [technology/pattern]"` *(e.g., "postmortem websocket streaming")*
2. `"why we abandoned [technology]"` *(e.g., "why we abandoned microservices")*
3. `"common pitfalls in [domain]"` *(e.g., "common pitfalls in geospatial route matching")*
4. `"things I wish I knew before building [system]"`
5. `"[technology] latency degradation in production"`

By studying the documented failures of previous engineering teams, you convert dangerous **unknown unknowns** into manageable **design constraints** before writing a single line of production code.

---

## The Engineer's Oath

> 1. I will not seek a perfect master plan; I will create a simple working system and evolve it.
> 2. I will not hold the entire system in my head; I will isolate boundaries and rely on invariants.
> 3. I will connect the start to the end on Day 1 with a thin wire.
> 4. I will make it work, then make it right, and only make it fast when profiled.
> 5. I will earn my complexity.
