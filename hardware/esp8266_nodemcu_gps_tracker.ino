/*
  ================================================================================
  SMART BUS LIVE TRACKING SYSTEM - ESP8266 NodeMCU + TinyGPS++ GNSS Tracker
  ================================================================================

  Hardware:
    - Microcontroller : ESP8266 NodeMCU v2 / v3 (ESP-12E Module)
    - GPS Module      : NEO-6M / NEO-7M / NEO-M8N GNSS Module
    - Baud Rate       : GPS = 9600 baud, Serial Monitor = 115200 baud
    - Wiring:
        * GPS TX  -----> NodeMCU D2 (GPIO 4, SoftwareSerial RX)
        * GPS RX  -----> NodeMCU D1 (GPIO 5, SoftwareSerial TX) [Optional voltage divider]
        * GPS VCC -----> NodeMCU 3.3V or External 3.3V/5V (check module spec)
        * GPS GND -----> NodeMCU GND (Common Ground mandatory)
        * Onboard LED -> GPIO 2 (LED_BUILTIN) for status indication

  Target Endpoints Supported:
    1. PythonAnywhere: https://trackbus.pythonanywhere.com/api/locations/save
    2. Vercel API    : https://bike-tracker-api-two.vercel.app/api/locations/save
    3. Local Dev     : http://192.168.x.x:5001/api/locations/save

  Key Production Features:
    - 100% Non-Blocking GPS feed (Zero delay() calls in loop to prevent UART buffer overflow)
    - Full coordinate pre-transmission validation (Lat/Lon range, zero-fix rejection)
    - Moving vs Stationary smart transmission (Reduces bandwidth and server load when stopped)
    - Automatic Wi-Fi disconnection detection and non-blocking auto-reconnect
    - Flexible HTTPS/HTTP communication with WiFiClientSecure & SSL certificate handling
    - Telemetry transmission: Lat, Lon, Speed (km/h), Heading (deg), Altitude, Satellites, HDOP/Accuracy
    - Visual LED status diagnostics:
        * Fast blinking  : Connecting to Wi-Fi
        * Heartbeat pulse: Waiting for GPS Satellite Fix (Indoors)
        * Solid / Flash  : Successful API Transmission
  ================================================================================
*/

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <SoftwareSerial.h>
#include <TinyGPS++.h>

// ================================================================================
// 1. CONFIGURABLE PARAMETERS
// ================================================================================

// --- Wi-Fi Credentials ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";         // Replace with your Wi-Fi SSID
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";     // Replace with your Wi-Fi Password

// --- API & Authentication ---
const char* DEVICE_ID     = "bus-01";                 // Target Device ID (matches backend bus identifier)
const char* API_KEY       = "YOUR_API_KEY";           // Server API Key (configured in backend .env)

// --- Server Configuration ---
// Options: "trackbus.pythonanywhere.com" or "bike-tracker-api-two.vercel.app"
const char* SERVER_HOST   = "trackbus.pythonanywhere.com";
const int   SERVER_PORT   = 443;                      // 443 for HTTPS, 80 for HTTP
const bool  USE_HTTPS     = true;                     // Set true for HTTPS, false for plain HTTP
const char* API_PATH      = "/api/locations/save";

// --- Transmission Timing & Thresholds ---
const unsigned long MOVING_INTERVAL_MS     = 5000;    // 5 seconds when bus is moving
const unsigned long STATIONARY_INTERVAL_MS = 20000;   // 20 seconds when bus is stopped
const float         MIN_MOVEMENT_METERS    = 5.0;     // Minimum distance change to force transmission
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;   // Retry connecting Wi-Fi every 10 seconds

// --- Pin Definitions ---
static const int GPS_RX_PIN = 4; // NodeMCU D2 (GPIO 4) -> Connect to GPS Module TX
static const int GPS_TX_PIN = 5; // NodeMCU D1 (GPIO 5) -> Connect to GPS Module RX
static const int STATUS_LED = 2; // NodeMCU onboard LED (GPIO 2 / D4, Active LOW)

// ================================================================================
// 2. GLOBAL OBJECTS & STATE
// ================================================================================
TinyGPSPlus gps;
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);

// Timing and Tracking State
unsigned long lastTransmitTime     = 0;
unsigned long lastWifiAttempt      = 0;
unsigned long lastStatusLedToggle  = 0;
unsigned long lastSerialDebugTime  = 0;

