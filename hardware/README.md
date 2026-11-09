# 🛰️ Smart Bus Tracking System - Hardware & Firmware Integration Guide

This guide details the physical hardware setup, pin connections, firmware flashing, and technical checks for connecting an **ESP8266 NodeMCU** and **TinyGPS++ GNSS module** (NEO-6M / NEO-7M / NEO-M8N) to the College Bus Tracking backend.

---

## 📌 Hardware Components & Bill of Materials (BOM)

| Component | Specification | Quantity | Role |
| :--- | :--- | :--- | :--- |
| **Microcontroller** | ESP8266 NodeMCU v2 or v3 (ESP-12E) | 1 | Microcontroller with Wi-Fi & HTTPS capabilities |
| **GPS Module** | u-blox NEO-6M / NEO-7M / NEO-M8N | 1 | GNSS receiver collecting coordinates & telemetry |
| **Antenna** | Ceramic Active GPS Patch Antenna | 1 | Satellite signal reception (Face upwards toward sky) |
| **Power Supply** | 5V / 2A Micro-USB or Step-down Buck Converter | 1 | Stable power source |
| **Jumper Wires** | Female-to-Female Dupont Wires | 4 | Interconnection between NodeMCU & GPS |

---

## 🔌 Pinout & Wiring Diagram

```
      ┌───────────────────────────┐
      │     ESP8266 NodeMCU       │
      │                           │
      │    [ D2 / GPIO 4 ] ───────┼───────► GPS Module TXD
      │                           │
      │    [ D1 / GPIO 5 ] ◄──────┼───────  GPS Module RXD
      │                           │
      │    [ 3.3V / 3V3 ]  ───────┼───────► GPS Module VCC (or 5V if supported)
      │                           │
      │    [ GND ]         ───────┼───────► GPS Module GND
      └───────────────────────────┘
```

> ⚠️ **IMPORTANT POWER & VOLTAGE NOTICE:**
> - Ensure **Common Ground (GND)** is connected between the ESP8266 and the GPS module.
> - Most NEO-6M breakout boards contain an onboard 3.3V LDO regulator and can accept **3.3V to 5V DC** on their VCC pin. Check your board markings.
> - The ESP8266 NodeMCU GPIO pins are 3.3V logic. The NEO-6M TXD outputs 3.3V UART, which directly interfaces with NodeMCU D2 (GPIO 4) without level shifting.

---

## 💻 Arduino IDE Setup & Required Libraries

1. **Install ESP8266 Board Package**:
   - In Arduino IDE, open **File → Preferences**.
   - In *Additional Boards Manager URLs*, add:
     ```
     http://arduino.esp8266.com/stable/package_esp8266com_index.json
     ```
   - Open **Tools → Board → Boards Manager**, search for `esp8266`, and install version `3.1.2` or later.
   - Select your board under **Tools → Board → ESP8266 Boards → NodeMCU 1.0 (ESP-12E Module)**.

2. **Install Required Libraries**:
   - Open **Sketch → Include Library → Manage Libraries...**
   - Search and install:
     * **`TinyGPSPlus`** by Mikal Hart (Version 1.0.3+)
     * **`ESP8266WiFi`** (Built-in with ESP8266 core)
     * **`SoftwareSerial`** (Built-in with ESP8266 core)

3. **Flashing Settings**:
   - CPU Frequency: `80 MHz` (or `160 MHz` for faster SSL processing)
   - Flash Size: `4MB (FS:2MB OTA:~1019KB)`
   - Upload Speed: `115200` or `921600`
   - Port: Select the COM port corresponding to your NodeMCU (CH340 or CP2102 driver).

---

## ⚙️ Firmware Configuration

Open [`hardware/esp8266_nodemcu_gps_tracker.ino`](file:///hardware/esp8266_nodemcu_gps_tracker.ino) and adjust the top configuration block:

```cpp
// --- Wi-Fi Credentials ---
const char* WIFI_SSID     = "Your_WiFi_Name";
const char* WIFI_PASSWORD = "Your_WiFi_Password";

// --- Device ID & Security API Key ---
const char* DEVICE_ID     = "bus-01";            // Matches Bus identifier in CampusFleet
const char* API_KEY       = "YOUR_API_KEY";      // Set in backend .env

// --- Target Server Endpoint ---
const char* SERVER_HOST   = "trackbus.pythonanywhere.com"; // or "bike-tracker-api-two.vercel.app"
const int   SERVER_PORT   = 443;                           // 443 for HTTPS, 80 for HTTP
const bool  USE_HTTPS     = true;
const char* API_PATH      = "/api/locations/save";
```

---

## 📡 Live Ingestion Telemetry Specification

The firmware transmits an HTTP GET query payload formatted as follows:

```
GET /api/locations/save?deviceId=bus-01&latitude=17.385044&longitude=78.486671&apiKey=YOUR_API_KEY&speed=32.5&heading=120.0&accuracy=1.20&satellites=9&altitude=540.2&gps_time=2026-11-09T07:45:00Z HTTP/1.1
Host: trackbus.pythonanywhere.com
User-Agent: ESP8266-SmartBusTracker/3.0
Connection: close
```

### Telemetry Fields Explained:
| Field | Type | Description |
| :--- | :--- | :--- |
| `deviceId` | String | Bus / Device unique identifier (`bus-01`) |
| `latitude` | Float | Signed 6-decimal latitude (-90.0 to +90.0) |
| `longitude` | Float | Signed 6-decimal longitude (-180.0 to +180.0) |
| `apiKey` | String | Authentication key matching server configuration |
| `speed` | Float | Instantaneous GPS ground speed in km/h |
| `heading` | Float | Direction of travel in degrees (0.0° - 359.9°) |
| `accuracy` | Float | HDOP (Horizontal Dilution of Precision in meters) |
| `satellites` | Integer | Visible locked GNSS satellites count |
| `altitude` | Float | Altitude above sea level in meters |
| `gps_time` | ISO-8601 | Satellite-synchronized UTC acquisition timestamp |

---

## 🩺 Diagnostic LED Status Codes

| LED Behavior | Meaning | Recommended Action |
| :--- | :--- | :--- |
| **Fast Blinking (200ms)** | Connecting to Wi-Fi | Verify SSID & password credentials |
| **Slow Heartbeat (1000ms)** | Connected to Wi-Fi, searching for satellites | Move GPS antenna near window or outdoors |
| **Off with Brief Flash** | Fix acquired, transmitting to API | Normal operating state |
| **Solid OFF (no blinks)** | Power down or execution halt | Check power connection |

---

## 🔍 Pre-Deployment Technical Checks

1. **GPS Indoors vs Outdoors**: Ceramic patch antennas require a clear view of the open sky. Indoor testing under concrete roofs may take 5 to 15 minutes for cold start fix or fail to lock satellites. Test near a window or outdoors.
2. **Non-blocking Execution**: The firmware contains zero `delay()` calls in the loop to preserve incoming UART character bytes from the GPS module.
3. **Transmission Debounce**: The firmware transmits every 5 seconds when moving and slows down to 20 seconds when stopped to conserve cellular/Wi-Fi bandwidth while keeping the live dashboard updated.

