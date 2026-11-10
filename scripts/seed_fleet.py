"""
Seed Fleet Script: Seeds 30 Sphoorthy Campus buses, hardware ESP devices,
multi-trip daily schedules, college geofencing arrivals, and 7-day route history.
"""
import sys
import random
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import datetime, timezone, timedelta
from backend.json_db import db_instance
from backend.models import Bus

DRIVER_NAMES = [
    "Ramesh Kumar", "Suresh Reddy", "Venkat Rao", "Mohammed Ali", "K. Srinivas",
    "P. Rajesh", "B. Naresh", "Syed Farooq", "M. Anji Reddy", "Ch. Venkatesh",
    "G. Prabhakar", "T. Mahesh", "Y. Ramu", "K. Chandraiah", "D. Shankar",
    "V. Satyanarayana", "B. Krishna", "S. Jagadish", "P. Anand", "R. Bhaskar",
    "Md. Khaja", "N. Gopal", "C. Ravinder", "K. Narsimha", "A. Mallesh",
    "T. Ravi Kumar", "L. Balu", "J. Raju", "P. Vijay", "K. Srinivasulu"
]

ROUTES_POOL = [
    ("AUTOROUTE-01", "Route 01: Koti Central -> Campus Terminal"),
    ("AUTOROUTE-02", "Route 02: Secunderabad -> Begumpet Tech Park"),
    ("AUTOROUTE-03", "Route 03: LB Nagar -> Malakpet Terminal")
]