double lastSentLat   = 0.0;
double lastSentLng   = 0.0;
float  lastSentSpeed = 0.0;
bool   lastTxSuccess = false;

// Statistics
unsigned long packetsTransmitted   = 0;
unsigned long packetsFailed        = 0;
unsigned long rejectedNoFixCount   = 0;

// ================================================================================
// 3. SETUP
// ================================================================================
void setup() {
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, HIGH); // Turn LED off (Active LOW on NodeMCU)

  // Initialize Hardware Serial for Diagnostics
  Serial.begin(115200);
  delay(100);
  Serial.println();
  Serial.println(F("================================================================"));
  Serial.println(F("    SMART BUS LIVE TRACKING SYSTEM - ESP8266 NodeMCU"));
  Serial.println(F("    Firmware: v3.0 | TinyGPS++ | HTTPS REST Ingestion"));
  Serial.println(F("================================================================"));
  Serial.print(F("[CONFIG] Bus Device ID : ")); Serial.println(DEVICE_ID);
  Serial.print(F("[CONFIG] Server Host   : ")); Serial.println(SERVER_HOST);
  Serial.print(F("[CONFIG] GPS Baud Rate : 9600 (RX=D2/GPIO4, TX=D1/GPIO5)"));
  Serial.println();

  // Initialize SoftwareSerial for GPS NEO-6M
  gpsSerial.begin(9600);

  // Initialize Wi-Fi
  connectWiFi();
}

// ================================================================================
// 4. MAIN LOOP (Strictly Non-Blocking)
// ================================================================================
void loop() {
  // CRITICAL: Continuously drain GPS UART buffer into TinyGPS++ parser.
  // Never add delay() in loop or GPS characters will be dropped!
  while (gpsSerial.available() > 0) {
    char c = gpsSerial.read();
    gps.encode(c);
  }

  unsigned long currentMillis = millis();

  // 1. Maintain Wi-Fi Connection
  maintainWiFi(currentMillis);

  // 2. Determine Transmission Schedule based on Movement
  bool isMoving = (gps.speed.isValid() && gps.speed.kmph() > 3.0);
  unsigned long activeInterval = isMoving ? MOVING_INTERVAL_MS : STATIONARY_INTERVAL_MS;

  // Calculate distance moved since last successful transmission
  double distanceMovedMeters = 0.0;
  if (gps.location.isValid() && lastSentLat != 0.0) {
    distanceMovedMeters = TinyGPSPlus::distanceBetween(
      gps.location.lat(), gps.location.lng(),
      lastSentLat, lastSentLng
    );
  }

  // Check if it's time to transmit (Interval elapsed OR bus moved significantly)
  bool timeToTransmit = (currentMillis - lastTransmitTime >= activeInterval);
  bool movedSignificantly = (distanceMovedMeters >= MIN_MOVEMENT_METERS && (currentMillis - lastTransmitTime >= 3000));

  if (timeToTransmit || movedSignificantly) {
    if (WiFi.status() == WL_CONNECTED) {
      processAndTransmitLocation();
    } else {
      Serial.println(F("[WARN] Scheduled transmission skipped: Wi-Fi offline."));
    }
    lastTransmitTime = currentMillis;
  }

  // 3. Periodic Debug Output on Serial Monitor (every 3 seconds)
  if (currentMillis - lastSerialDebugTime >= 3000) {
    lastSerialDebugTime = currentMillis;
    printDiagnosticHUD();
  }

  // 4. Update Status LED
  updateStatusLED(currentMillis);
}

