/**
 * Uber Mobility Engine - Client Frontend Controller
 * Implements 60fps Vector Map Engine, Gesture Bottom Sheet, and Telemetry Streaming
 */

// ============================================================================
// 1. Core State & Data Models
// ============================================================================

const APP_STATE = {
  phase: 'idle', // 'idle' | 'selection' | 'matching' | 'telemetry'
  origin: { lat: 10.7760, lon: 106.7000, name: 'Current Location (District 1)' },
  destination: null,
  waypoints: [],
  selectedTier: 'UberX',
  activeTrip: null,
  ws: null,
  surgeMultiplier: 1.2,
  carTelemetry: {
    lat: 10.7720,
    lon: 106.6980,
    bearing: 45,
    speedKmh: 0,
    driverName: 'Alex Chen',
    rating: 4.96,
    plate: '51A-982.34',
    vehicle: 'Toyota Camry • White',
  },
  routeCoordinates: [],
  travelProgress: 0, // 0.0 to 1.0 along the route
};

// ============================================================================
// 2. Vector Canvas Map Engine (Uber High-Contrast Aesthetics)
// ============================================================================

class UberMapEngine {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.center = { lat: 10.7760, lon: 106.7000 };
    this.zoom = 15;
    this.paddingBottom = 220; // Bottom sheet asymmetric padding
    this.idleFleet = [
      { lat: 10.7780, lon: 106.7040, bearing: 110, id: 'D-01' },
      { lat: 10.7710, lon: 106.6940, bearing: 30, id: 'D-02' },
      { lat: 10.7820, lon: 106.6980, bearing: 220, id: 'D-03' },
    ];
    this.initCanvasSize();
    window.addEventListener('resize', () => this.initCanvasSize());
    this.startRenderLoop();
  }

  initCanvasSize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.width = rect.width;
    this.height = rect.height;
  }

  // Convert Geo Coordinates to Canvas Pixels
  geoToPixel(lat, lon) {
    const scale = Math.pow(2, this.zoom) * 0.4;
    const x = this.width / 2 + (lon - this.center.lon) * scale * 111320 * Math.cos(this.center.lat * Math.PI / 180);
    // Asymmetric camera offset: shifts view center upwards so route is not blocked by bottom sheet
    const verticalOffset = (this.paddingBottom / 2);
    const y = (this.height / 2 - verticalOffset) - (lat - this.center.lat) * scale * 110574;
    return { x, y };
  }

  setCameraPadding(paddingPx) {
    this.paddingBottom = paddingPx;
  }

  fitBounds(coordinates) {
    if (!coordinates || coordinates.length === 0) return;
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    coordinates.forEach(c => {
      minLat = Math.min(minLat, c.lat);
      maxLat = Math.max(maxLat, c.lat);
      minLon = Math.min(minLon, c.lon);
      maxLon = Math.max(maxLon, c.lon);
    });

    this.center = {
      lat: (minLat + maxLat) / 2,
      lon: (minLon + maxLon) / 2,
    };
    this.zoom = 14.5;
  }

  startRenderLoop() {
    const render = () => {
      this.draw();
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
  }

  draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    // 1. Draw Map Base (Subtle light gray land)
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, this.width, this.height);

    // 2. Draw Saigon River Water Body
    this.drawRiver(ctx);

    // 3. Draw City Road Grid
    this.drawRoadGrid(ctx);

    // 4. Draw Active Route Polyline
    if (APP_STATE.routeCoordinates.length > 1) {
      this.drawRoutePolyline(ctx);
    }

    // 5. Draw Idle Fleet (When in Idle State)
    if (APP_STATE.phase === 'idle') {
      this.idleFleet.forEach(car => {
        const pt = this.geoToPixel(car.lat, car.lon);
        this.drawVehicle(ctx, pt.x, pt.y, car.bearing, '#111827', 0.85);
      });
    }

    // 6. Draw Origin & Destination Markers
    if (APP_STATE.origin) {
      const p = this.geoToPixel(APP_STATE.origin.lat, APP_STATE.origin.lon);
      this.drawOriginMarker(ctx, p.x, p.y);
    }

    if (APP_STATE.destination) {
      const d = this.geoToPixel(APP_STATE.destination.lat, APP_STATE.destination.lon);
      this.drawDestinationMarker(ctx, d.x, d.y);
    }

    // Intermediate Waypoints
    APP_STATE.waypoints.forEach((wp, idx) => {
      const w = this.geoToPixel(wp.lat, wp.lon);
      this.drawWaypointMarker(ctx, w.x, w.y, idx + 1);
    });

    // 7. Draw Active Driver Vehicle (When Matched / In Transit)
    if (APP_STATE.phase === 'telemetry' || APP_STATE.phase === 'matching') {
      const c = this.geoToPixel(APP_STATE.carTelemetry.lat, APP_STATE.carTelemetry.lon);
      this.drawVehicle(ctx, c.x, c.y, APP_STATE.carTelemetry.bearing, '#000000', 1.1);
    }
  }

  drawRiver(ctx) {
    const pts = [
      this.geoToPixel(10.7950, 106.7150),
      this.geoToPixel(10.7850, 106.7120),
      this.geoToPixel(10.7720, 106.7080),
      this.geoToPixel(10.7600, 106.7020),
      this.geoToPixel(10.7500, 106.6980),
    ];
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(pts[i].x, pts[i].y);
    }
    ctx.strokeStyle = '#e0f2fe';
    ctx.lineWidth = 36;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
  }

  drawRoadGrid(ctx) {
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 6;
    ctx.lineCap = 'round';
    const lines = [
      // Main Boulevards
      [{ lat: 10.765, lon: 106.685 }, { lat: 10.785, lon: 106.715 }],
      [{ lat: 10.785, lon: 106.685 }, { lat: 10.765, lon: 106.715 }],
      [{ lat: 10.775, lon: 106.680 }, { lat: 10.775, lon: 106.730 }],
      [{ lat: 10.755, lon: 106.700 }, { lat: 10.810, lon: 106.700 }],
      [{ lat: 10.795, lon: 106.690 }, { lat: 10.795, lon: 106.730 }],
      [{ lat: 10.760, lon: 106.670 }, { lat: 10.760, lon: 106.720 }],
    ];
    lines.forEach(line => {
      const p1 = this.geoToPixel(line[0].lat, line[0].lon);
      const p2 = this.geoToPixel(line[1].lat, line[1].lon);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    });
  }

  drawRoutePolyline(ctx) {
    const coords = APP_STATE.routeCoordinates;
    if (coords.length < 2) return;

    // Route Outer Border
    ctx.beginPath();
    const first = this.geoToPixel(coords[0].lat, coords[0].lon);
    ctx.moveTo(first.x, first.y);
    for (let i = 1; i < coords.length; i++) {
      const pt = this.geoToPixel(coords[i].lat, coords[i].lon);
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 6;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Route Inner Vivid Fill (Uber Blue)
    ctx.beginPath();
    ctx.moveTo(first.x, first.y);
    for (let i = 1; i < coords.length; i++) {
      const pt = this.geoToPixel(coords[i].lat, coords[i].lon);
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.strokeStyle = '#276ef1';
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
  }

  drawOriginMarker(ctx, x, y) {
    // Pulsing radar ripple
    ctx.beginPath();
    ctx.arc(x, y, 14, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(39, 110, 241, 0.18)';
    ctx.fill();

    // Center dot
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#276ef1';
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();
  }

  drawDestinationMarker(ctx, x, y) {
    // Destination Black Square Pin
    ctx.fillStyle = '#000000';
    ctx.fillRect(x - 6, y - 6, 12, 12);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x - 2, y - 2, 4, 4);

    // Stem line
    ctx.beginPath();
    ctx.moveTo(x, y + 6);
    ctx.lineTo(x, y + 14);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  drawWaypointMarker(ctx, x, y, num) {
    ctx.beginPath();
    ctx.arc(x, y, 9, 0, Math.PI * 2);
    ctx.fillStyle = '#ffb703';
    ctx.fill();
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#000000';
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(num, x, y);
  }

  drawVehicle(ctx, x, y, bearingDeg, color, scale = 1.0) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate((bearingDeg * Math.PI) / 180);
    ctx.scale(scale, scale);

    // Vehicle Shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.25)';
    ctx.beginPath();
    ctx.roundRect(-8, -14, 16, 30, 4);
    ctx.fill();

    // Vehicle Body
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(-7, -15, 14, 28, 4);
    ctx.fill();

    // Roof & Windshield
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.roundRect(-5, -8, 10, 14, 2);
    ctx.fill();

    // Windshield Glass tint
    ctx.fillStyle = '#93c5fd';
    ctx.beginPath();
    ctx.roundRect(-4, -7, 8, 4, 1);
    ctx.fill();

    // Headlights
    ctx.fillStyle = '#fef08a';
    ctx.fillRect(-6, -15, 3, 2);
    ctx.fillRect(3, -15, 3, 2);

    ctx.restore();
  }
}

// ============================================================================
// 3. UI Phase Transitions & Bottom Sheet Controller
// ============================================================================

class BottomSheetManager {
  constructor(mapEngine) {
    this.map = mapEngine;
    this.sheet = document.getElementById('bottom-sheet');
    this.handle = document.getElementById('sheet-handle');
    this.content = document.getElementById('sheet-content');

    this.phaseIdle = document.getElementById('phase-idle');
    this.phaseSelection = document.getElementById('phase-selection');
    this.phaseMatching = document.getElementById('phase-matching');
    this.phaseTelemetry = document.getElementById('phase-telemetry');

    this.initGestures();
  }

  setPhase(newPhase) {
    APP_STATE.phase = newPhase;

    this.phaseIdle.style.display = 'none';
    this.phaseSelection.style.display = 'none';
    this.phaseMatching.style.display = 'none';
    this.phaseTelemetry.style.display = 'none';

    if (newPhase === 'idle') {
      this.phaseIdle.style.display = 'block';
      this.map.setCameraPadding(180);
    } else if (newPhase === 'selection') {
      this.phaseSelection.style.display = 'block';
      this.map.setCameraPadding(380);
    } else if (newPhase === 'matching') {
      this.phaseMatching.style.display = 'block';
      this.map.setCameraPadding(240);
    } else if (newPhase === 'telemetry') {
      this.phaseTelemetry.style.display = 'block';
      this.map.setCameraPadding(360);
    }
  }

  initGestures() {
    let startY = 0;
    let isDragging = false;

    const onStart = (e) => {
      startY = e.touches ? e.touches[0].clientY : e.clientY;
      isDragging = true;
    };

    const onMove = (e) => {
      if (!isDragging) return;
      const currentY = e.touches ? e.touches[0].clientY : e.clientY;
      const deltaY = currentY - startY;
      if (deltaY > 0) {
        this.sheet.style.transform = `translateY(${deltaY}px)`;
      }
    };

    const onEnd = () => {
      if (!isDragging) return;
      isDragging = false;
      this.sheet.style.transform = '';
    };

    this.handle.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);

    this.handle.addEventListener('touchstart', onStart, { passive: true });
    window.addEventListener('touchmove', onMove, { passive: true });
    window.addEventListener('touchend', onEnd);
  }
}

