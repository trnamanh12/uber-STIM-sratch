# The Mobile Uber UI/UX Architectural Blueprint
### Complete Implementation Guide for React Native & Flutter

> *"The map is not a widget on a screen. In Uber, the map is the canvas of reality, and the UI is an adaptive physical layer resting on top of it."*

---

## 1. Executive Summary & Design System

Building an application that feels identical to Uber requires mastering three disciplines:
1. **Physical Gesture Physics:** Real-time spring physics for bottom sheets with velocity clamping and zero-jank frame rates.
2. **Asymmetric Camera Geometry:** Map viewports must dynamically offset their center point so routes and pins are framed perfectly above the bottom sheet rather than obscured behind it.
3. **Continuous Telemetry Interpolation:** Raw GPS is noisy and low-frequency (0.5–1 Hz). Uber renders 60fps smooth vehicle traversal through dead reckoning, polyline snap-to-road, and continuous bearing rotation.

---

## 2. Design System Tokens (The Uber Visual Language)

Uber uses **Base Design**—a high-contrast, minimalist design language that prioritizes legibility in moving vehicles under bright sunlight or dark night driving.

### Color Tokens (Hex / HSL)
| Token | Value | Semantic Usage |
| :--- | :--- | :--- |
| `color-surface-primary` | `#FFFFFF` / `#000000` | Background of bottom sheet and cards (light/dark mode) |
| `color-surface-secondary`| `#F6F6F6` / `#161616` | Search inputs, inactive pills, subtle borders |
| `color-text-primary` | `#000000` / `#FFFFFF` | Primary headers, destination names, vehicle titles |
| `color-text-muted` | `#6B7280` / `#9CA3AF` | ETAs, subtitles, address details |
| `color-brand-accent` | `#000000` / `#FFFFFF` | Primary CTA buttons ("Choose UberX") |
| `color-status-success` | `#05A357` | Green badge for promotions, savings, on-time arrivals |
| `color-status-info` | `#276EF1` | Active route lines, pickup location pin |
| `color-status-warning` | `#FFC043` | Surge pricing lightning indicator |

### Typography & Spacing
- **Font Family:** `Uber Move Text`, `Uber Move`, or clean geometric grotesques (`Inter`, `Plus Jakarta Sans`, `SF Pro Display`).
- **Radii:** 
  - Buttons & Inputs: `8px` or pill `9999px`
  - Cards & Bottom Sheets: `20px` to `24px` top corners
  - Badges: `4px`
- **Elevation / Shadows:**
  - Bottom Sheet: `box-shadow: 0px -4px 20px rgba(0, 0, 0, 0.12)` (subtle ambient occlusion, not harsh drops).

---

## 3. The 4 Interactive UX States

Uber's core booking loop takes place in a **continuous bottom sheet**, eliminating traditional page navigation transitions.

```
┌────────────────────────────────────────────────────────┐
│ STATE 1: IDLE / DISCOVERY                             │
│ • Floating "Where to?" search capsule                  │
│ • Quick destination shortcuts: Home, Work, Airport     │
│ • Nearby idle driver markers roaming on map            │
└───────────────────────────┬────────────────────────────┘
                            │ User taps "Where to?"
                            ▼
┌────────────────────────────────────────────────────────┐
│ STATE 2: SEARCH & AUTOCOMPLETE MODAL                   │
│ • Full-screen sheet slide-up                          │
│ • Origin & Destination inputs                          │
│ • Recent destinations list with distance & ETA         │
│ • "Set pin on map" mode with bouncing center pin       │
└───────────────────────────┬────────────────────────────┘
                            │ Destination selected
                            ▼
┌────────────────────────────────────────────────────────┐
│ STATE 3: VEHICLE & SURGE SELECTION                    │
│ • Half-expanded bottom sheet (45% viewport height)     │
│ • Ride tier cards: UberX, Comfort, UberXL, Black       │
│ • Upfront fare calculation with Surge badges           │
│ • Payment selector pill (Apple Pay / Credit Card)      │
│ • Primary CTA: "Choose UberX"                          │
└───────────────────────────┬────────────────────────────┘
                            │ Rider confirms booking
                            ▼
┌────────────────────────────────────────────────────────┐
│ STATE 4: LIVE DISPATCH & TELEMETRY                    │
│ • Sub-state A: "Finding your ride..." (Pulsing radar)  │
│ • Sub-state B: "Driver arriving in 3 mins"             │
│ • Driver Card: Name, rating (★ 4.96), car model, plate │
│ • Live vehicle marker interpolating along route line   │
│ • Dynamic route polyline trimming                      │
└────────────────────────────────────────────────────────┘
```

---

## 4. Mobile Implementation Blueprint: React Native

