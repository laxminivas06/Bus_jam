# CampusFleet - Smart Bus Live Tracking & Route Intelligence System 🚍📍

A production-grade, responsive, hardware-independent College Bus Live Tracking and Route Intelligence Platform built with **Python Flask**, **Thread-Safe JSON Storage**, **Vanilla HTML5/CSS3/JavaScript (ES6)**, and **Leaflet.js**.

The system integrates physical **ESP8266 NodeMCU + TinyGPS++** modules (and **SIMCom A7600C/A7670C 4G** modems), performing real-time GNSS telemetry ingestion, bus stop geofencing, dynamic ETA calculation, cross-track route deviation detection, and historical journey playback.

---

## 🏗️ System Architecture & Data Flow

```
                      PHYSICAL TRACKERS & CLIENTS
     ┌────────────────────────────────┬────────────────────────────────┐
     │                                │                                │
     ▼                                ▼                                ▼
[ ESP8266 + TinyGPS++ ]    [ Arduino UNO + A7670C ]     [ Multi-Bus Simulator / API ]
(NodeMCU D2=RX, D1=TX)     (SIMCom 4G LTE AT+HTTP)      (25 Hyderabad Buses)
     │                                │                                │
     └────────────────────────────────┼────────────────────────────────┘
                                      │
                                      ▼
    HTTPS GET /api/locations/save?deviceId=bus-01&latitude=...&longitude=...&apiKey=...
                                      │
                                      ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │                          Python Flask REST Engine                          │
   │  1. Hardware Security Verification (apiKey / device authentication)        │
   │  2. Strict Coordinate Validation (Rejection of unacquired 0,0 & bounds)    │
   │  3. Automatic Speed & Heading Calculation (Haversine & Bearing math)       │
   │  4. Bus Stop Geofencing Detection (Arrivals, Departures & Dwell Times)     │
   │  5. Route Intelligence Engine (Cross-track distance to polyline)           │
   │  6. Route Deviation Evaluation (>150m alert generation & debouncing)       │
   │  7. Dynamic ETA Estimation to upcoming transit stops                       │
   │  8. Device Diagnostics & Online vs Stopped State Differentiation           │
   └─────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                                         ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │                   Thread-Safe Persistent JSON Database                     │
   │  - Buses (buses.json)               - Current Locations (locations.json)   │
   │  - Predefined Routes (routes.json)  - Journey History (history.json)       │
   │  - Bus Stops (stops.json)           - Route Deviations (deviations.json)   │
   │  - Geofence Events (stop_events)    - Device Health (device_health.json)   │
   └─────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                                         ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │              Modern 9-Section Glassmorphic Web Dashboard                   │
   │  1. Overview & KPIs                 6. Route Management (Geometry)         │
   │  2. Live Full-Screen Map (Leaflet)  7. GPS Device Diagnostics              │
   │  3. Route Analysis & Deviations     8. Reports & Downloadable CSV Export   │
   │  4. Historical Playback Player      9. System Threshold Settings           │
   │  5. Bus Stops & Geofencing Feed                                            │
   └────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛰️ 1. ESP8266 NodeMCU & GPS Firmware Integration

The system includes complete production C++ firmware for the **ESP8266 NodeMCU** paired with a **u-blox NEO-6M** GNSS module in [`hardware/esp8266_nodemcu_gps_tracker.ino`](file:///hardware/esp8266_nodemcu_gps_tracker.ino).

### Pin Connections:
| ESP8266 NodeMCU Pin | NEO-6M GPS Pin | Notes |
| :--- | :--- | :--- |
| **D2 (GPIO 4)** | **TXD** | SoftwareSerial RX (Receives NMEA bytes from GPS) |
| **D1 (GPIO 5)** | **RXD** | SoftwareSerial TX (Optional configuration transmit) |
| **3V3 or VIN** | **VCC** | Power supply (3.3V to 5V DC) |
| **GND** | **GND** | Common Ground (Mandatory) |
| **GPIO 2 (D4)** | **Onboard LED** | Diagnostic status flash |

### Key Firmware Engineering Highlights:
- **100% Non-Blocking Loop**: Continuously feeds `gps.encode(gpsSerial.read())` without blocking `delay()` calls, preventing UART FIFO buffer overflow and lost NMEA sentences.
- **Pre-Transmission Coordinate Validation**: Coordinates are validated before transmission (`gps.location.isValid()`, latitude $\in [-90, 90]$, longitude $\in [-180, 180]$, zero-fix rejection).
- **Adaptive Transmission Timing**: Transmits every 5 seconds when moving ($> 3\text{ km/h}$) and throttles down to 20 seconds when stopped to minimize cellular/Wi-Fi bandwidth.
- **Automatic Wi-Fi Reconnection**: Non-blocking state machine automatically recovers from dropped Wi-Fi connections.
- **Secure HTTPS Communication**: Uses `WiFiClientSecure` with SSL support.

---

## 📡 2. Hardware API Specification

### Endpoint: `GET /api/locations/save` or `POST /api/locations/save`

#### Parameters:
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `deviceId` | String | **Yes** | Bus or tracker identifier | `bus-01` or `BUS001` |
| `latitude` | Float | **Yes** | GPS Latitude (-90.0 to +90.0) | `17.385044` |
| `longitude` | Float | **Yes** | GPS Longitude (-180.0 to +180.0) | `78.486671` |
| `apiKey` | String | **Yes** | Server API authentication key | `YOUR_API_KEY` |
| `speed` | Float | Optional | Instantaneous ground speed in km/h | `38.5` |
| `heading` | Float | Optional | Direction of travel in degrees (0 - 360°) | `120.0` |
| `accuracy` | Float | Optional | HDOP horizontal precision in meters | `1.15` |
| `satellites`| Integer | Optional | Number of locked GNSS satellites | `9` |
| `altitude` | Float | Optional | Height above sea level in meters | `542.0` |
| `gps_time` | ISO String | Optional | GPS satellite acquisition timestamp | `2026-11-09T07:45:00Z` |

#### Lightweight Response (Compatible with SIMCom `AT+HTTPREAD` and ESP8266):
```json
{
  "success": true,
  "status": "success",
  "message": "Location saved",
  "data": {
    "deviceId": "BUS-01",
    "latitude": 17.385044,
    "longitude": 78.486671,
    "speed": 38.5,
    "heading": 120.0,
    "cardinal": "ESE",
    "satellites": 9,
    "accuracy": 1.15,
    "date": "09-11-2026",
    "time": "01:15:00 PM",
    "geofence": {
      "in_stop": true,
      "stop_id": "STOP-01",
      "stop_name": "Koti Central Bus Stop"
    },
    "deviation": {
      "is_deviating": false,
      "distance_from_route_m": 12.4
    }
  }
}
```

---

## 🧠 3. Route Intelligence & Geospatial Analytics

The backend implements custom geospatial algorithms in [`backend/route_engine.py`](file:///backend/route_engine.py):

1. **Cross-Track Polyline Distance**:
   Calculates the exact orthogonal distance in meters from the bus coordinate $P$ to every line segment $AB$ of the predefined route polyline using flat-earth equirectangular projection clamped to segment endpoints:
   $$t = \max\left(0, \min\left(1, \frac{\vec{AP} \cdot \vec{AB}}{|\vec{AB}|^2}\right)\right)$$
2. **Route Deviation Alert**:
   If the minimum distance exceeds `deviation_threshold_meters` (default 150m), the system triggers a **ROUTE DEVIATION DETECTED** alert, records the start time, maximum deviation distance, and marks the deviation as `ACTIVE` until the bus returns to its assigned corridor.
3. **Bus Stop Geofencing**:
   Continuously checks proximity to registered bus stops with configurable radii (50m - 100m). When entered, logs an `ARRIVED` event; when departed, calculates exact dwell/stoppage duration at the stop.
4. **Dynamic ETA Calculation**:
   Estimates arrival times to upcoming stops along the route using remaining distance and effective moving speed:
   $$\text{ETA (minutes)} = \frac{\text{Distance to Stop (km)}}{\max(\text{Speed}, 20\text{ km/h})} \times 60$$
5. **Stopped Bus vs Disconnected GPS Device Distinction**:
   - **Bus Stopped**: Device is transmitting recent updates ($\le 30\text{s}$), but speed is $< 3\text{ km/h}$. Marked as **ONLINE - VEHICLE STOPPED**.
   - **Device Offline**: No communication received for $> 30\text{s}$. Marked as **OFFLINE**.

---

## 📅 4. Historical Journey Tracking & Route Playback

1. **Date & Range Filters**: Query history by `Today`, `Yesterday`, `Past 7 Days`, `Past 30 Days`, or custom dates.
2. **Trip Summary Metrics**:
   - Total distance covered ($\text{km}$)
   - Average speed ($\text{km/h}$) and Maximum speed ($\text{km/h}$)
   - Number of stops made and Total stoppage duration ($\text{minutes}$)
   - Journey start & end coordinates and timestamps
3. **Interactive Playback Player**:
   - **Play**, **Pause**, and **Reset** controls.
   - **Speed Multiplier**: 1x, 2x, 5x, 10x playback speed.
   - **Interactive Scrubber Slider**: Scrub to any point in the timeline.
   - **Live HUD**: Displays time, instantaneous speed, and coordinates dynamically as the marker moves along the route.

---

## 📊 5. Reports & CSV Data Export

- **Fleet Summary Report**: One-click download of aggregate daily fleet metrics across all buses.
- **Detailed GPS Logs Export**: Exports every recorded coordinate ping with timestamp, latitude, longitude, speed, heading, satellites, and accuracy to CSV:
  ```
  GET /api/reports/export?bus_id=bus-01&date=today
  ```

---

## 🚀 Quick Start & Local Execution

### 1. Set Up Environment
```bash
# Clone the repository
cd Bus_jam

# Copy environment template
cp .env.example .env
```

### 2. Run the Automated Test Suite
```bash
python tests/test_api.py
python tests/test_audit_comprehensive.py
```
*(All tests execute in < 2 seconds with zero external test runner dependencies).*

### 3. Launch Flask Server
```bash
python run.py
```
Open **`http://127.0.0.1:5001`** in any web browser to view the live dashboard!

### 4. Run Multi-Bus Simulator (Optional)
```bash
# Simulate 25 live buses on Hyderabad routes
python simulator/gps_simulator.py

# Or simulate a single bus matching ESP8266 deviceId:
python simulator/gps_simulator.py --bus-id bus-01 --interval 5
```

---

## ☁️ PythonAnywhere Live Deployment

The system is deployed and production-ready on PythonAnywhere:
- **Live URL**: `https://trackbus.pythonanywhere.com/`
- **Location Ingestion Endpoint**:
  ```
  https://trackbus.pythonanywhere.com/api/locations/save?deviceId=bus-01&latitude=17.385044&longitude=78.486671&apiKey=YOUR_API_KEY
  ```