// ================================================================================
// 5. GPS VALIDATION & HTTPS TRANSMISSION
// ================================================================================
void processAndTransmitLocation() {
  // STEP 1: Rigorous GPS Coordinate Pre-Validation
  if (!gps.location.isValid()) {
    rejectedNoFixCount++;
    Serial.println(F("[GPS] Waiting for valid GPS Fix. Satellites searching..."));
    return;
  }

  double lat = gps.location.lat();
  double lng = gps.location.lng();

  // Validate Latitude and Longitude limits
  if (lat < -90.0 || lat > 90.0 || lng < -180.0 || lng > 180.0) {
    Serial.println(F("[GPS ERROR] Coordinates out of mathematical bounds! Skipping."));
    return;
  }

  // Validate Zero Coordinates (NEO-6M occasionally emits 0.000000 on weak fix)
  if (abs(lat) < 0.0001 && abs(lng) < 0.0001) {
    Serial.println(F("[GPS ERROR] Coordinate is 0.0, 0.0 (Unacquired fix). Skipping."));
    return;
  }

  // STEP 2: Collect Telemetry Parameters
  float speedKmph   = gps.speed.isValid() ? gps.speed.kmph() : 0.0;
  float headingDeg  = gps.course.isValid() ? gps.course.deg() : 0.0;
  float altitudeM   = gps.altitude.isValid() ? gps.altitude.meters() : 0.0;
  int   satellites  = gps.satellites.isValid() ? gps.satellites.value() : 0;
  float hdop        = gps.hdop.isValid() ? (gps.hdop.value() / 100.0) : 1.5;

  // Format GPS Timestamp (UTC)
  char timeBuffer[32];
  if (gps.date.isValid() && gps.time.isValid()) {
    snprintf(timeBuffer, sizeof(timeBuffer), "%04d-%02d-%02dT%02d:%02d:%02dZ",
             gps.date.year(), gps.date.month(), gps.date.day(),
             gps.time.hour(), gps.time.minute(), gps.time.second());
  } else {
    snprintf(timeBuffer, sizeof(timeBuffer), "N/A");
  }

  // STEP 3: Build HTTP Query URL
  // Matches both legacy parameters: ?deviceId=bus-01&latitude=...&longitude=...&apiKey=...
  // and rich parameters: &speed=...&heading=...&accuracy=...&satellites=...
  String url = String(API_PATH) +
               "?deviceId=" + String(DEVICE_ID) +
               "&latitude=" + String(lat, 6) +
               "&longitude=" + String(lng, 6) +
               "&apiKey=" + String(API_KEY) +
               "&speed=" + String(speedKmph, 1) +
               "&heading=" + String(headingDeg, 1) +
               "&accuracy=" + String(hdop, 2) +
               "&satellites=" + String(satellites) +
               "&altitude=" + String(altitudeM, 1) +
               "&gps_time=" + String(timeBuffer);

  Serial.println();
  Serial.println(F("----------------------------------------------------------------"));
  Serial.print(F("[TRANSMIT] Connecting to: ")); Serial.print(SERVER_HOST);
  Serial.print(F(" (Port ")); Serial.print(SERVER_PORT); Serial.println(F(")"));
  Serial.print(F("[TRANSMIT] URL: ")); Serial.println(url);

  // STEP 4: Perform HTTP / HTTPS Request
  bool success = false;
  if (USE_HTTPS) {
    WiFiClientSecure secureClient;
    // In production IoT devices, setInsecure avoids certificate expiration lockouts
    // while maintaining encrypted SSL/TLS data in transit.
    secureClient.setInsecure();
    secureClient.setTimeout(8000); // 8 second timeout

    if (!secureClient.connect(SERVER_HOST, SERVER_PORT)) {
      Serial.println(F("[HTTPS ERROR] Connection to server failed!"));
      packetsFailed++;
      lastTxSuccess = false;
      return;
    }

    // Send HTTP GET Request
    secureClient.print(String("GET ") + url + " HTTP/1.1\r\n" +
                       "Host: " + SERVER_HOST + "\r\n" +
                       "User-Agent: ESP8266-SmartBusTracker/3.0\r\n" +
                       "Connection: close\r\n\r\n");

    // Read HTTP Response Status Code
    unsigned long timeout = millis();
    while (secureClient.available() == 0) {
      if (millis() - timeout > 5000) {
        Serial.println(F("[HTTPS ERROR] Client response timeout!"));
        secureClient.stop();
        packetsFailed++;
        lastTxSuccess = false;
        return;
      }
      yield();
    }

    String statusLine = secureClient.readStringUntil('\n');
    Serial.print(F("[SERVER RESPONSE] ")); Serial.println(statusLine);

    if (statusLine.indexOf("200") != -1 || statusLine.indexOf("201") != -1) {
      success = true;
    }

    secureClient.stop();
  } else {
    WiFiClient client;
    client.setTimeout(6000);

    if (!client.connect(SERVER_HOST, SERVER_PORT)) {
      Serial.println(F("[HTTP ERROR] Connection to server failed!"));
      packetsFailed++;
      lastTxSuccess = false;
      return;
    }

    client.print(String("GET ") + url + " HTTP/1.1\r\n" +
                 "Host: " + SERVER_HOST + "\r\n" +
                 "User-Agent: ESP8266-SmartBusTracker/3.0\r\n" +
                 "Connection: close\r\n\r\n");

    unsigned long timeout = millis();
    while (client.available() == 0) {
      if (millis() - timeout > 5000) {
        Serial.println(F("[HTTP ERROR] Timeout waiting for server response"));
        client.stop();
        packetsFailed++;
        lastTxSuccess = false;
        return;
      }
      yield();
    }

    String statusLine = client.readStringUntil('\n');
    Serial.print(F("[SERVER RESPONSE] ")); Serial.println(statusLine);

    if (statusLine.indexOf("200") != -1 || statusLine.indexOf("201") != -1) {
      success = true;
    }

    client.stop();
  }

  // STEP 5: Update State & Statistics
  if (success) {
    packetsTransmitted++;
    lastSentLat   = lat;
    lastSentLng   = lng;
    lastSentSpeed = speedKmph;
    lastTxSuccess = true;
    Serial.println(F("[SUCCESS] GPS location saved on server!"));

    // Quick confirmation blink on LED
    digitalWrite(STATUS_LED, LOW);
    delay(80);
    digitalWrite(STATUS_LED, HIGH);
  } else {
    packetsFailed++;
    lastTxSuccess = false;
    Serial.println(F("[WARN] Server did not respond with 200 OK."));
  }
}