def seed():
    print("Clearing old test data...")
    db_instance.clear_all_data()

    now = datetime.now(timezone.utc)
    college = db_instance.get_college_config()
    college_lat = college["college_latitude"]
    college_lng = college["college_longitude"]

    print("Registering 30 College Fleet Buses with 1-to-1 ESP Devices...")

    for i in range(1, 31):
        bus_id = f"BUS-{i:02d}"
        bus_number = f"TS 09 UB {1000 + i}"
        bus_name = f"Campus Express {i:02d}"
        device_id = f"AIV-DEV-{i:03d}"
        route_id, route_name = ROUTES_POOL[(i - 1) % len(ROUTES_POOL)]
        driver_name = DRIVER_NAMES[i - 1]
        driver_phone = f"+91 98480 {11000 + i}"
        dev_type = "ESP8266" if (i % 2 == 1) else "ESP32"
        mac = f"24:6F:28:1A:BC:{i:02X}"

        # 1. Register Bus
        bus = Bus(
            bus_id=bus_id,
            bus_name=bus_name,
            bus_number=bus_number,
            device_id=device_id,
            route_id=route_id,
            route_name=route_name,
            driver_name=driver_name,
            driver_phone=driver_phone,
            capacity=52,
            campus=college["college_name"],
            is_active=True
        )
        bus.save()

        # 2. Register Universal Hardware Device
        db_instance.register_device({
            "device_id": device_id,
            "device_name": f"{bus_name} Tracker ({device_id})",
            "mac_address": mac,
            "device_type": dev_type,
            "assigned_bus_id": bus_id
        })

        # 3. Seed 7 days of daily trips (2-4 trips per day per bus)
        for day_offset in range(7):
            d_date = now - timedelta(days=day_offset)
            d_str = d_date.strftime("%d-%m-%Y")

            # 2 to 4 trips per day: Trip 1 (Morning Inbound), Trip 2 (Morning Return), Trip 3 (Afternoon Inbound), Trip 4 (Evening Departure)
            trip_count = 3 if (i % 3 == 0) else (4 if i % 2 == 0 else 2)

            trip_templates = [
                ("07:15 AM", "08:25 AM", 12.8, [17.3850, 78.4866], [college_lat, college_lng]),
                ("09:10 AM", "10:15 AM", 12.4, [college_lat, college_lng], [17.3850, 78.4866]),
                ("01:45 PM", "02:55 PM", 13.1, [17.3850, 78.4866], [college_lat, college_lng]),
                ("04:30 PM", "05:40 PM", 12.9, [college_lat, college_lng], [17.3850, 78.4866])
            ]

            trips_list = db_instance._read_json(db_instance.trips_file, default=[])
            for t_idx in range(trip_count):
                st_time, end_time, dist, s_coord, e_coord = trip_templates[t_idx]

                # If it's today and currently running
                is_current_active = (day_offset == 0 and t_idx == (trip_count - 1) and (i % 3 != 0))

                trip_id = f"TRIP-{bus_id}-{d_date.strftime('%Y%m%d')}-{t_idx + 1}"
                trip_entry = {
                    "id": trip_id,
                    "bus_id": bus_id,
                    "device_id": device_id,
                    "route_id": route_id,
                    "trip_number": t_idx + 1,
                    "date": d_str,
                    "start_time": st_time,
                    "start_coordinates": s_coord,
                    "end_time": None if is_current_active else end_time,
                    "end_coordinates": None if is_current_active else e_coord,
                    "distance_km": round(dist * 0.6 if is_current_active else dist, 2),
                    "status": "RUNNING" if is_current_active else "COMPLETED",
                    "arrival_time": None if is_current_active else end_time,
                    "last_lat": s_coord[0] + 0.01 if is_current_active else e_coord[0],
                    "last_lng": s_coord[1] + 0.01 if is_current_active else e_coord[1],
                    "created_at": d_date.isoformat(),
                    "updated_at": d_date.isoformat()
                }
                trips_list.append(trip_entry)
            db_instance._write_json(db_instance.trips_file, trips_list)

        # 4. Set current live locations:
        # Buses 1 to 10: Running / moving
        # Buses 11 to 20: Reached College (Parked at campus geofence)
        # Buses 21 to 28: Connected & Idle
        # Buses 29, 30: Offline
        if i <= 10:
            lat = 17.3500 + (i * 0.005)
            lng = 78.5000 + (i * 0.006)
            db_instance.save_current_location(
                bus_id=bus_id,
                lat=lat,
                lng=lng,
                speed=35.0 + (i % 6) * 3.0,
                heading=85.0,
                timestamp=now - timedelta(seconds=i * 2),
                satellites=9,
                accuracy=1.2,
                device_id=device_id,
                status="MOVING"
            )
            db_instance.touch_device_seen(device_id, gps_status="valid", assigned_bus_id=bus_id)
        elif i <= 20:
            # Inside college geofence (college_lat: 17.3156, college_lng: 78.5833)
            # Offset by tiny distance < 40m
            lat = college_lat + ((i - 10) * 0.0001)
            lng = college_lng + ((i - 10) * 0.0001)
            db_instance.save_current_location(
                bus_id=bus_id,
                lat=lat,
                lng=lng,
                speed=0.0,
                heading=0.0,
                timestamp=now - timedelta(seconds=15),
                satellites=10,
                accuracy=1.0,
                device_id=device_id,
                status="REACHED_COLLEGE"
            )
            db_instance.touch_device_seen(device_id, gps_status="valid", assigned_bus_id=bus_id)
        elif i <= 28:
            lat = 17.3850 + (i * 0.001)
            lng = 78.4866 + (i * 0.001)
            db_instance.save_current_location(
                bus_id=bus_id,
                lat=lat,
                lng=lng,
                speed=0.0,
                heading=0.0,
                timestamp=now - timedelta(seconds=20),
                satellites=7,
                accuracy=1.8,
                device_id=device_id,
                status="STOPPED"
            )
            db_instance.touch_device_seen(device_id, gps_status="valid", assigned_bus_id=bus_id)
        else:
            # Offline
            lat = 17.3850
            lng = 78.4866
            db_instance.save_current_location(
                bus_id=bus_id,
                lat=lat,
                lng=lng,
                speed=0.0,
                heading=0.0,
                timestamp=now - timedelta(hours=3),
                satellites=0,
                accuracy=5.0,
                device_id=device_id,
                status="STOPPED"
            )

    # 5. Seed detailed 7-day location history for BUS-01, BUS-02, BUS-11 (reached college)
    print("Generating representative 7-day location history points...")
    for day_offset in range(7):
        target_date = now - timedelta(days=day_offset)
        for step in range(12):
            t_point = target_date.replace(hour=8, minute=0, second=0) + timedelta(minutes=step * 4)
            offset = step * 0.003
            db_instance.add_location_history(
                bus_id="BUS-01",
                lat=17.3850 + offset,
                lng=78.4866 + (offset * 0.8),
                speed=36.0 + (step % 5) * 3,
                heading=90.0,
                timestamp=t_point,
                satellites=9,
                device_id="AIV-DEV-001"
            )
            db_instance.add_location_history(
                bus_id="BUS-11",
                lat=college_lat + (step * 0.0005),
                lng=college_lng + (step * 0.0005),
                speed=28.0 if step < 8 else 0.0,
                heading=110.0,
                timestamp=t_point,
                satellites=10,
                device_id="AIV-DEV-011"
            )

    # 6. Seed Audit Logs
    print("Seeding initial security audit logs...")
    db_instance.record_audit_log(
        username="admin",
        role="ADMIN",
        action="FLEET_INITIALIZATION",
        target_type="SYSTEM",
        target_id="FLEET_30",
        details="Provisioned 30 college fleet buses with universal ESP tracking",
        ip_address="127.0.0.1"
    )

    # 7. Check 300 MB storage allocation metrics
    storage = db_instance.get_storage_metrics()
    print("\n==========================================")
    print("FLEET SEEDING COMPLETE!")
    print(f"Total Registered Buses: {len(db_instance.get_all_buses())}")
    print(f"Total Hardware Devices: {len(db_instance.get_all_devices(compute_status=False))}")
    print(f"Total Daily Trips:      {len(db_instance.get_all_trips())}")
    print(f"300 MB Storage Allocation:")
    print(f"  Max Storage:    {storage['max_storage_mb']} MB")
    print(f"  Used Storage:   {storage['total_used_mb']} MB ({storage['total_used_bytes']} bytes)")
    print(f"  Available:      {storage['available_mb']} MB")
    print(f"  Usage:          {storage['percent_used']}% (Status: {storage['warning_level']})")
    print("==========================================\n")

if __name__ == "__main__":
    seed()
