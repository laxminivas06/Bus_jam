"""
Seed Fleet Script: Seeds 4 Sphoorthy Campus buses, hardware devices, and 7-day route history.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import datetime, timezone, timedelta
from backend.json_db import db_instance
from backend.models import Bus

def seed():
    print("Clearing old test data...")
    db_instance.clear_all_data()

    now = datetime.now(timezone.utc)

    buses = [
        {
            "bus_id": "BUS-01",
            "bus_name": "Campus Express 01",
            "bus_number": "TS 09 UB 1001",
            "device_id": "AIV-DEV-001",
            "route_id": "ROUTE-01",
            "route_name": "Route 01: Koti Central - Campus Main",
            "driver_name": "Ramesh Kumar",
            "driver_phone": "+91 98480 11001",
            "capacity": 52,
            "campus": "Sphoorthy Campus Lead",
            "is_active": True,
            "device_type": "ESP8266",
            "mac_address": "24:6F:28:1A:BC:01"
        },
        {
            "bus_id": "BUS-02",
            "bus_name": "Campus Express 02",
            "bus_number": "TS 09 UB 1002",
            "device_id": "AIV-DEV-002",
            "route_id": "ROUTE-02",
            "route_name": "Route 02: Secunderabad - Campus Main",
            "driver_name": "Suresh Reddy",
            "driver_phone": "+91 98480 11002",
            "capacity": 52,
            "campus": "Sphoorthy Campus Lead",
            "is_active": True,
            "device_type": "ESP32",
            "mac_address": "24:6F:28:1A:BC:02"
        },
        {
            "bus_id": "BUS-03",
            "bus_name": "Campus Express 03",
            "bus_number": "TS 09 UB 1003",
            "device_id": "AIV-DEV-003",
            "route_id": "ROUTE-03",
            "route_name": "Route 03: LB Nagar - Malakpet",
            "driver_name": "Venkat Rao",
            "driver_phone": "+91 98480 11003",
            "capacity": 48,
            "campus": "Sphoorthy Campus Lead",
            "is_active": True,
            "device_type": "ARDUINO_CELLULAR",
            "mac_address": "86:49:32:05:12:34:03"
        },
        {
            "bus_id": "BUS-04",
            "bus_name": "Campus Express 04",
            "bus_number": "TS 09 UB 1004",
            "device_id": "AIV-DEV-004",
            "route_id": "ROUTE-01",
            "route_name": "Route 01: Koti Central - Campus Main",
            "driver_name": "Mohammed Ali",
            "driver_phone": "+91 98480 11004",
            "capacity": 52,
            "campus": "Sphoorthy Campus Lead",
            "is_active": True,
            "device_type": "ESP8266",
            "mac_address": "24:6F:28:1A:BC:04"
        }
    ]

    for b_data in buses:
        # Save Bus
        bus = Bus(
            bus_id=b_data["bus_id"],
            bus_name=b_data["bus_name"],
            bus_number=b_data["bus_number"],
            device_id=b_data["device_id"],
            route_id=b_data["route_id"],
            route_name=b_data["route_name"],
            driver_name=b_data["driver_name"],
            driver_phone=b_data["driver_phone"],
            capacity=b_data["capacity"],
            campus=b_data["campus"],
            is_active=b_data["is_active"]
        )
        bus.save()

        # Register Device
        dev = db_instance.register_device({
            "device_id": b_data["device_id"],
            "device_name": f"{b_data['bus_name']} Tracker ({b_data['device_id']})",
            "mac_address": b_data["mac_address"],
            "device_type": b_data["device_type"],
            "assigned_bus_id": b_data["bus_id"]
        })

    # Seed 7 days of route history for BUS-01 and BUS-02
    routes = db_instance.get_all_routes()
    r1_pts = routes[0]["waypoints"] if routes else []

    base_lat = 17.337420
    base_lng = 78.583150

    for day_offset in range(7):
        target_date = now - timedelta(days=day_offset)
        print(f"Seeding history for {target_date.strftime('%Y-%m-%d')} (Day -{day_offset})...")

        for step in range(12):
            t_point = target_date.replace(hour=8, minute=0, second=0) + timedelta(minutes=step * 4)
            offset_factor = step * 0.003
            lat = base_lat + offset_factor
            lng = base_lng + (offset_factor * 0.8)

            db_instance.add_location_history(
                bus_id="BUS-01",
                lat=lat,
                lng=lng,
                speed=36.0 + (step % 5) * 3,
                heading=90.0,
                timestamp=t_point,
                satellites=9,
                accuracy=1.2,
                altitude=540.0,
                gps_status="valid",
                device_id="AIV-DEV-001"
            )

    # Save current live location for BUS-01 (Online & Active)
    db_instance.save_current_location(
        bus_id="BUS-01",
        lat=base_lat + 0.036,
        lng=base_lng + 0.028,
        speed=42.0,
        heading=115.0,
        timestamp=now,
        satellites=10,
        accuracy=1.1,
        altitude=545.0,
        gps_status="valid",
        device_id="AIV-DEV-001"
    )
    db_instance.touch_device_seen("AIV-DEV-001", gps_status="valid", assigned_bus_id="BUS-01")

    # Save current live location for BUS-02 (Online & Moving)
    db_instance.save_current_location(
        bus_id="BUS-02",
        lat=17.440100,
        lng=78.490100,
        speed=38.0,
        heading=180.0,
        timestamp=now - timedelta(seconds=12),
        satellites=8,
        accuracy=1.5,
        altitude=520.0,
        gps_status="valid",
        device_id="AIV-DEV-002"
    )
    db_instance.touch_device_seen("AIV-DEV-002", gps_status="valid", assigned_bus_id="BUS-02")

    print(f"Successfully seeded fleet! Total Buses: {len(db_instance.get_all_buses())}, Total Devices: {len(db_instance.get_all_devices(compute_status=False))}")

if __name__ == "__main__":
    seed()
