# CampusFleet - Hardware-Independent College Bus Live Tracking System 🚍📍

A complete, responsive, real-time College Bus Live Tracking System built with **Python Flask**, **SQLite / SQLAlchemy**, **Vanilla HTML5/CSS3/JavaScript**, and **Leaflet.js** (with **MapLibre GL** vector tiles).

The system is **100% Hardware-Independent**: whether location updates originate from an **Arduino UNO + SIMCom A7600C/A7670C**, direct **AT-Command Terminals**, **Postman**, a **Browser URL bar**, or the built-in **25-bus Python Simulator**, all send identical HTTP requests to the same endpoint.

---

## 🏗️ Hardware-Independent System Architecture

```
                       ANY CLIENT SENDS IDENTICAL HTTP REQUEST
        ┌──────────────────────────────────┬──────────────────────────────────┐
        │                                  │                                  │
        ▼                                  ▼                                  ▼
[ Arduino UNO + A7600C/A7670C ]  [ Direct AT Terminal / Emulator ]  [ Browser / Postman / Simulator ]
(AT+HTTPACTION=0)                (AT+HTTPREAD)                      (GET /api/locations/save)
        │                                  │                                  │
        └──────────────────────────────────┼──────────────────────────────────┘
                                           │
                                           ▼
             ┌──────────────────────────────────────────────────────────┐
             │       GET /api/locations/save?deviceId=BUS001...         │
             └─────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
             ┌──────────────────────────────────────────────────────────┐
             │                 Python Flask REST API                    │
             │       1. Validates API Key (apikey=...)                  │
             │       2. Validates Bus Number (deviceId=...)             │
             │       3. Validates Latitude & Longitude                  │
             │       4. Auto-generates Server Date, Time & Timestamp    │
             │       5. Calculates Speed & Heading automatically        │
             └─────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
             ┌──────────────────────────────────────────────────────────┐
             │                SQLite Database (SQLAlchemy)              │
             │       - Buses (BUS001 to BUS025+)                        │
             │       - CurrentLocation (Latest coordinates & status)    │
             │       - LocationHistory (Date-wise route history)        │
             └─────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
             ┌──────────────────────────────────────────────────────────┐
             │          Live Web Dashboard (Auto-refresh 5-10s)         │
             │          - Leaflet Map (Non-duplicating markers)         │
             │          - Responsive Bus List & Search                  │
             │          - Date-Wise Route History & Playback            │
             └──────────────────────────────────────────────────────────┘
```

---

## 📡 Hardware & Client API Specification

### Endpoint: `GET /api/locations/save`

#### Query Parameters:
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `deviceId` | String | **Yes** | Bus Number / Identifier | `BUS001` |
| `latitude` | Float | **Yes** | Latitude (-90.0 to +90.0) | `17.281409` |
| `longitude` | Float | **Yes** | Longitude (-180.0 to +180.0) | `78.553712` |
| `apikey` | String | **Yes** | Server API key (from `.env`) | `YOUR_API_KEY` |

> 💡 **The hardware sends ONLY 3 values**: `deviceId`, `latitude`, `longitude`.  
> The server automatically adds date, time, timestamp, and calculates speed and route history.

#### Lightweight Response (Optimized for SIMCom `AT+HTTPREAD`):
```json
{
  "success": true,
  "message": "Location saved"
}
```

---

## 🧪 5 Ways to Test the Same API (Hardware-Independent)

### 1. Browser URL (Instant Test)
Paste directly into any web browser:
```
http://127.0.0.1:5001/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY
```

### 2. cURL / Postman
```bash
curl -X GET "http://127.0.0.1:5001/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY"
```

### 3. Built-in Multi-Bus Simulator (25 Live Buses)
```bash
python simulator/gps_simulator.py
```
Simulates 25 buses (`BUS001` to `BUS025`) moving on realistic Hyderabad routes every 10 seconds.

### 4. Direct AT-Command Terminal (SIMCom A7600C / A7670C)
```
AT+CGDCONT=1,"IP","airtelgprs.com"
AT+CGATT=1
AT+CREG?
AT+HTTPINIT
AT+HTTPPARA="URL","https://YOUR-SERVER.com/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY"
AT+HTTPACTION=0
AT+HTTPREAD
AT+HTTPTERM
```

### 5. Physical Hardware (Arduino UNO + A7600C / A7670C)
Flash [`hardware/arduino_a7670c_tracker.ino`](file:///Users/nivas/Documents/Python%20Softwarez/bus_jam/hardware/arduino_a7670c_tracker.ino) to your Arduino.

---

## 🚀 Quick Start & Local Execution

### 1. Clone & Set Up Virtual Environment
```bash
cd bus_jam
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Run Flask Application
```bash
python run.py
```
Open **`http://127.0.0.1:5001`** in your browser to see the live dashboard!

### 4. Run Automated Test Suite
```bash
PYTHONPATH=. pytest
```

---

## 📅 Date-Wise History Route Playback

1. In the Web Dashboard, select any bus from the list.
2. In the Bus Detail Drawer, pick a **Date** from the dropdown.
3. The dashboard queries `GET /api/buses/<bus_id>/history?date=YYYY-MM-DD` and renders:
   - Glowing route path on the Leaflet map.
   - Interactive waypoint markers with recorded time badges.
   - Chronological table in the Admin Audit view.

---

## ☁️ PythonAnywhere Deployment Guide

1. **Sign Up / Login** on [PythonAnywhere](https://www.pythonanywhere.com/).
2. Open a **Bash Console** and clone your repository:
   ```bash
   git clone <your-repo-url> bus_tracker
   cd bus_tracker
   mkvirtualenv --python=python3.10 bus-env
   pip install -r requirements.txt
   cp .env.example .env
   ```
3. Go to the **Web** tab in PythonAnywhere dashboard:
   - Click **Add a new web app** → **Manual configuration** → **Python 3.10**.
   - Set **Virtualenv path**: `/home/yourusername/.virtualenvs/bus-env`
   - Edit the **WSGI configuration file**:
     ```python
     import sys
     from pathlib import Path

     path = '/home/yourusername/bus_tracker'
     if path not in sys.path:
         sys.path.append(path)

     from wsgi import application
     ```
4. Click **Reload yourusername.pythonanywhere.com**.
5. Your public endpoint is live:
   ```
   https://yourusername.pythonanywhere.com/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY
   ```
