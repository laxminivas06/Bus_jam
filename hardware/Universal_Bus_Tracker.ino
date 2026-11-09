/*
 * ================================================================================================
 * SMART BUS LIVE TRACKING SYSTEM - UNIVERSAL ARDUINO GPS FIRMWARE
 * ================================================================================================
 * Hardware: ESP8266 (NodeMCU v2/v3, WeMos D1 Mini) & ESP32 (DevKit, WROOM)
 * GPS Module: U-Blox NEO-6M / NEO-8M / SAM-M8Q (9600 Baud)
 * Server Endpoint: /api/locations/save
 * ================================================================================================
 */

// ======================================
// UNIVERSAL BUS TRACKING CONFIGURATION
// ======================================

#define BUS_NUMBER "BUS-001"
#define DEVICE_ID  "AIV-DEV-001"

// Set your backend server URL (supports both http:// and https://)
const char* SERVER_URL = "http://192.168.1.100:5001"; // Or "https://your-deployed-server.com"

// ======================================
// NETWORK & API CREDENTIALS
// ======================================
const char* ssid     = "College_WiFi";
const char* password = "College@2026";
const char* apiKey   = "default_secret_api_key_12345";

// Transmission interval (milliseconds) - non-blocking!
const unsigned long sendInterval = 5000; // Send GPS update every 5 seconds

// ----------------------------------------------------------------------
// Microcontroller & Hardware Pin Setup
// ----------------------------------------------------------------------
#include <TinyGPS++.h>

#if defined(ESP8266)
  // ESP8266 Architecture (NodeMCU, D1 Mini)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
  #include <WiFiClientSecure.h>
  #include <SoftwareSerial.h>

  // NodeMCU: D2 connects to GPS TX, D1 connects to GPS RX
  const int RXPin = 4; // NodeMCU D2 (GPIO4)
  const int TXPin = 5; // NodeMCU D1 (GPIO5)
  SoftwareSerial gpsSerial(RXPin, TXPin);

#elif defined(ESP32)
  // ESP32 Architecture (DevKit v1, WROOM)
  #include <WiFi.h>
  #include <HTTPClient.h>
  #include <WiFiClient.h>
  #include <WiFiClientSecure.h>
  #include <HardwareSerial.h>

  // ESP32: GPIO16 (RX2) connects to GPS TX, GPIO17 (TX2) connects to GPS RX
  const int RXPin = 16;
  const int TXPin = 17;
  HardwareSerial gpsSerial(2);

#else
  // Standard Arduino AVR (UNO / Mega / Nano)
  #include <SoftwareSerial.h>
  const int RXPin = 10;
  const int TXPin = 11;
  SoftwareSerial gpsSerial(RXPin, TXPin);
#endif

const uint32_t GPSBaud = 9600;
TinyGPSPlus gps;

// Timing & state tracker (Non-blocking execution)
unsigned long lastSendTime = 0;
unsigned long lastWifiCheck = 0;

// Function Declaration
void sendLocationHTTPS(float lat, float lng, float speed, float heading, int satellites, float accuracy, float altitude);
void connectWiFi();

// ================================================================================================
// SETUP
// ================================================================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=================================================");
  Serial.println("   SPHOORTHY CAMPUS LEAD - SMART BUS TRACKER     ");
  Serial.print("   Bus Number: "); Serial.println(BUS_NUMBER);
  Serial.print("   Device ID:  "); Serial.println(DEVICE_ID);
  Serial.print("   Server:     "); Serial.println(SERVER_URL);
  Serial.println("=================================================");

  // Initialize GPS Serial at 9600 baud
#if defined(ESP32)
  gpsSerial.begin(GPSBaud, SERIAL_8N1, RXPin, TXPin);
#else
  gpsSerial.begin(GPSBaud);
#endif

  // Connect to Wi-Fi
  connectWiFi();
}

// ================================================================================================
// WI-FI CONNECTION & RECOVERY
// ================================================================================================
void connectWiFi() {
  Serial.print("Connecting to Wi-Fi SSID: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnected to Wi-Fi successfully!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWi-Fi connection pending. Background reconnection active.");
  }
}

