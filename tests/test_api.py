import unittest
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend import create_app
from backend.config import TestConfig
from backend.json_db import db_instance
from backend.models import Bus


class TestSmartBusAPI(unittest.TestCase):
    def setUp(self):
        db_instance.clear_all_data()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        db_instance.clear_all_data()

    def test_health_check(self):
        """Test health endpoint returns healthy JSON."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["storage"], "json")
        self.assertIn("timestamp", data)

    def test_clean_initial_state_empty_buses(self):
        """Test that initially there are zero buses registered."""
        response = self.client.get("/api/buses")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["metrics"]["total_buses"], 0)
        self.assertEqual(data["metrics"]["online_buses"], 0)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["buses"], [])

    def test_esp8266_locations_save_with_rich_telemetry(self):
        """
        Test ESP8266 / Arduino GET & POST /api/locations/save with rich telemetry:
        deviceId=bus-01, latitude, longitude, apiKey, speed, heading, satellites, accuracy
        """
        url = (
            "/api/locations/save?deviceId=bus-01&latitude=17.385044&longitude=78.486671"
            "&apiKey=YOUR_API_KEY&speed=35.5&heading=120.0&satellites=9&accuracy=1.2"
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Location saved")
        self.assertEqual(data["data"]["deviceId"], "BUS-01")
        self.assertEqual(data["data"]["latitude"], 17.385044)
        self.assertEqual(data["data"]["longitude"], 78.486671)
        self.assertEqual(data["data"]["speed"], 35.5)
        self.assertEqual(data["data"]["satellites"], 9)
        self.assertIn("cardinal", data["data"])

        # Verify bus is registered and online
        bus_res = self.client.get("/api/buses/BUS-01")
        self.assertEqual(bus_res.status_code, 200)
        bus_data = bus_res.get_json()["bus"]
        self.assertEqual(bus_data["bus_id"], "BUS-01")
        self.assertTrue(bus_data["is_online"])
        self.assertTrue(bus_data["is_moving"])
        self.assertFalse(bus_data["is_stopped"])

    def test_locations_save_validation_and_gps_fix(self):
        """Test rejection of invalid coordinates, zero-fix coordinates, and missing keys."""
        # 1. Invalid API key
        res_bad_key = self.client.get("/api/locations/save?deviceId=BUS001&latitude=17.385&longitude=78.486&apiKey=BAD_KEY")
        self.assertEqual(res_bad_key.status_code, 401)

        # 2. Missing deviceId
        res_no_dev = self.client.get("/api/locations/save?latitude=17.385&longitude=78.486&apiKey=YOUR_API_KEY")
        self.assertEqual(res_no_dev.status_code, 400)

        # 3. Missing coordinates
        res_no_coords = self.client.get("/api/locations/save?deviceId=BUS001&apiKey=YOUR_API_KEY")
        self.assertEqual(res_no_coords.status_code, 400)

        # 4. Zero coordinates (No GPS fix acquired)
        res_zero = self.client.get("/api/locations/save?deviceId=BUS001&latitude=0.0&longitude=0.0&apiKey=YOUR_API_KEY")
        self.assertEqual(res_zero.status_code, 400)
        self.assertIn("Zero latitude and longitude", res_zero.get_json()["message"])

        # 5. Out of range coordinates
        res_bad_lat = self.client.get("/api/locations/save?deviceId=BUS001&latitude=120.0&longitude=78.486&apiKey=YOUR_API_KEY")
        self.assertEqual(res_bad_lat.status_code, 400)

    def test_route_analysis_and_deviation_detection(self):
        """
        Test route analysis:
        - When bus is on Route 1 -> is_deviating is False
        - When bus moves away (> 150m) -> is_deviating is True and deviation logged
        """
        # Point on Route 1 (Koti: 17.385044, 78.486671)
        self.client.get("/api/locations/save?deviceId=BUS001&latitude=17.385044&longitude=78.486671&apiKey=YOUR_API_KEY")

        analysis_res = self.client.get("/api/buses/BUS001/route-analysis")
        self.assertEqual(analysis_res.status_code, 200)
        analysis_data = analysis_res.get_json()["analysis"]
        self.assertFalse(analysis_data["is_deviating"])
        self.assertLess(analysis_data["distance_from_route_m"], 50.0)
        self.assertGreater(len(analysis_data["upcoming_stops"]), 0)

        # Send deviating coordinates far off Route 1 (e.g. 17.480000, 78.580000 > 10km away)
        self.client.get("/api/locations/save?deviceId=BUS001&latitude=17.480000&longitude=78.580000&apiKey=YOUR_API_KEY")

        analysis_dev = self.client.get("/api/buses/BUS001/route-analysis")
        self.assertEqual(analysis_dev.status_code, 200)
        dev_data = analysis_dev.get_json()["analysis"]
        self.assertTrue(dev_data["is_deviating"])
        self.assertGreater(dev_data["distance_from_route_m"], 150.0)

        # Check deviations API
        dev_list_res = self.client.get("/api/deviations?bus_id=BUS001")
        self.assertEqual(dev_list_res.status_code, 200)
        self.assertGreater(dev_list_res.get_json()["count"], 0)

    def test_bus_stop_geofencing_detection(self):
        """
        Test arrival detection when a bus enters a bus stop geofence radius.
        """
        # STOP-01 is at (17.385044, 78.486671) with radius 80m
        res = self.client.get(
            "/api/locations/save?deviceId=BUS002&latitude=17.385050&longitude=78.486675&apiKey=YOUR_API_KEY"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertIsNotNone(data["geofence"])
        self.assertTrue(data["geofence"]["in_stop"])
        self.assertEqual(data["geofence"]["stop_id"], "STOP-01")

        # Check recorded stop events
        events_res = self.client.get("/api/stops/events?bus_id=BUS002")
        self.assertEqual(events_res.status_code, 200)
        events = events_res.get_json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["stop_id"], "STOP-01")
        self.assertEqual(events[0]["event_type"], "ARRIVED")

    def test_date_wise_history_and_trip_summary(self):
        """Test recording history and retrieving trip metrics (distance, avg speed, max speed)."""
        # Send 3 coordinates
        self.client.get("/api/locations/save?deviceId=BUS003&latitude=17.385000&longitude=78.486000&speed=20.0&apiKey=YOUR_API_KEY")
        self.client.get("/api/locations/save?deviceId=BUS003&latitude=17.389000&longitude=78.480000&speed=40.0&apiKey=YOUR_API_KEY")
        self.client.get("/api/locations/save?deviceId=BUS003&latitude=17.394000&longitude=78.475000&speed=30.0&apiKey=YOUR_API_KEY")

        hist_res = self.client.get("/api/buses/BUS003/history?date=today")
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.get_json()
        self.assertGreaterEqual(hist_data["count"], 2)
        summary = hist_data["trip_summary"]
        self.assertIsNotNone(summary)
        self.assertGreater(summary["total_distance_km"], 0.0)
        self.assertGreater(summary["max_speed"], 35.0)

    def test_device_health_monitoring(self):
        """Test device health endpoint records packet count and online/offline status."""
        self.client.get("/api/locations/save?deviceId=bus-01&latitude=17.385&longitude=78.486&satellites=10&accuracy=1.1&apiKey=YOUR_API_KEY")

        health_res = self.client.get("/api/devices/health")
        self.assertEqual(health_res.status_code, 200)
        devices = health_res.get_json()["devices"]
        self.assertGreaterEqual(len(devices), 1)
        dev = next((d for d in devices if d["device_id"] == "BUS-01"), None)
        self.assertIsNotNone(dev)
        self.assertTrue(dev["is_online"])
        self.assertEqual(dev["satellites"], 10)

    def test_csv_report_export(self):
        """Test CSV export returns valid CSV content."""
        self.client.get("/api/locations/save?deviceId=BUS004&latitude=17.385&longitude=78.486&apiKey=YOUR_API_KEY")

        csv_res = self.client.get("/api/reports/export?bus_id=BUS004&date=today")
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, "text/csv")
        csv_text = csv_res.get_data(as_text=True)
        self.assertIn("Record ID", csv_text)
        self.assertIn("BUS004", csv_text)

    def test_admin_crud_lifecycle(self):
        """Test admin authentication, creating, updating, and deleting buses."""
        # 1. Login with bad credentials
        bad_login = self.client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
        self.assertEqual(bad_login.status_code, 401)

        # 2. Login with valid credentials
        login_res = self.client.post("/api/admin/login", json={"username": "admin", "password": "adminpass"})
        self.assertEqual(login_res.status_code, 200)

        # 3. Create a new bus
        new_bus_data = {
            "bus_id": "BUS050",
            "bus_number": "TS 09 UB 5050",
            "route_name": "Route 50: Campus Express",
            "driver_name": "Rajesh Kumar",
            "driver_phone": "+91 98480 50505",
            "capacity": 52
        }
        create_res = self.client.post("/api/admin/buses", json=new_bus_data)
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(create_res.get_json()["bus"]["bus_id"], "BUS050")

        # 4. Update the bus
        update_res = self.client.put("/api/admin/buses/BUS050", json={"driver_name": "Rajesh K."})
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.get_json()["bus"]["driver_name"], "Rajesh K.")

        # 5. Delete the bus
        delete_res = self.client.delete("/api/admin/buses/BUS050")
        self.assertEqual(delete_res.status_code, 200)

        # 6. Verify deleted
        get_res = self.client.get("/api/buses/BUS050")
        self.assertEqual(get_res.status_code, 404)

    def test_seven_day_retention_and_automated_backup(self):
        """Test rolling 7-day data retention: older records deleted, valid kept, backups created & pruned."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        ten_days_ago = now - timedelta(days=10)
        two_days_ago = now - timedelta(days=2)

        # Insert historical records directly: 1 old (10 days ago), 1 recent (2 days ago)
        db_instance.add_location_history(
            bus_id="RET-BUS", lat=17.385, lng=78.486, speed=30.0,
            timestamp=ten_days_ago
        )
        db_instance.add_location_history(
            bus_id="RET-BUS", lat=17.390, lng=78.490, speed=35.0,
            timestamp=two_days_ago
        )

        all_hist_before = db_instance._read_json(db_instance.history_file, default=[])
        self.assertEqual(len(all_hist_before), 2)

        # Trigger retention cleanup
        res = self.client.post("/api/retention/cleanup")
        self.assertEqual(res.status_code, 200)
        cleanup_data = res.get_json()
        self.assertEqual(cleanup_data["status"], "success")
        self.assertEqual(cleanup_data["retention_days"], 7)
        self.assertEqual(cleanup_data["pruned_history_records"], 1)

        # Verify active storage only has 1 record (the recent one)
        all_hist_after = db_instance._read_json(db_instance.history_file, default=[])
        self.assertEqual(len(all_hist_after), 1)
        self.assertAlmostEqual(all_hist_after[0]["latitude"], 17.390, places=3)

        # Verify automated backup snapshot was created
        backup_files = list(db_instance.backups_dir.glob("*.json"))
        self.assertGreaterEqual(len(backup_files), 1)

    def test_sphoorthy_campus_lead_grouping(self):
        """Test Sphoorthy Campus Lead grouping and filtering."""
        # Register a bus with default Sphoorthy Campus Lead
        self.client.post("/api/buses", json={
            "bus_id": "SPH-01",
            "bus_number": "TS 08 UB 2001",
            "device_id": "esp8266-sph-01",
            "campus": "Sphoorthy Campus Lead"
        })

        # Test campuses list endpoint
        camp_res = self.client.get("/api/campuses")
        self.assertEqual(camp_res.status_code, 200)
        campuses = camp_res.get_json()["campuses"]
        self.assertTrue(any(c["name"] == "Sphoorthy Campus Lead" for c in campuses))

        # Test buses filter by campus
        bus_res = self.client.get("/api/buses?campus=Sphoorthy Campus Lead")
        self.assertEqual(bus_res.status_code, 200)
        buses = bus_res.get_json()["buses"]
        self.assertTrue(any(b["bus_id"] == "SPH-01" for b in buses))


if __name__ == "__main__":
    unittest.main()