// ============================================================================
// 4. Destination Search Modal (Compliant with Modern Web Guidance)
// ============================================================================

function initSearchDialog(bottomSheet, mapEngine) {
  const dialog = document.getElementById('search-dialog');
  const openTrigger = document.getElementById('open-search-trigger');
  const closeBtn = document.getElementById('close-search-btn');
  const destInput = document.getElementById('dest-search-input');
  const suggestions = document.querySelectorAll('.suggestion-item');
  const shortcutItems = document.querySelectorAll('.shortcut-item');

  // Open Modal
  const openSearch = () => {
    dialog.showModal();
    destInput.focus();
  };

  openTrigger.addEventListener('click', openSearch);
  openTrigger.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openSearch();
    }
  });

  // Close Modal
  closeBtn.addEventListener('click', () => dialog.close());

  // Modern Web Guidance: IME-safe enter submission
  destInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      // Block submission if user is actively composing IME characters (e.g. Vietnamese, Japanese)
      if (event.isComposing || event.keyCode === 229) {
        return;
      }
      if (destInput.value.trim().length > 0) {
        selectDestination({
          name: destInput.value.trim(),
          lat: 10.7950,
          lon: 106.7218,
        });
        dialog.close();
      }
    }
  });

  // Selection handler from suggestions list
  const selectDestination = (dest) => {
    APP_STATE.destination = dest;
    generateRoutePolyline(APP_STATE.origin, dest);
    mapEngine.fitBounds(APP_STATE.routeCoordinates);
    updateFareEstimates();
    bottomSheet.setPhase('selection');
  };

  suggestions.forEach(item => {
    item.addEventListener('click', () => {
      const dest = {
        name: item.dataset.dest,
        lat: parseFloat(item.dataset.lat),
        lon: parseFloat(item.dataset.lon),
      };
      selectDestination(dest);
      dialog.close();
    });
  });

  shortcutItems.forEach(item => {
    item.addEventListener('click', () => {
      const dest = {
        name: item.dataset.dest,
        lat: parseFloat(item.dataset.lat),
        lon: parseFloat(item.dataset.lon),
      };
      selectDestination(dest);
    });
  });
}