// ================================================================================================
// MAIN LOOP (NON-BLOCKING)
// ================================================================================================
void loop() {
  // 1. Feed the GPS parser with data from Serial continuously (non-blocking)
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }

  // 2. Automatic Wi-Fi reconnection check every 5 seconds
  if (millis() - lastWifiCheck >= 5000) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi disconnected! Reconnecting...");
      WiFi.reconnect();
    }
  }

  // 3. Non-blocking periodic GPS location transmission
  if (millis() - lastSendTime >= sendInterval) {
    lastSendTime = millis();

    // Check if GPS has a valid fix
    if (gps.location.isValid()) {
      float latitude = gps.location.lat();
      float longitude = gps.location.lng();

      // Reject unacquired zero coordinates (0.0, 0.0)
      if (abs(latitude) > 0.0001 && abs(longitude) > 0.0001) {
        float speed = gps.speed.isValid() ? (float)gps.speed.kmph() : 0.0f;
        float heading = gps.course.isValid() ? (float)gps.course.deg() : 0.0f;
        int satellites = gps.satellites.isValid() ? gps.satellites.value() : 0;
        float accuracy = gps.hdop.isValid() ? (float)gps.hdop.hdop() : 1.5f;
        float altitude = gps.altitude.isValid() ? (float)gps.altitude.meters() : 500.0f;

        Serial.println("\n-------------------------------------------------");
        Serial.print("Valid Fix Acquired - Lat: ");
        Serial.print(latitude, 6);
        Serial.print(", Lng: ");
        Serial.print(longitude, 6);
        Serial.print(" | Speed: ");
        Serial.print(speed, 1);
        Serial.print(" km/h | Sats: ");
        Serial.println(satellites);

        sendLocationHTTPS(latitude, longitude, speed, heading, satellites, accuracy, altitude);
      } else {
        Serial.println("GPS Fix pending: Waiting for valid non-zero satellite coordinates...");
      }
    } else {
      Serial.print("Searching for satellites... Sats visible: ");
      Serial.println(gps.satellites.isValid() ? gps.satellites.value() : 0);
    }
  }
}

// ================================================================================================
// HTTPS / HTTP LOCATION TRANSMISSION
// ================================================================================================
void sendLocationHTTPS(float lat, float lng, float speed, float heading, int satellites, float accuracy, float altitude) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Cannot send: Wi-Fi is disconnected.");
    return;
  }

  String serverStr = String(SERVER_URL);
  bool isHttps = serverStr.startsWith("https://");

  WiFiClient plainClient;
  WiFiClientSecure secureClient;

  // Skip SSL certificate validation for ease of development
  if (isHttps) {
    secureClient.setInsecure();
  }

  HTTPClient http;

  // Format the complete URL string with parameters (UDIP v1.0 Standard)
  String fullUrl = serverStr;
  if (!fullUrl.endsWith("/")) {
    fullUrl += "/";
  }
  fullUrl += "api/locations/save";
  fullUrl += "?bus_number=" + String(BUS_NUMBER);
  fullUrl += "&deviceId=" + String(DEVICE_ID);
  fullUrl += "&latitude=" + String(lat, 6);
  fullUrl += "&longitude=" + String(lng, 6);
  fullUrl += "&speed=" + String(speed, 1);
  fullUrl += "&heading=" + String(heading, 1);
  fullUrl += "&satellites=" + String(satellites);
  fullUrl += "&accuracy=" + String(accuracy, 1);
  fullUrl += "&altitude=" + String(altitude, 1);
  fullUrl += "&apiKey=" + String(apiKey);

  Serial.print("Sending Request: ");
  Serial.println(fullUrl);

  bool beginSuccess = isHttps ? http.begin(secureClient, fullUrl) : http.begin(plainClient, fullUrl);

  if (beginSuccess) {
    http.setTimeout(4000);
    int httpCode = http.GET(); // Execute GET request

    if (httpCode > 0) {
      Serial.printf("[HTTP] GET... code: %d\n", httpCode);
      if (httpCode == HTTP_CODE_OK) {
        String payload = http.getString();
        Serial.println("Server Response:");
        Serial.println(payload);
      }
    } else {
      Serial.printf("[HTTP] GET... failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("[HTTP] Unable to connect to server.");
  }
}
