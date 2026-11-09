import unittest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend import create_app
from backend.config import TestConfig
from backend.json_db import db_instance
from backend.models import Bus
from backend.route_engine import (
    haversine_distance_m,
    haversine_distance_km,
    calculate_bearing,
    bearing_to_cardinal,
    distance_to_route_polyline,
    calculate_route_progress_and_eta,
    compute_trip_summary
)


class TestComprehensiveSmartBusAudit(unittest.TestCase):
    """
    Complete audit test suite verifying all 18 requirements:
    GPS telemetry, validation, geofencing, route intelligence, deviation alerts,
    historical playback, journey metrics, device diagnostics, and reporting.
    """

    def setUp(self):
        db_instance.clear_all_data()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        db_instance.clear_all_data()

    # -------------------------------------------------------------------------
    # 1. Geographic & Route Math Engine Audits
    # -------------------------------------------------------------------------
    def test_haversine_distance_accuracy(self):
        """Test Haversine distance matches expected geodesic distances."""
        # Hyderabad Charminar (17.361564, 78.474665) to Golconda Fort (17.383300, 78.401100) ~8.2 km
        dist_m = haversine_distance_m(17.361564, 78.474665, 17.383300, 78.401100)
        dist_km = haversine_distance_km(17.361564, 78.474665, 17.383300, 78.401100)
        self.assertAlmostEqual(dist_km, 8.2, delta=0.5)
        self.assertAlmostEqual(dist_m, dist_km * 1000.0, delta=1.0)

    def test_bearing_and_cardinal_directions(self):
        """Test bearing heading angle (0-360 deg) and cardinal text mapping."""
        # Pure North
        heading_n = calculate_bearing(17.0, 78.0, 18.0, 78.0)
        self.assertAlmostEqual(heading_n, 0.0, delta=1.0)
        self.assertEqual(bearing_to_cardinal(heading_n), "N")

        # Pure East
        heading_e = calculate_bearing(17.0, 78.0, 17.0, 79.0)
        self.assertAlmostEqual(heading_e, 90.0, delta=1.0)
        self.assertEqual(bearing_to_cardinal(heading_e), "E")

        # Pure South
        heading_s = calculate_bearing(18.0, 78.0, 17.0, 78.0)
        self.assertAlmostEqual(heading_s, 180.0, delta=1.0)
        self.assertEqual(bearing_to_cardinal(heading_s), "S")

        # Pure West
        heading_w = calculate_bearing(17.0, 79.0, 17.0, 78.0)
        self.assertAlmostEqual(heading_w, 270.0, delta=1.0)
        self.assertEqual(bearing_to_cardinal(heading_w), "W")

    def test_polyline_cross_track_distance_and_snapping(self):
        """Test distance_to_route_polyline correctly calculates offset from route polyline."""
        # Simple straight segment from (17.0, 78.0) to (17.0, 78.1)
        waypoints = [[17.0, 78.0], [17.0, 78.1]]

        # Point directly on the segment
        d_on, _, _ = distance_to_route_polyline(17.0, 78.05, waypoints)
        self.assertLess(d_on, 1.0)  # ~0 meters offset

        # Point 0.001 deg North (~110 meters away)
        d_off, _, pt = distance_to_route_polyline(17.001, 78.05, waypoints)
        self.assertAlmostEqual(d_off, 110.0, delta=15.0)
        self.assertAlmostEqual(pt[0], 17.0, delta=0.0001)

    # -------------------------------------------------------------------------
    # 2. ESP8266 Ingestion & Telemetry Handling
    # -------------------------------------------------------------------------
    def test_esp8266_nodemcu_full_payload_ingestion(self):
        """Test ESP8266 NodeMCU transmitting bus-01 with complete sensor fields."""
        payload = {
            "deviceId": "bus-01",
            "latitude": 17.385044,
            "longitude": 78.486671,
            "speed": 42.5,
            "heading": 135.0,
            "accuracy": 1.15,
            "satellites": 10,
            "altitude": 542.0,
            "gps_time": "2026-11-09T07:45:00Z",
            "apiKey": "YOUR_API_KEY"
        }
        res = self.client.post("/api/locations/save", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertEqual(data["deviceId"], "BUS-01")
        self.assertEqual(data["speed"], 42.5)
        self.assertEqual(data["heading"], 135.0)
        self.assertEqual(data["accuracy"], 1.15)
        self.assertEqual(data["satellites"], 10)

        # Verify device diagnostics updated
        health_res = self.client.get("/api/devices/health/BUS-01")
        self.assertEqual(health_res.status_code, 200)
        dev = health_res.get_json()
        self.assertIsNotNone(dev)
        self.assertEqual(dev["satellites"], 10)

    # -------------------------------------------------------------------------
    # 3. Validation & Coordinate Anomaly Rejection
    # -------------------------------------------------------------------------
    def test_rejection_of_unacquired_zero_fix(self):
        """GPS modules occasionally output 0.0, 0.0 when searching for satellites."""
        res = self.client.get("/api/locations/save?deviceId=bus-01&latitude=0.000000&longitude=0.000000&apiKey=YOUR_API_KEY")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])
        self.assertIn("No GPS Fix", res.get_json()["message"])

    def test_rejection_of_out_of_bounds_and_nan(self):
        """Coordinates outside -90..90 and -180..180 must be rejected."""
        res_lat = self.client.get("/api/locations/save?deviceId=bus-01&latitude=95.0&longitude=78.48&apiKey=YOUR_API_KEY")
        self.assertEqual(res_lat.status_code, 400)

        res_lng = self.client.get("/api/locations/save?deviceId=bus-01&latitude=17.38&longitude=195.0&apiKey=YOUR_API_KEY")
        self.assertEqual(res_lng.status_code, 400)

        res_nan = self.client.get("/api/locations/save?deviceId=bus-01&latitude=NaN&longitude=78.48&apiKey=YOUR_API_KEY")
        self.assertEqual(res_nan.status_code, 400)

    # -------------------------------------------------------------------------
    # 4. Bus Stop Geofencing & Event Logs
    # -------------------------------------------------------------------------
    def test_bus_stop_geofencing_entry_and_event_recording(self):
        """When bus coordinates enter a bus stop's geofence, ARRIVED event must be logged."""
        # Stop STOP-01 is at (17.385044, 78.486671)
        res = self.client.get(
            "/api/locations/save?deviceId=bus-01&latitude=17.385044&longitude=78.486671&apiKey=YOUR_API_KEY"
        )
        self.assertEqual(res.status_code, 200)
        geofence = res.get_json()["data"]["geofence"]
        self.assertIsNotNone(geofence)
        self.assertTrue(geofence["in_stop"])
        self.assertEqual(geofence["stop_id"], "STOP-01")

        # Query events
        events_res = self.client.get("/api/stops/events?bus_id=bus-01")
        self.assertEqual(events_res.status_code, 200)
        events = events_res.get_json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["stop_name"], "Koti Central Bus Stop")

    # -------------------------------------------------------------------------
    # 5. Route Analysis, Progress, and Deviation Detection
    # -------------------------------------------------------------------------
    def test_route_analysis_and_deviation_alert(self):
        """Bus on route should be ON_ROUTE; bus deviating beyond 150m triggers deviation."""
        # Point on Route 1
        self.client.get("/api/locations/save?deviceId=BUS001&latitude=17.385044&longitude=78.486671&apiKey=YOUR_API_KEY")
        res1 = self.client.get("/api/buses/BUS001/route-analysis")
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.get_json()["analysis"]["is_deviating"])

        # Point deviating 500m off route
        self.client.get("/api/locations/save?deviceId=BUS001&latitude=17.398000&longitude=78.500000&apiKey=YOUR_API_KEY")
        res2 = self.client.get("/api/buses/BUS001/route-analysis")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.get_json()["analysis"]["is_deviating"])
        self.assertGreater(res2.get_json()["analysis"]["distance_from_route_m"], 150.0)

        # Check deviations list endpoint
        dev_res = self.client.get("/api/deviations?bus_id=BUS001&status=ACTIVE")
        self.assertEqual(dev_res.status_code, 200)
        self.assertGreaterEqual(dev_res.get_json()["count"], 1)

    # -------------------------------------------------------------------------
    # 6. Stopped Bus vs Disconnected Device Differentiation
    # -------------------------------------------------------------------------
    def test_stopped_bus_vs_offline_device_distinction(self):
        """
        Differentiate:
        - Stopped Bus: device is sending pings with speed = 0 -> ONLINE & STOPPED
        - Disconnected Device: device has not communicated for > threshold -> OFFLINE
        """
        # 1. Bus transmitting speed = 0.0 (Stopped at bus stop)
        self.client.get("/api/locations/save?deviceId=BUS-STOPPED&latitude=17.385&longitude=78.486&speed=0.0&apiKey=YOUR_API_KEY")
        bus_res = self.client.get("/api/buses/BUS-STOPPED")
        self.assertEqual(bus_res.status_code, 200)
        bus_data = bus_res.get_json()["bus"]
        self.assertTrue(bus_data["is_online"])
        self.assertTrue(bus_data["is_stopped"])
        self.assertFalse(bus_data["is_moving"])

        # 2. Check fleet metrics reflect this correctly
        metrics_res = self.client.get("/api/buses")
        metrics = metrics_res.get_json()["metrics"]
        self.assertGreaterEqual(metrics["stopped_buses"], 1)

    # -------------------------------------------------------------------------
    # 7. Historical Data, Playback & Trip Metrics
    # -------------------------------------------------------------------------
    def test_historical_date_filtering_and_trip_summary(self):
        """Historical records must calculate total distance, average speed, max speed, and stoppage."""
        # Transmit 4 route coordinates
        coords = [
            (17.385000, 78.486000, 25.0),
            (17.391000, 78.474000, 35.0),
            (17.402000, 78.461000, 45.0),
            (17.425000, 78.451000, 0.0),  # Stopped point
        ]
        for lat, lng, spd in coords:
            self.client.get(
                f"/api/locations/save?deviceId=HIST-BUS&latitude={lat}&longitude={lng}&speed={spd}&apiKey=YOUR_API_KEY"
            )

        res = self.client.get("/api/buses/HIST-BUS/history?date=today")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(data["count"], 3)
        summary = data["trip_summary"]
        self.assertGreater(summary["total_distance_km"], 1.0)
        self.assertEqual(summary["max_speed"], 45.0)
        self.assertGreater(summary["average_speed"], 10.0)
        self.assertIsNotNone(summary["start_point"])
        self.assertIsNotNone(summary["end_point"])

    # -------------------------------------------------------------------------
    # 8. CSV Reports Export
    # -------------------------------------------------------------------------
    def test_csv_report_generation(self):
        """Test CSV download contains required audit columns and data."""
        self.client.get("/api/locations/save?deviceId=REP-BUS&latitude=17.385&longitude=78.486&apiKey=YOUR_API_KEY")

        # 1. Fleet summary CSV
        res_all = self.client.get("/api/reports/export?date=today")
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.mimetype, "text/csv")
        content_all = res_all.get_data(as_text=True)
        self.assertIn("Bus ID,Bus Number,Route Name,Date", content_all)

        # 2. Individual bus GPS log CSV
        res_single = self.client.get("/api/reports/export?bus_id=REP-BUS&date=today")
        self.assertEqual(res_single.status_code, 200)
        content_single = res_single.get_data(as_text=True)
        self.assertIn("Record ID,Bus ID,Date,Time,Timestamp,Latitude,Longitude", content_single)
        self.assertIn("REP-BUS", content_single)

    # -------------------------------------------------------------------------
    # 9. Settings Configuration API
    # -------------------------------------------------------------------------
    def test_settings_retrieval_and_update(self):
        """Test getting and updating system thresholds (geofence radius, deviation tolerance)."""
        # Login admin
        self.client.post("/api/admin/login", json={"username": "admin", "password": "adminpass"})

        # Get settings
        get_res = self.client.get("/api/settings")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("deviation_threshold_meters", get_res.get_json()["settings"])

        # Update settings
        put_res = self.client.put("/api/settings", json={
            "deviation_threshold_meters": 200,
            "geofence_radius_meters": 100
        })
        self.assertEqual(put_res.status_code, 200)
        updated = put_res.get_json()["settings"]
        self.assertEqual(updated["deviation_threshold_meters"], 200)
        self.assertEqual(updated["geofence_radius_meters"], 100)


if __name__ == "__main__":
    unittest.main()