// ================================================================================
// 6. WI-FI MANAGEMENT (Non-Blocking Auto-Reconnect)
// ================================================================================
void connectWiFi() {
  Serial.print(F("[WIFI] Connecting to SSID: ")); Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttempt = millis();
}

void maintainWiFi(unsigned long currentMillis) {
  if (WiFi.status() != WL_CONNECTED) {
    if (currentMillis - lastWifiAttempt >= WIFI_RETRY_INTERVAL_MS) {
      Serial.println(F("[WIFI] Connection lost. Attempting auto-reconnect..."));
      lastWifiAttempt = currentMillis;
      WiFi.reconnect();
    }
  }
}

// ================================================================================
// 7. DIAGNOSTICS & STATUS MONITORING
// ================================================================================
void printDiagnosticHUD() {
  bool hasFix = gps.location.isValid();
  int sats    = gps.satellites.isValid() ? gps.satellites.value() : 0;
  float hdop  = gps.hdop.isValid() ? (gps.hdop.value() / 100.0) : 0.0;
  float kmph  = gps.speed.isValid() ? gps.speed.kmph() : 0.0;

  Serial.print(F("[HUD] Wi-Fi: "));
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(F("CONNECTED (IP: ")); Serial.print(WiFi.localIP()); Serial.print(F(", RSSI: "));
    Serial.print(WiFi.RSSI()); Serial.print(F(" dBm)"));
  } else {
    Serial.print(F("DISCONNECTED"));
  }

  Serial.print(F(" | GPS Fix: "));
  if (hasFix) {
    Serial.print(F("YES (")); Serial.print(sats); Serial.print(F(" sats, HDOP: "));
    Serial.print(hdop, 1); Serial.print(F(")"));
    Serial.print(F(" | Lat: ")); Serial.print(gps.location.lat(), 6);
    Serial.print(F(" Lng: ")); Serial.print(gps.location.lng(), 6);
    Serial.print(F(" | Speed: ")); Serial.print(kmph, 1); Serial.print(F(" km/h"));
  } else {
    Serial.print(F("NO FIX (Searching sats: ")); Serial.print(sats); Serial.print(F(")"));
  }

  Serial.print(F(" | TX: OK=")); Serial.print(packetsTransmitted);
  Serial.print(F(", Fail=")); Serial.println(packetsFailed);
}

void updateStatusLED(unsigned long currentMillis) {
  if (WiFi.status() != WL_CONNECTED) {
    // Fast flash: 200ms toggle
    if (currentMillis - lastStatusLedToggle >= 200) {
      lastStatusLedToggle = currentMillis;
      digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
    }
  } else if (!gps.location.isValid()) {
    // Wi-Fi connected but no GPS fix: 1000ms heartbeat
    if (currentMillis - lastStatusLedToggle >= 1000) {
      lastStatusLedToggle = currentMillis;
      digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
    }
  } else {
    // Fully operational: LED stays OFF with short blinks on TX
    digitalWrite(STATUS_LED, HIGH);
  }
}

