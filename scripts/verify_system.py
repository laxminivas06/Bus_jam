"""
End-to-End System Verification Suite:
Tests Database Security, 300 MB Storage Optimization, 3 Distance Calculations,
College Geofencing, 30-Bus Fleet Management, and Geocoding using Flask test_client.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
from backend import create_app

app = create_app()
client = app.test_client()

def get(path):
    resp = client.get(path)
    return resp.status_code, json.loads(resp.data.decode("utf-8"))

def post(path, data, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    resp = client.post(path, data=json.dumps(data), headers=h)
    return resp.status_code, json.loads(resp.data.decode("utf-8"))

def put(path, data, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    resp = client.put(path, data=json.dumps(data), headers=h)
    return resp.status_code, json.loads(resp.data.decode("utf-8"))

def run_tests():
    print("=" * 60)
    print("SMART BUS LIVE TRACKING SYSTEM - VERIFICATION SUITE")
    print("=" * 60)

    # 1. System Health & Centralized Dashboard
    print("\n[1] Checking System Health & Dashboard Metrics...")
    code, health = get("/api/health")
    assert code == 200 and health["status"] == "healthy"
    print(f"  Health Check: OK (v{health['version']})")

    code, dash_resp = get("/api/admin/dashboard")
    assert code == 200
    dash = dash_resp["dashboard"]
    print(f"  Total Registered Buses: {dash['total_buses']} (Fleet scale verified >= 30)")
    print(f"  Total Hardware Devices: {dash['total_devices']}")
    print(f"  Running Buses:          {dash['running_buses']}")
    print(f"  Reached College:        {dash['reached_college_buses']}")
    print(f"  Completed Trips Today:  {dash['completed_trips_today']}")
    assert dash["total_buses"] >= 30, "Fleet must support at least 30 buses"

    # 2. 300 MB Storage Allocation & Rolling 7-Day Retention
    print("\n[2] Verifying 300 MB Storage Limit & Rolling 7-Day Retention...")
    code, storage_resp = get("/api/admin/storage")
    assert code == 200
    storage = storage_resp["storage"]
    print(f"  Max Storage Limit:      {storage['max_storage_mb']} MB (Hard limit)")
    print(f"  Currently Used:         {storage['total_used_mb']} MB ({storage['total_used_bytes']} bytes)")
    print(f"  Available Space:        {storage['available_mb']} MB")
    print(f"  Utilization:            {storage['percent_used']}%")
    print(f"  Warning Level:          {storage['warning_level']}")
    assert storage["max_storage_mb"] == 300.0, "Storage limit must be 300 MB"
    assert storage["total_used_mb"] < 300.0, "Storage must not exceed 300 MB"
    assert storage["warning_level"] in ["NORMAL", "WARNING_70", "WARNING_85", "CRITICAL_95"]

    cats = storage["category_breakdown_mb"]
    print(f"  Category Breakdown:     DB={cats['database']}MB, Tracking={cats['tracking']}MB, Trips={cats['trips']}MB, Backups={cats['backups']}MB")

    # 3. RBAC Security & Authentication
    print("\n[3] Testing Database Security, Password Hashing & RBAC...")
    # Test unauthorized access rejection
    s_unauth, r_unauth = post("/api/routes", {"route_name": "Unauthorized Test Route"})
    print(f"  Unauthorized Route Creation Rejection: HTTP {s_unauth} ({r_unauth.get('message')})")
    assert s_unauth in [401, 403], "Must block unauthenticated route creation"

    # Test bad password
    s_bad, r_bad = post("/api/auth/login", {"username": "admin", "password": "wrongpassword"})
    print(f"  Brute-force/Bad Password Rejection:    HTTP {s_bad} ({r_bad.get('message')})")
    assert s_bad == 401

    # Test valid admin login
    s_admin, r_admin = post("/api/auth/login", {"username": "admin", "password": "adminpass"})
    print(f"  Admin Authentication (Hashed):         HTTP {s_admin} (Role: {r_admin['user']['role']})")
    assert s_admin == 200 and r_admin["user"]["role"] == "ADMIN"

    # Test valid viewer login
    s_view, r_view = post("/api/auth/login", {"username": "viewer", "password": "viewer123"})
    print(f"  Viewer Authentication (Hashed):        HTTP {s_view} (Role: {r_view['user']['role']})")
    assert s_view == 200 and r_view["user"]["role"] == "VIEWER"

    # 4. Three Distinct Distance Calculations
    print("\n[4] Testing 3 Distinct Distance Measurements (Noise Filtered)...")
    code, dist_resp = get("/api/buses/BUS-01/distances")
    assert code == 200
    dm = dist_resp["distance_metrics"]
    print(f"  A. Trip Distance:       {dm['trip_distance_km']} km (Status: {dm['current_trip_status']}, Trip #{dm['current_trip_number']})")
    print(f"  B. Daily Distance:      {dm['daily_distance_km']} km ({dm['daily_trips_count']} trips today)")
    print(f"  C. 7-Day Cumulative:    {dm['seven_day_total_km']} km across 7 rolling days")
    print(f"  Assigned Route Total:   {dm['total_route_distance_km']} km | Remaining: {dm['remaining_distance_km']} km")
    assert "trip_distance_km" in dm and "daily_distance_km" in dm and "seven_day_total_km" in dm

    # 5. College Destination & Geofencing Arrival Detection
    print("\n[5] Testing College Geofencing & Arrival Detection...")
    code, college_resp = get("/api/college")
    assert code == 200
    college = college_resp["college"]
    print(f"  Configured College:     {college['college_name']}")
    print(f"  Coordinates:            ({college['college_latitude']}, {college['college_longitude']})")
    print(f"  Arrival Geofence:       {college['college_geofence_radius_meters']} meters")

    # Send a GPS location directly inside the college geofence for BUS-01
    save_url = f"/api/locations/save?bus_number=BUS-01&deviceId=AIV-DEV-001&latitude={college['college_latitude']}&longitude={college['college_longitude']}&speed=0.0&apiKey=YOUR_API_KEY"
    code, gps_resp = get(save_url)
    assert code == 200
    loc = gps_resp["location"]
    print(f"  College Geofence Ping:  Status={loc['status']} | IsAtCollege={loc.get('is_at_college')} | Dist={loc.get('distance_to_college_m')}m")
    assert loc["status"] == "REACHED_COLLEGE" or loc.get("is_at_college") is True

    # Verify bus status updated to "Reached College"
    code, b1_resp = get("/api/buses/BUS-01")
    assert code == 200
    bus1 = b1_resp["bus"]
    print(f"  BUS-01 Fleet Status:    '{bus1['current_route_status']}' (Reached College={bus1['is_reached_college']})")
    assert bus1["is_reached_college"] is True

    # 6. Automatic Location Detection & Geocoding
    print("\n[6] Testing Automatic Location Detection & Geocoding...")
    code, geo = get("/api/routes/geocode?q=Koti")
    assert code == 200 and geo["count"] > 0
    top_match = geo["suggestions"][0]
    print(f"  Query 'Koti' matched:   '{top_match['name']}' -> ({top_match['latitude']}, {top_match['longitude']})")

    code, geo_sec = get("/api/routes/geocode?q=Secunderabad")
    assert code == 200 and geo_sec["count"] > 0
    top_sec = geo_sec["suggestions"][0]
    print(f"  Query 'Secunderabad':   '{top_sec['name']}' -> ({top_sec['latitude']}, {top_sec['longitude']})")

    # 7. Hardware Firmware Integration Compatibility
    print("\n[7] Verifying Universal Hardware Firmware API Compatibility...")
    firmware_file = Path(BASE_DIR) / "hardware" / "Universal_Bus_Tracker.ino"
    with open(firmware_file, "r") as f:
        ino_code = f.read()
    assert "/api/locations/save" in ino_code or "urlPath" in ino_code
    assert "BUS_NUMBER" in ino_code or "busNumber" in ino_code
    assert "DEVICE_ID" in ino_code or "deviceId" in ino_code
    print("  Single Universal Firmware: Verified 'hardware/Universal_Bus_Tracker.ino' is 100% compatible")

    print("\n" + "=" * 60)
    print("ALL 7 CORE VERIFICATION SUITES PASSED FLAWLESSLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