For React Native, the industry standard stack to replicate Uber 1:1 is:
- **Navigation & Gestures:** `react-native-gesture-handler` + `react-native-reanimated` (v3)
- **Bottom Sheet:** `@gorhom/bottom-sheet` (built by a senior ex-Uber engineer; mirrors the exact physics)
- **Map Engine:** `@rnmapbox/maps` or `react-native-maps`
- **Haptics:** `expo-haptics`

### A. The Bottom Sheet Architecture (`@gorhom/bottom-sheet`)

```tsx
import React, { useMemo, useRef } from 'react';
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';

export function UberBookingSheet({ bookingState }) {
  const bottomSheetRef = useRef<BottomSheet>(null);

  // Snap points matching Uber's exact proportions:
  // - 15%: Collapsed idle peek
  // - 45%: Vehicle selection carousel
  // - 90%: Full search / Place autocomplete
  const snapPoints = useMemo(() => ['15%', '45%', '90%'], []);

  return (
    <BottomSheet
      ref={bottomSheetRef}
      snapPoints={snapPoints}
      index={bookingState === 'IDLE' ? 0 : bookingState === 'SELECTING' ? 1 : 2}
      handleIndicatorStyle={{ backgroundColor: '#E5E7EB', width: 40, height: 4 }}
      backgroundStyle={{ backgroundColor: '#FFFFFF', borderRadius: 24 }}
    >
      <BottomSheetView style={{ flex: 1, paddingHorizontal: 16 }}>
        {/* Render Idle / Ride Options / Telemetry based on state */}
      </BottomSheetView>
    </BottomSheet>
  );
}
```

### B. Asymmetric Camera Padding Algorithm
When the bottom sheet expands to 45% or 90% of screen height, the route must be padded upwards:

```tsx
function fitRouteOnMap(mapRef, origin, destination, sheetHeightPx) {
  mapRef.current?.fitToCoordinates(
    [
      { latitude: origin.lat, longitude: origin.lon },
      { latitude: destination.lat, longitude: destination.lon },
    ],
    {
      edgePadding: {
        top: 80,
        right: 40,
        left: 40,
        bottom: sheetHeightPx + 40, // Critical: offsets map center above sheet!
      },
      animated: true,
    }
  );
}
```

### C. 60fps Vehicle Rotation & Interpolation (Reanimated 3)
```tsx
import { useSharedValue, useAnimatedStyle, withTiming } from 'react-native-reanimated';

// Calculate bearing angle between two coordinates
function getBearing(startLat, startLon, endLat, endLon) {
  const dLon = (endLon - startLon) * (Math.PI / 180);
  const lat1 = startLat * (Math.PI / 180);
  const lat2 = endLat * (Math.PI / 180);
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return (Math.atan2(y, x) * (180 / Math.PI) + 360) % 360;
}
```

---

## 5. Mobile Implementation Blueprint: Flutter

For Flutter, the canonical architecture uses:
- **Map Engine:** `google_maps_flutter` or `mapbox_maps_flutter`
- **Bottom Sheet:** `sliding_up_panel2` or custom `DraggableScrollableSheet`
- **State Management:** `flutter_bloc` or `Riverpod` for FSM state transitions

```dart
// DraggableScrollableSheet with Uber Snap Points
DraggableScrollableSheet(
  initialChildSize: 0.40,
  minChildSize: 0.15,
  maxChildSize: 0.90,
  snap: true,
  snapSizes: const [0.15, 0.40, 0.90],
  builder: (context, scrollController) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [
          BoxShadow(color: Colors.black12, blurRadius: 15, spreadRadius: 2),
        ],
      ),
      child: ListView(
        controller: scrollController,
        children: [
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 8, bottom: 12),
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          // Content widgets
        ],
      ),
    );
  },
);
```

---

## 6. Real-Time Telemetry & WebSocket Contract

The mobile app must maintain a continuous WebSocket connection to the backend telemetry stream (`/ws/trips/{trip_id}/telemetry`):

1. **Client Sends:** Keep-alive heartbeat pings every 5 seconds.
2. **Server Broadcasts (1–5Hz):**
   ```json
   {
     "trip_id": "TRIP-7492-9182",
     "state": "IN_TRANSIT",
     "driver_id": "D-01",
     "driver_name": "Alex Chen",
     "rating": 4.96,
     "vehicle": "Toyota Camry • White",
     "plate": "51A-982.34",
     "current_lat": 10.7765,
     "current_lon": 106.7020,
     "bearing": 42.5,
     "speed_kmh": 32.4,
     "eta_minutes": 4,
     "surge_multiplier": 1.4
   }
   ```
3. **Client Interpolation:** The mobile client smooths the movement between consecutive coordinate packets using linear interpolation (`LERP`) over the packet interval.