// Generate realistic intermediate coordinates between origin and destination
function generateRoutePolyline(origin, dest) {
  const steps = 30;
  const coords = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    // Add subtle curvature to mimic city streets
    const curvature = Math.sin(t * Math.PI) * 0.004;
    coords.push({
      lat: origin.lat + (dest.lat - origin.lat) * t + curvature,
      lon: origin.lon + (dest.lon - origin.lon) * t,
    });
  }
  APP_STATE.routeCoordinates = coords;
}

// Upfront pricing calculation with Surge bounds
function updateFareEstimates() {
  const baseRate = 10.0;
  const surge = APP_STATE.surgeMultiplier;
  
  const uberX = (baseRate * 1.0 * surge).toFixed(2);
  const comfort = (baseRate * 1.35 * surge).toFixed(2);
  const xl = (baseRate * 1.75 * surge).toFixed(2);

  document.getElementById('uberx-fare').textContent = `$${uberX}`;
  document.getElementById('uberx-old-fare').textContent = `$${(uberX * 1.2).toFixed(2)}`;
  document.getElementById('comfort-fare').textContent = `$${comfort}`;
  document.getElementById('xl-fare').textContent = `$${xl}`;
  document.getElementById('surge-text').textContent = `${surge.toFixed(1)}x Surge`;
}

// ============================================================================
// 5. Backend REST API & WebSocket Telemetry Client
// ============================================================================

class UberApiClient {
  constructor(bottomSheet, mapEngine) {
    this.sheet = bottomSheet;
    this.map = mapEngine;
    this.initButtons();
  }

  initButtons() {
    // Ride Tier Selection Cards
    const cards = document.querySelectorAll('.ride-card');
    cards.forEach(card => {
      card.addEventListener('click', () => {
        cards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        APP_STATE.selectedTier = card.dataset.tier;
        document.querySelector('#confirm-booking-btn span').textContent = `Choose ${card.dataset.tier}`;
      });
    });

    // Confirm Booking CTA Button
    document.getElementById('confirm-booking-btn').addEventListener('click', async () => {
      await this.requestTrip();
    });

    // Simulate Step Button
    document.getElementById('step-simulation-btn').addEventListener('click', () => {
      this.simulateDriveStep();
    });

    // Add Stop / Detour Button
    document.getElementById('add-waypoint-btn').addEventListener('click', async () => {
      await this.addWaypoint();
    });

    // Cancel Trip Button
    document.getElementById('cancel-trip-btn').addEventListener('click', async () => {
      await this.cancelTrip();
    });

    // Recenter Button
    document.getElementById('recenter-btn').addEventListener('click', () => {
      if (APP_STATE.routeCoordinates.length > 0) {
        this.map.fitBounds(APP_STATE.routeCoordinates);
      } else {
        this.map.center = { ...APP_STATE.origin };
      }
    });
  }

  async requestTrip() {
    this.sheet.setPhase('matching');

    const payload = {
      idempotency_key: `trip-${Date.now()}`,
      rider_id: 'rider-mobile-01',
      origin: { lat: APP_STATE.origin.lat, lon: APP_STATE.origin.lon },
      destination: { lat: APP_STATE.destination.lat, lon: APP_STATE.destination.lon },
    };

    try {
      const res = await fetch('/api/v1/trips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      APP_STATE.activeTrip = data;
      document.getElementById('active-trip-id-display').textContent = data.trip_id;

      // Dispatch nearest driver via spatial matching API
      setTimeout(async () => {
        await this.matchDriver(data.trip_id);
      }, 1000);

    } catch (err) {
      console.error('Failed to create trip:', err);
      // Fallback offline mock for testing standalone
      this.mockMatchingFallback();
    }
  }

  async matchDriver(tripId) {
    try {
      const res = await fetch(`/api/v1/trips/${tripId}/match`, { method: 'POST' });
      const matchData = await res.json();
      
      // Update Driver UI
      document.getElementById('driver-name-text').textContent = matchData.driver_name || 'Alex Chen';
      document.getElementById('driver-avatar-initials').textContent = (matchData.driver_name || 'Alex Chen').split(' ').map(n => n[0]).join('');
      
      this.sheet.setPhase('telemetry');
      this.connectWebSocket(tripId);
    } catch (err) {
      console.warn('Backend match failed, using fallback:', err);
      this.mockMatchingFallback();
    }
  }

  mockMatchingFallback() {
    this.sheet.setPhase('telemetry');
    document.getElementById('live-trip-status-badge').textContent = 'MATCHED';
    document.getElementById('live-trip-status-badge').className = 'status-badge-lg badge-MATCHED';
    document.getElementById('live-trip-eta-headline').textContent = 'Driver arriving in 3 mins';
  }

  connectWebSocket(tripId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/trips/${tripId}/telemetry`;

    try {
      const ws = new WebSocket(wsUrl);
      APP_STATE.ws = ws;

      ws.onopen = () => {
        document.getElementById('ws-indicator').style.backgroundColor = '#05a357';
        document.getElementById('connection-status-text').textContent = 'Live Telemetry';
      };

      ws.onmessage = (event) => {
        const frame = JSON.parse(event.data);
        this.handleTelemetryFrame(frame);
      };

      ws.onclose = () => {
        document.getElementById('ws-indicator').style.backgroundColor = '#6b7280';
        document.getElementById('connection-status-text').textContent = 'Offline';
      };
    } catch (e) {
      console.warn('WebSocket connection not available:', e);
    }
  }

  handleTelemetryFrame(frame) {
    const badge = document.getElementById('live-trip-status-badge');
    badge.textContent = frame.state;
    badge.className = `status-badge-lg badge-${frame.state}`;

    if (frame.state === 'MATCHED') {
      document.getElementById('live-trip-eta-headline').textContent = 'Driver assigned • 3 mins';
    } else if (frame.state === 'DRIVER_ARRIVING') {
      document.getElementById('live-trip-eta-headline').textContent = 'Driver arriving now!';
    } else if (frame.state === 'IN_TRANSIT') {
      document.getElementById('live-trip-eta-headline').textContent = 'Heading to destination...';
    } else if (frame.state === 'COMPLETED') {
      document.getElementById('live-trip-eta-headline').textContent = 'You have arrived!';
      setTimeout(() => alert('Trip Completed! Thank you for riding with Uber.'), 300);
    }

    if (frame.current_lat && frame.current_lon) {
      APP_STATE.carTelemetry.lat = frame.current_lat;
      APP_STATE.carTelemetry.lon = frame.current_lon;
    }
    if (frame.bearing !== undefined) {
      APP_STATE.carTelemetry.bearing = frame.bearing;
    }
  }

  simulateDriveStep() {
    // Smooth progress along route
    APP_STATE.travelProgress = Math.min(1.0, APP_STATE.travelProgress + 0.1);
    const coords = APP_STATE.routeCoordinates;
    if (coords.length > 0) {
      const idx = Math.min(coords.length - 1, Math.floor(APP_STATE.travelProgress * (coords.length - 1)));
      const nextIdx = Math.min(coords.length - 1, idx + 1);
      
      const p1 = coords[idx];
      const p2 = coords[nextIdx];
      
      APP_STATE.carTelemetry.lat = p1.lat;
      APP_STATE.carTelemetry.lon = p1.lon;
      
      // Calculate bearing angle
      const dLon = (p2.lon - p1.lon) * (Math.PI / 180);
      const lat1 = p1.lat * (Math.PI / 180);
      const lat2 = p2.lat * (Math.PI / 180);
      const y = Math.sin(dLon) * Math.cos(lat2);
      const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
      APP_STATE.carTelemetry.bearing = (Math.atan2(y, x) * (180 / Math.PI) + 360) % 360;

      // Update badge states based on progress
      const badge = document.getElementById('live-trip-status-badge');
      if (APP_STATE.travelProgress < 0.2) {
        badge.textContent = 'DRIVER_ARRIVING';
        badge.className = 'status-badge-lg badge-DRIVER_ARRIVING';
        document.getElementById('live-trip-eta-headline').textContent = 'Driver arriving in 2 mins';
      } else if (APP_STATE.travelProgress < 0.95) {
        badge.textContent = 'IN_TRANSIT';
        badge.className = 'status-badge-lg badge-IN_TRANSIT';
        document.getElementById('live-trip-eta-headline').textContent = `In Transit • ${Math.round((1 - APP_STATE.travelProgress) * 6)} mins remaining`;
      } else {
        badge.textContent = 'COMPLETED';
        badge.className = 'status-badge-lg badge-COMPLETED';
        document.getElementById('live-trip-eta-headline').textContent = 'Dropped off at destination!';
      }
    }

    // If WebSocket is alive, trigger server step
    if (APP_STATE.ws && APP_STATE.ws.readyState === WebSocket.OPEN) {
      APP_STATE.ws.send(JSON.stringify({ command: 'SIMULATE_STEP' }));
    }
  }

  async addWaypoint() {
    const wp = { lat: 10.7850, lon: 106.7050 };
    APP_STATE.waypoints.push(wp);
    if (APP_STATE.activeTrip) {
      try {
        await fetch(`/api/v1/trips/${APP_STATE.activeTrip.trip_id}/waypoints`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(wp),
        });
      } catch (e) {
        console.warn('Waypoint API call failed:', e);
      }
    }
    alert('Added intermediate stop: Ben Nghe Waypoint (+1.5 km)');
  }

  async cancelTrip() {
    if (APP_STATE.activeTrip) {
      try {
        await fetch(`/api/v1/trips/${APP_STATE.activeTrip.trip_id}/cancel`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: 'Rider cancelled from mobile app' }),
        });
      } catch (e) {
        console.warn('Cancel API failed:', e);
      }
    }
    if (APP_STATE.ws) {
      APP_STATE.ws.close();
    }
    APP_STATE.activeTrip = null;
    APP_STATE.destination = null;
    APP_STATE.routeCoordinates = [];
    APP_STATE.travelProgress = 0;
    this.sheet.setPhase('idle');
  }
}

// ============================================================================
// 6. Application Bootstrap
// ============================================================================

window.addEventListener('DOMContentLoaded', () => {
  const mapEngine = new UberMapEngine('mapCanvas');
  const bottomSheet = new BottomSheetManager(mapEngine);
  const apiClient = new UberApiClient(bottomSheet, mapEngine);
  initSearchDialog(bottomSheet, mapEngine);
});
