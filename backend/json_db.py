import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from backend.route_engine import compute_trip_summary, haversine_distance_m, haversine_distance_km

# Thread lock for concurrent file safety
_LOCK = threading.RLock()

# In-memory active trajectory tracking per bus for auto-route creation
_ACTIVE_TRIPS = {}


# Initial Seed Route Templates & Stops
DEFAULT_ROUTES = [
    {
        "id": "AUTOROUTE-01",
        "bus_id": "BUS-01",
        "route_name": "Route 01: Koti Central -> Campus Terminal",
        "route_code": "R01",
        "origin": "Koti Central Bus Station",
        "destination": "Main Campus Terminal",
        "description": "Primary college arterial corridor learned from GPS movement.",
        "first_recorded": "08:00 AM",
        "last_recorded": "09:15 AM",
        "frequency": 14,
        "operating_times": ["08:00 AM - 09:15 AM", "04:30 PM - 05:45 PM"],
        "distance_km": 11.2,
        "duration_minutes": 75,
        "waypoints": [
            [17.385044, 78.486671],
            [17.391200, 78.474500],
            [17.402100, 78.461000],
            [17.425500, 78.451200],
            [17.442000, 78.448000],
            [17.458000, 78.441000]
        ],
        "assigned_stops": ["STOP-01", "STOP-02", "STOP-03", "STOP-04", "STOP-05"]
    },
    {
        "id": "AUTOROUTE-02",
        "bus_id": "BUS002",
        "route_name": "Route 02: Secunderabad -> Begumpet Tech Park",
        "route_code": "R02",
        "origin": "Secunderabad Station",
        "destination": "Begumpet Tech Park",
        "description": "Northern transit feeder route.",
        "first_recorded": "07:30 AM",
        "last_recorded": "08:35 AM",
        "frequency": 11,
        "operating_times": ["07:30 AM - 08:35 AM", "01:45 PM - 02:50 PM"],
        "distance_km": 8.4,
        "duration_minutes": 65,
        "waypoints": [
            [17.439930, 78.498274],
            [17.443500, 78.487000],
            [17.441100, 78.471200],
            [17.438000, 78.459000],
            [17.435000, 78.446000]
        ],
        "assigned_stops": ["STOP-06", "STOP-07", "STOP-08"]
    },
    {
        "id": "AUTOROUTE-03",
        "bus_id": "BUS003",
        "route_name": "Route 03: LB Nagar -> Malakpet Terminal",
        "route_code": "R03",
        "origin": "LB Nagar Metro Station",
        "destination": "Malakpet Terminal",
        "description": "Eastern feeder corridor.",
        "first_recorded": "08:15 AM",
        "last_recorded": "09:05 AM",
        "frequency": 9,
        "operating_times": ["08:15 AM - 09:05 AM", "05:10 PM - 06:00 PM"],
        "distance_km": 9.1,
        "duration_minutes": 50,
        "waypoints": [
            [17.345719, 78.552230],
            [17.368800, 78.524500],
            [17.375500, 78.498000],
            [17.382000, 78.482000]
        ],
        "assigned_stops": ["STOP-09", "STOP-10"]
    }
]

DEFAULT_STOPS = [
    {
        "id": "STOP-01",
        "name": "Koti Central Bus Stop",
        "code": "KT01",
        "latitude": 17.385044,
        "longitude": 78.486671,
        "radius_m": 80,
        "route_id": "AUTOROUTE-01",
        "sequence": 1
    },
    {
        "id": "STOP-02",
        "name": "Abids GPO Circle",
        "code": "AB02",
        "latitude": 17.391200,
        "longitude": 78.474500,
        "radius_m": 75,
        "route_id": "AUTOROUTE-01",
        "sequence": 2
    },
    {
        "id": "STOP-03",
        "name": "Lakdi-ka-pul Junction",
        "code": "LK03",
        "latitude": 17.402100,
        "longitude": 78.461000,
        "radius_m": 75,
        "route_id": "AUTOROUTE-01",
        "sequence": 3
    },
    {
        "id": "STOP-04",
        "name": "Punjagutta Circle",
        "code": "PJ04",
        "latitude": 17.425500,
        "longitude": 78.451200,
        "radius_m": 85,
        "route_id": "AUTOROUTE-01",
        "sequence": 4
    },
    {
        "id": "STOP-05",
        "name": "Main Campus Gate 1",
        "code": "CP05",
        "latitude": 17.458000,
        "longitude": 78.441000,
        "radius_m": 100,
        "route_id": "AUTOROUTE-01",
        "sequence": 5
    },
    {
        "id": "STOP-06",
        "name": "Secunderabad Station Stop",
        "code": "SC06",
        "latitude": 17.439930,
        "longitude": 78.498274,
        "radius_m": 80,
        "route_id": "AUTOROUTE-02",
        "sequence": 1
    },
    {
        "id": "STOP-07",
        "name": "Paradise Circle Stop",
        "code": "PR07",
        "latitude": 17.443500,
        "longitude": 78.487000,
        "radius_m": 75,
        "route_id": "AUTOROUTE-02",
        "sequence": 2
    },
    {
        "id": "STOP-08",
        "name": "Begumpet Airport Road Stop",
        "code": "BG08",
        "latitude": 17.441100,
        "longitude": 78.471200,
        "radius_m": 85,
        "route_id": "AUTOROUTE-02",
        "sequence": 3
    },
    {
        "id": "STOP-09",
        "name": "LB Nagar Ring Road Stop",
        "code": "LB09",
        "latitude": 17.345719,
        "longitude": 78.552230,
        "radius_m": 90,
        "route_id": "AUTOROUTE-03",
        "sequence": 1
    },
    {
        "id": "STOP-10",
        "name": "Dilsukhnagar Bus Complex",
        "code": "DS10",
        "latitude": 17.368800,
        "longitude": 78.524500,
        "radius_m": 80,
        "route_id": "AUTOROUTE-03",
        "sequence": 2
    }
]


class JsonDB:
    """
    Robust, thread-safe JSON-only database layer supporting multi-bus registration,
    ESP8266 device association, and automatic route detection.
    """

    def __init__(self, data_dir=None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            base_dir = Path(__file__).resolve().parent.parent
            self.data_dir = base_dir / "data"

        self.buses_file = self.data_dir / "buses.json"
        self.locations_file = self.data_dir / "locations.json"
        self.history_file = self.data_dir / "history.json"
        self.settings_file = self.data_dir / "settings.json"
        self.users_file = self.data_dir / "users.json"
        self.routes_file = self.data_dir / "routes.json"
        self.journeys_file = self.data_dir / "journeys.json"
        self.stops_file = self.data_dir / "stops.json"
        self.deviations_file = self.data_dir / "deviations.json"
        self.stop_events_file = self.data_dir / "stop_events.json"
        self.device_health_file = self.data_dir / "device_health.json"
        self.backups_dir = self.data_dir / "backups"
        self._last_retention_check = None

        self.init_storage()

    def init_storage(self):
        """Ensure data directory and required JSON files exist."""
        with _LOCK:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            files_and_defaults = [
                (self.buses_file, []),
                (self.locations_file, {}),
                (self.history_file, []),
                (self.settings_file, {
                    "online_threshold_seconds": 30,
                    "deviation_threshold_meters": 150,
                    "geofence_radius_meters": 75,
                    "auto_refresh_seconds": 5,
                    "server_url": "https://trackbus.pythonanywhere.com",
                    "api_key": "YOUR_API_KEY"
                }),
                (self.users_file, []),
                (self.routes_file, DEFAULT_ROUTES),
                (self.journeys_file, []),
                (self.stops_file, DEFAULT_STOPS),
                (self.deviations_file, []),
                (self.stop_events_file, []),
                (self.device_health_file, {}),
            ]

            for file_path, default_content in files_and_defaults:
                if not file_path.exists() or file_path.stat().st_size == 0:
                    self._write_json_direct(file_path, default_content)

            self.backups_dir.mkdir(parents=True, exist_ok=True)
            self.enforce_seven_day_retention_and_backup(force=False)

    def _read_json(self, file_path, default=None):
        """Read and parse JSON file safely."""
        with _LOCK:
            if not file_path.exists():
                return default if default is not None else []
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return default if default is not None else []

    def _write_json(self, file_path, data):
        """Write data to JSON file atomically."""
        with _LOCK:
            self._write_json_direct(file_path, data)

    def _write_json_direct(self, file_path, data):
        temp_file = file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(file_path)
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # BUSES CRUD & MULTI-DEVICE MAPPING
    # -------------------------------------------------------------------------
    def get_all_buses(self):
        """Return list of all registered buses."""
        return self._read_json(self.buses_file, default=[])

    def get_bus(self, bus_id):
        """Find a bus by bus_id or bus_number."""
        if not bus_id:
            return None
        target = str(bus_id).strip().upper()
        buses = self.get_all_buses()
        for b in buses:
            if (b.get("bus_id", "").upper() == target or
                b.get("bus_number", "").upper() == target or
                b.get("device_id", "").upper() == target):
                return b
        return None

    def get_bus_by_device_id(self, device_id):
        """Find bus mapped to a specific ESP device ID."""
        if not device_id:
            return None
        target_raw = str(device_id).strip()
        target_upper = target_raw.upper()
        target_lower = target_raw.lower()

        buses = self.get_all_buses()
        for b in buses:
            b_dev = str(b.get("device_id", "")).strip().lower()
            b_id = str(b.get("bus_id", "")).strip().upper()
            b_num = str(b.get("bus_number", "")).strip().upper()
            if b_dev == target_lower or b_id == target_upper or b_num == target_upper:
                return b
        return None

    def create_bus(self, bus_data):
        """Create and store a new bus with its ESP device ID."""
        with _LOCK:
            buses = self.get_all_buses()
            bus_id = str(bus_data.get("bus_id") or bus_data.get("bus_number") or "").strip().upper()
            if not bus_id:
                raise ValueError("bus_id is required")

            # Check if bus already exists
            for b in buses:
                if b.get("bus_id", "").upper() == bus_id:
                    return b

            bus_name = bus_data.get("bus_name") or f"College Bus {bus_id}"
            device_id = str(bus_data.get("device_id") or bus_id).strip().upper()
            bus_number = bus_data.get("bus_number") or bus_id

            now_iso = datetime.now(timezone.utc).isoformat()
            new_bus = {
                "id": len(buses) + 1,
                "bus_id": bus_id,
                "bus_name": bus_name,
                "bus_number": bus_number,
                "device_id": device_id,
                "route_name": bus_data.get("route_name") or f"Auto-Route {bus_id}",
                "route_id": bus_data.get("route_id") or "AUTOROUTE-01",
                "driver_name": bus_data.get("driver_name") or "Unassigned",
                "driver_phone": bus_data.get("driver_phone") or "N/A",
                "capacity": int(bus_data.get("capacity") or 50),
                "is_active": bool(bus_data.get("is_active", True)),
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            buses.append(new_bus)
            self._write_json(self.buses_file, buses)
            return new_bus

    def update_bus(self, bus_id, update_data):
        """Update existing bus fields."""
        with _LOCK:
            buses = self.get_all_buses()
            target = str(bus_id).strip().upper()
            for i, b in enumerate(buses):
                if b.get("bus_id", "").upper() == target:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    for k in ["bus_name", "bus_number", "device_id", "route_name", "route_id", "driver_name", "driver_phone", "capacity", "is_active"]:
                        if k in update_data:
                            b[k] = update_data[k]
                    b["updated_at"] = now_iso
                    buses[i] = b
                    self._write_json(self.buses_file, buses)
                    return b
            return None

    def delete_bus(self, bus_id):
        """Delete a bus and its location records."""
        with _LOCK:
            target = str(bus_id).strip().upper()
            buses = self.get_all_buses()
            filtered = [b for b in buses if b.get("bus_id", "").upper() != target]
            if len(filtered) == len(buses):
                return False

            self._write_json(self.buses_file, filtered)

            # Clean current location
            locations = self._read_json(self.locations_file, default={})
            if target in locations:
                del locations[target]
                self._write_json(self.locations_file, locations)

            # Clean history
            history = self._read_json(self.history_file, default=[])
            history_filtered = [h for h in history if h.get("bus_id", "").upper() != target]
            self._write_json(self.history_file, history_filtered)

            return True

    # -------------------------------------------------------------------------
    # CURRENT LOCATIONS
    # -------------------------------------------------------------------------
    def get_all_locations(self):
        """Return dict of all current bus locations."""
        return self._read_json(self.locations_file, default={})

    def get_location(self, bus_id):
        """Get latest location for a specific bus."""
        if not bus_id:
            return None
        target = str(bus_id).strip().upper()
        locations = self.get_all_locations()
        return locations.get(target)

    def save_current_location(self, bus_id, lat, lng, speed=0.0, heading=0.0, timestamp=None,
                              satellites=None, accuracy=None, altitude=None, gps_status="valid",
                              device_id=None, status=None):
        """Update or insert current location for a bus."""
        with _LOCK:
            target = str(bus_id).strip().upper()
            locations = self.get_all_locations()

            now = timestamp or datetime.now(timezone.utc)
            now_iso = now.isoformat()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%I:%M:%S %p")

            calc_status = status or ("MOVING" if float(speed) > 3.0 else "STOPPED")

            loc_entry = {
                "id": len(locations) + 1,
                "bus_id": target,
                "bus_no": target,
                "device_id": str(device_id or target).lower(),
                "latitude": round(float(lat), 6),
                "longitude": round(float(lng), 6),
                "speed": round(float(speed), 1),
                "heading": round(float(heading), 1),
                "satellites": int(satellites) if satellites is not None else 8,
                "accuracy": round(float(accuracy), 1) if accuracy is not None else 1.5,
                "altitude": round(float(altitude), 1) if altitude is not None else 500.0,
                "gps_status": gps_status or "valid",
                "status": calc_status,
                "timestamp": now_iso,
                "updated_at": now_iso,
                "date": date_str,
                "time": time_str,
            }

            locations[target] = loc_entry
            self._write_json(self.locations_file, locations)
            return loc_entry

    # -------------------------------------------------------------------------
    # LOCATION HISTORY
    # -------------------------------------------------------------------------
    def add_location_history(self, bus_id, lat, lng, speed=0.0, heading=0.0, timestamp=None,
                             satellites=None, accuracy=None, altitude=None, gps_status="valid",
                             device_id=None, force=False):
        """
        Append a location history ping with smart deduplication.
        If stationary and distance moved < 5m within last 45s, skip duplicate.
        """
        with _LOCK:
            target = str(bus_id).strip().upper()
            history = self._read_json(self.history_file, default=[])

            now = timestamp or datetime.now(timezone.utc)
            now_iso = now.isoformat()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%I:%M:%S %p")

            # Deduplication against last history ping for this bus
            if not force and history:
                for last_rec in reversed(history):
                    if last_rec.get("bus_id", "").upper() == target:
                        prev_lat = float(last_rec.get("latitude", 0))
                        prev_lng = float(last_rec.get("longitude", 0))
                        prev_speed = float(last_rec.get("speed", 0))
                        dist_moved = haversine_distance_m(prev_lat, prev_lng, float(lat), float(lng))

                        try:
                            prev_dt = datetime.fromisoformat(last_rec["timestamp"])
                            time_diff = (now - prev_dt).total_seconds()
                        except Exception:
                            time_diff = 60

                        if dist_moved < 5.0 and float(speed) < 3.0 and prev_speed < 3.0 and time_diff < 45.0:
                            return last_rec
                        break

            entry = {
                "id": len(history) + 1,
                "bus_id": target,
                "bus_no": target,
                "device_id": str(device_id or target).lower(),
                "latitude": round(float(lat), 6),
                "longitude": round(float(lng), 6),
                "speed": round(float(speed), 1),
                "heading": round(float(heading), 1),
                "satellites": int(satellites) if satellites is not None else 8,
                "accuracy": round(float(accuracy), 1) if accuracy is not None else 1.5,
                "altitude": round(float(altitude), 1) if altitude is not None else 500.0,
                "gps_status": gps_status or "valid",
                "timestamp": now_iso,
                "date": date_str,
                "time": time_str,
            }

            history.append(entry)
            self._write_json(self.history_file, history)
            return entry

    def get_bus_history(self, bus_id, date_filter=None, limit=500):
        """Query location history for a bus, optionally filtered by date."""
        target = str(bus_id).strip().upper()
        history = self._read_json(self.history_file, default=[])

        bus_records = [h for h in history if h.get("bus_id", "").upper() == target]

        all_dates = []
        for r in bus_records:
            d = r.get("date")
            if d and d not in all_dates:
                all_dates.append(d)

        now = datetime.now(timezone.utc)
        today_str = now.strftime("%d-%m-%Y")
        yesterday_str = (now - timedelta(days=1)).strftime("%d-%m-%Y")

        filtered_records = bus_records

        if date_filter and date_filter.lower() != "all":
            df = date_filter.strip().lower()
            if df == "today":
                filtered_records = [r for r in bus_records if r.get("date") == today_str]
            elif df == "yesterday":
                filtered_records = [r for r in bus_records if r.get("date") == yesterday_str]
            elif df in ["week", "7days"]:
                cutoff = now - timedelta(days=7)
                filtered_records = [
                    r for r in bus_records
                    if datetime.fromisoformat(r["timestamp"]) >= cutoff
                ]
            elif df in ["month", "30days"]:
                cutoff = now - timedelta(days=30)
                filtered_records = [
                    r for r in bus_records
                    if datetime.fromisoformat(r["timestamp"]) >= cutoff
                ]
            else:
                formatted_filter = date_filter.strip()
                if len(formatted_filter) == 10 and formatted_filter[4] == "-" and formatted_filter[7] == "-":
                    parts = formatted_filter.split("-")
                    formatted_filter = f"{parts[2]}-{parts[1]}-{parts[0]}"

                filtered_records = [
                    r for r in bus_records
                    if r.get("date") == formatted_filter
                ]

        trip_summary = compute_trip_summary(filtered_records)

        if limit and limit > 0:
            filtered_records = filtered_records[-limit:]

        return {
            "records": filtered_records,
            "available_dates": all_dates,
            "total_count": len(filtered_records),
            "trip_summary": trip_summary
        }

    # -------------------------------------------------------------------------
    # AUTOMATIC ROUTE DETECTION & CREATION ENGINE
    # -------------------------------------------------------------------------
    def process_incoming_gps_point_for_auto_routes(self, bus_id, lat, lng, speed, now_dt):
        """
        Continuously processes incoming coordinates, tracks active moving segments,
        and automatically detects & learns recurring route corridors and operating times!
        """
        global _ACTIVE_TRIPS
        bus_key = str(bus_id).strip().upper()

        if bus_key not in _ACTIVE_TRIPS:
            _ACTIVE_TRIPS[bus_key] = {
                "start_time": now_dt,
                "last_move_time": now_dt,
                "start_point": [lat, lng],
                "waypoints": [[lat, lng]],
                "accumulated_dist_km": 0.0,
                "in_motion": (speed > 3.0),
                "stationary_cycles": 0
            }
            return

        trip = _ACTIVE_TRIPS[bus_key]
        last_pt = trip["waypoints"][-1]
        step_dist_m = haversine_distance_m(last_pt[0], last_pt[1], lat, lng)
        step_dist_km = step_dist_m / 1000.0

        if speed > 3.0 or step_dist_m > 15.0:
            trip["waypoints"].append([lat, lng])
            trip["accumulated_dist_km"] += step_dist_km
            trip["last_move_time"] = now_dt
            trip["in_motion"] = True
            trip["stationary_cycles"] = 0
        else:
            trip["stationary_cycles"] += 1

        # Check if journey should be finalized (covered > 400m and stopped for 15+ cycles)
        if trip["accumulated_dist_km"] > 0.4 and trip["stationary_cycles"] >= 15:
            self._finalize_and_cluster_journey(bus_key, trip)
            # Reset active trip
            _ACTIVE_TRIPS[bus_key] = {
                "start_time": now_dt,
                "last_move_time": now_dt,
                "start_point": [lat, lng],
                "waypoints": [[lat, lng]],
                "accumulated_dist_km": 0.0,
                "in_motion": False,
                "stationary_cycles": 0
            }

    def _finalize_and_cluster_journey(self, bus_id, trip):
        """Record completed journey and cluster with existing routes in routes.json."""
        with _LOCK:
            journeys = self._read_json(self.journeys_file, default=[])
            routes = self.get_all_routes()

            start_t = trip["start_time"]
            end_t = trip["last_move_time"]
            duration_mins = max(1, int((end_t - start_t).total_seconds() / 60.0))
            dist_km = round(trip["accumulated_dist_km"], 2)

            start_pt = trip["start_point"]
            end_pt = trip["waypoints"][-1]

            start_str = start_t.strftime("%I:%M %p")
            end_str = end_t.strftime("%I:%M %p")
            time_window = f"{start_str} - {end_str}"
            date_str = start_t.strftime("%d-%m-%Y")

            # Check if this journey matches an existing route for this bus (within 500m start & end)
            matched_route = None
            for r in routes:
                r_pts = r.get("waypoints", [])
                if len(r_pts) >= 2:
                    r_start = r_pts[0]
                    r_end = r_pts[-1]
                    d_start = haversine_distance_m(start_pt[0], start_pt[1], r_start[0], r_start[1])
                    d_end = haversine_distance_m(end_pt[0], end_pt[1], r_end[0], r_end[1])
                    if d_start <= 500 and d_end <= 500:
                        matched_route = r
                        break

            if matched_route:
                matched_route["frequency"] = matched_route.get("frequency", 1) + 1
                matched_route["last_recorded"] = end_str
                ops = matched_route.get("operating_times", [])
                if time_window not in ops:
                    ops.append(time_window)
                matched_route["operating_times"] = ops[-5:]  # Keep recent windows
                route_id = matched_route["id"]
                route_name = matched_route["route_name"]
                self.update_route(route_id, matched_route)
            else:
                # Create a new automatically learned route
                route_id = f"AUTOROUTE-{len(routes)+1:02d}"
                origin_name = f"Terminal at {start_pt[0]:.3f}, {start_pt[1]:.3f}"
                dest_name = f"Destination at {end_pt[0]:.3f}, {end_pt[1]:.3f}"
                route_name = f"Route {len(routes)+1}: {origin_name} to {dest_name}"

                new_route = {
                    "id": route_id,
                    "bus_id": bus_id,
                    "route_name": route_name,
                    "route_code": f"R{len(routes)+1:02d}",
                    "origin": origin_name,
                    "destination": dest_name,
                    "description": "Learned automatically from live GPS movement trajectory.",
                    "first_recorded": start_str,
                    "last_recorded": end_str,
                    "frequency": 1,
                    "operating_times": [time_window],
                    "distance_km": dist_km,
                    "duration_minutes": duration_mins,
                    "waypoints": trip["waypoints"][::2],  # Downsample for compact polyline
                    "assigned_stops": []
                }
                routes.append(new_route)
                self._write_json(self.routes_file, routes)

            # Store in journeys.json
            journey_entry = {
                "id": f"JRN-{len(journeys)+1:05d}",
                "bus_id": bus_id,
                "route_id": route_id,
                "route_name": route_name,
                "date": date_str,
                "start_time": start_str,
                "end_time": end_str,
                "duration_minutes": duration_mins,
                "distance_km": dist_km,
                "start_point": start_pt,
                "end_point": end_pt,
                "waypoints": trip["waypoints"][::2]
            }
            journeys.append(journey_entry)
            self._write_json(self.journeys_file, journeys)

    def get_routes_by_bus(self, bus_id):
        """Get all routes learned or assigned for a specific bus."""
        target = str(bus_id).strip().upper()
        routes = self.get_all_routes()
        return [r for r in routes if str(r.get("bus_id", "")).upper() == target or target in r.get("route_name", "").upper()]

    def get_journeys(self, bus_id=None, date_filter=None, limit=50):
        """Get list of historical journeys."""
        journeys = self._read_json(self.journeys_file, default=[])
        if bus_id:
            target = str(bus_id).strip().upper()
            journeys = [j for j in journeys if j.get("bus_id", "").upper() == target]
        if date_filter and date_filter.lower() != "all":
            journeys = [j for j in journeys if j.get("date") == date_filter]
        if limit and limit > 0:
            journeys = journeys[-limit:]
        return journeys

    # -------------------------------------------------------------------------
    # ROUTES CRUD
    # -------------------------------------------------------------------------
    def get_all_routes(self):
        """Return list of predefined routes."""
        return self._read_json(self.routes_file, default=DEFAULT_ROUTES)

    def get_route(self, route_id):
        """Find route by ID or code."""
        if not route_id:
            return None
        target = str(route_id).strip().upper()
        for r in self.get_all_routes():
            if r.get("id", "").upper() == target or r.get("route_code", "").upper() == target:
                return r
        return None

    def create_route(self, route_data):
        """Add a new planned route."""
        with _LOCK:
            routes = self.get_all_routes()
            route_id = str(route_data.get("id") or f"ROUTE-{len(routes)+1:02d}").upper()

            for r in routes:
                if r.get("id", "").upper() == route_id:
                    return r

            new_route = {
                "id": route_id,
                "bus_id": route_data.get("bus_id", ""),
                "route_name": route_data.get("route_name", f"Route {route_id}"),
                "route_code": route_data.get("route_code", route_id),
                "origin": route_data.get("origin", "Start Terminal"),
                "destination": route_data.get("destination", "End Terminal"),
                "description": route_data.get("description", "Learned transit route."),
                "first_recorded": route_data.get("first_recorded", "08:00 AM"),
                "last_recorded": route_data.get("last_recorded", "09:00 AM"),
                "frequency": int(route_data.get("frequency", 1)),
                "operating_times": route_data.get("operating_times", ["08:00 AM - 09:00 AM"]),
                "distance_km": float(route_data.get("distance_km", 10.0)),
                "duration_minutes": int(route_data.get("duration_minutes", 60)),
                "waypoints": route_data.get("waypoints", []),
                "assigned_stops": route_data.get("assigned_stops", [])
            }
            routes.append(new_route)
            self._write_json(self.routes_file, routes)
            return new_route

    def update_route(self, route_id, route_data):
        """Update an existing route."""
        with _LOCK:
            routes = self.get_all_routes()
            target = str(route_id).strip().upper()
            for i, r in enumerate(routes):
                if r.get("id", "").upper() == target:
                    for k in ["route_name", "route_code", "origin", "destination", "description", "waypoints", "assigned_stops", "frequency", "last_recorded", "operating_times"]:
                        if k in route_data:
                            r[k] = route_data[k]
                    routes[i] = r
                    self._write_json(self.routes_file, routes)
                    return r
            return None

    def delete_route(self, route_id):
        """Delete a route."""
        with _LOCK:
            routes = self.get_all_routes()
            target = str(route_id).strip().upper()
            filtered = [r for r in routes if r.get("id", "").upper() != target]
            if len(filtered) == len(routes):
                return False
            self._write_json(self.routes_file, filtered)
            return True

    # -------------------------------------------------------------------------
    # BUS STOPS CRUD
    # -------------------------------------------------------------------------
    def get_all_stops(self, route_id=None):
        """Return list of all registered bus stops, optionally filtered by route."""
        stops = self._read_json(self.stops_file, default=DEFAULT_STOPS)
        if route_id and route_id.lower() != "all":
            target = str(route_id).strip().upper()
            stops = [s for s in stops if str(s.get("route_id", "")).upper() == target]
        return stops

    def get_stop(self, stop_id):
        """Find a bus stop by ID."""
        if not stop_id:
            return None
        target = str(stop_id).strip().upper()
        for s in self.get_all_stops():
            if s.get("id", "").upper() == target or s.get("code", "").upper() == target:
                return s
        return None

    def create_stop(self, stop_data):
        """Add a new bus stop with geofence radius."""
        with _LOCK:
            stops = self.get_all_stops()
            stop_id = str(stop_data.get("id") or f"STOP-{len(stops)+1:02d}").upper()

            for s in stops:
                if s.get("id", "").upper() == stop_id:
                    return s

            new_stop = {
                "id": stop_id,
                "name": stop_data.get("name", f"Stop {stop_id}"),
                "code": stop_data.get("code", stop_id),
                "latitude": float(stop_data.get("latitude", 0.0)),
                "longitude": float(stop_data.get("longitude", 0.0)),
                "radius_m": int(stop_data.get("radius_m", 75)),
                "route_id": stop_data.get("route_id", "AUTOROUTE-01"),
                "sequence": int(stop_data.get("sequence", len(stops) + 1))
            }
            stops.append(new_stop)
            self._write_json(self.stops_file, stops)
            return new_stop

    def update_stop(self, stop_id, stop_data):
        """Update an existing bus stop."""
        with _LOCK:
            stops = self.get_all_stops()
            target = str(stop_id).strip().upper()
            for i, s in enumerate(stops):
                if s.get("id", "").upper() == target:
                    for k in ["name", "code", "latitude", "longitude", "radius_m", "route_id", "sequence"]:
                        if k in stop_data:
                            s[k] = stop_data[k]
                    stops[i] = s
                    self._write_json(self.stops_file, stops)
                    return s
            return None

    def delete_stop(self, stop_id):
        """Delete a bus stop."""
        with _LOCK:
            stops = self.get_all_stops()
            target = str(stop_id).strip().upper()
            filtered = [s for s in stops if s.get("id", "").upper() != target]
            if len(filtered) == len(stops):
                return False
            self._write_json(self.stops_file, filtered)
            return True

    # -------------------------------------------------------------------------
    # GEOFENCING & STOP ARRIVAL/DEPARTURE EVENTS
    # -------------------------------------------------------------------------
    def record_stop_event(self, event_data):
        """Log a stop arrival or departure event."""
        with _LOCK:
            events = self._read_json(self.stop_events_file, default=[])
            event_id = f"EVT-{len(events)+1:05d}"
            now_iso = datetime.now(timezone.utc).isoformat()

            entry = {
                "id": event_id,
                "bus_id": event_data.get("bus_id"),
                "stop_id": event_data.get("stop_id"),
                "stop_name": event_data.get("stop_name"),
                "event_type": event_data.get("event_type", "ARRIVED"),
                "timestamp": event_data.get("timestamp", now_iso),
                "date": datetime.now(timezone.utc).strftime("%d-%m-%Y"),
                "time": datetime.now(timezone.utc).strftime("%I:%M:%S %p"),
                "dwell_seconds": event_data.get("dwell_seconds", 0)
            }
            events.append(entry)
            self._write_json(self.stop_events_file, events)
            return entry

    def get_stop_events(self, bus_id=None, date_filter=None, limit=100):
        """Retrieve recorded stop arrival and departure events."""
        events = self._read_json(self.stop_events_file, default=[])
        if bus_id:
            target = str(bus_id).strip().upper()
            events = [e for e in events if e.get("bus_id", "").upper() == target]
        if date_filter:
            events = [e for e in events if e.get("date") == date_filter]
        if limit and limit > 0:
            events = events[-limit:]
        return events

    # -------------------------------------------------------------------------
    # ROUTE DEVIATION TRACKING
    # -------------------------------------------------------------------------
    def record_deviation(self, dev_data):
        """Record or update a route deviation event."""
        with _LOCK:
            deviations = self._read_json(self.deviations_file, default=[])
            now_iso = datetime.now(timezone.utc).isoformat()
            dev_id = f"DEV-{len(deviations)+1:04d}"

            entry = {
                "id": dev_id,
                "bus_id": dev_data.get("bus_id"),
                "route_name": dev_data.get("route_name", "Assigned Route"),
                "start_time": dev_data.get("start_time", now_iso),
                "end_time": dev_data.get("end_time"),
                "max_deviation_m": round(float(dev_data.get("max_deviation_m", 0)), 1),
                "start_latitude": dev_data.get("latitude"),
                "start_longitude": dev_data.get("longitude"),
                "status": dev_data.get("status", "ACTIVE"),
                "date": datetime.now(timezone.utc).strftime("%d-%m-%Y"),
            }
            deviations.append(entry)
            self._write_json(self.deviations_file, deviations)
            return entry

    def update_deviation(self, dev_id, update_data):
        """Update deviation (e.g., mark as RESOLVED)."""
        with _LOCK:
            deviations = self._read_json(self.deviations_file, default=[])
            for i, d in enumerate(deviations):
                if d.get("id") == dev_id:
                    for k, v in update_data.items():
                        d[k] = v
                    deviations[i] = d
                    self._write_json(self.deviations_file, deviations)
                    return d
            return None

    def get_deviations(self, bus_id=None, status=None, date_filter=None, limit=100):
        """Get deviation records."""
        deviations = self._read_json(self.deviations_file, default=[])
        if bus_id:
            target = str(bus_id).strip().upper()
            deviations = [d for d in deviations if d.get("bus_id", "").upper() == target]
        if status:
            deviations = [d for d in deviations if d.get("status") == status]
        if date_filter:
            deviations = [d for d in deviations if d.get("date") == date_filter]
        if limit and limit > 0:
            deviations = deviations[-limit:]
        return deviations

    # -------------------------------------------------------------------------
    # DEVICE HEALTH MONITORING
    # -------------------------------------------------------------------------
    def update_device_health(self, device_id, health_data):
        """Update diagnostic health status of an ESP8266 or tracker device."""
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.device_health_file, default={})
            now_iso = datetime.now(timezone.utc).isoformat()

            existing = devices.get(target, {
                "device_id": target,
                "first_seen": now_iso,
                "total_packets": 0,
                "invalid_packets": 0,
                "http_errors": 0,
            })

            existing["last_seen"] = now_iso
            existing["total_packets"] = existing.get("total_packets", 0) + 1
            if health_data.get("is_invalid"):
                existing["invalid_packets"] = existing.get("invalid_packets", 0) + 1
            if health_data.get("http_error"):
                existing["http_errors"] = existing.get("http_errors", 0) + 1

            for field in ["bus_id", "satellites", "accuracy", "altitude", "gps_status", "wifi_rssi", "firmware_version", "ip_address"]:
                if field in health_data and health_data[field] is not None:
                    existing[field] = health_data[field]

            devices[target] = existing
            self._write_json(self.device_health_file, devices)
            return existing

    def get_device_health(self, device_id=None):
        """Get device health dictionary or single device entry."""
        devices = self._read_json(self.device_health_file, default={})
        if device_id:
            target = str(device_id).strip().upper()
            return devices.get(target) or devices.get(target.lower())
        return devices

    # -------------------------------------------------------------------------
    # SETTINGS
    # -------------------------------------------------------------------------
    def get_settings(self):
        """Get current system configuration settings."""
        defaults = {
            "online_threshold_seconds": 30,
            "deviation_threshold_meters": 150,
            "geofence_radius_meters": 75,
            "auto_refresh_seconds": 5,
            "server_url": "https://trackbus.pythonanywhere.com",
            "api_key": "YOUR_API_KEY"
        }
        stored = self._read_json(self.settings_file, default=defaults)
        defaults.update(stored)
        return defaults

    def update_settings(self, update_data):
        """Update system configuration settings."""
        with _LOCK:
            curr = self.get_settings()
            for k, v in update_data.items():
                if k in curr:
                    curr[k] = v
            self._write_json(self.settings_file, curr)
            return curr

    # -------------------------------------------------------------------------
    # 7-DAY ROLLING RETENTION & AUTOMATED BACKUP ENGINE
    # -------------------------------------------------------------------------
    def enforce_seven_day_retention_and_backup(self, force=False):
        """
        Enforce strict 7-day rolling data retention policy:
        1. Automatically deletes historical GPS coordinates older than 7 days from active storage.
        2. Automatically backs up required GPS and route data into data/backups/.
        3. Automatically deletes backups older than 7 days from backup storage.
        4. Runs non-blocking without interrupting live GPS tracking.
        """
        now = datetime.now(timezone.utc)
        if not force and self._last_retention_check:
            elapsed = (now - self._last_retention_check).total_seconds()
            if elapsed < 1800:  # Run at most once every 30 minutes unless forced
                return {"status": "skipped", "message": "Retention checked recently", "elapsed_seconds": elapsed}

        with _LOCK:
            cutoff = now - timedelta(days=7)
            self.backups_dir.mkdir(parents=True, exist_ok=True)

            def is_recent(item):
                ts = item.get("timestamp") or item.get("updated_at") or item.get("created_at") or item.get("start_time")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt >= cutoff
                    except Exception:
                        pass
                date_str = item.get("date")
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, "%d-%m-%Y").replace(tzinfo=timezone.utc)
                        return dt >= cutoff
                    except Exception:
                        pass
                return True

            # 1. Prune active history
            history = self._read_json(self.history_file, default=[])
            initial_hist_count = len(history)
            pruned_history = [h for h in history if is_recent(h)]
            pruned_hist_count = initial_hist_count - len(pruned_history)
            if pruned_hist_count > 0 or not self.history_file.exists():
                self._write_json(self.history_file, pruned_history)

            # 2. Prune active journeys
            journeys = self._read_json(self.journeys_file, default=[])
            initial_journey_count = len(journeys)
            pruned_journeys = [j for j in journeys if is_recent(j)]
            if len(pruned_journeys) != initial_journey_count or not self.journeys_file.exists():
                self._write_json(self.journeys_file, pruned_journeys)

            # 3. Prune deviations & stop events
            devs = self._read_json(self.deviations_file, default=[])
            pruned_devs = [d for d in devs if is_recent(d)]
            if len(pruned_devs) != len(devs):
                self._write_json(self.deviations_file, pruned_devs)

            events = self._read_json(self.stop_events_file, default=[])
            pruned_events = [e for e in events if is_recent(e)]
            if len(pruned_events) != len(events):
                self._write_json(self.stop_events_file, pruned_events)

            # 4. Create daily automated backup snapshot within retention policy
            today_str = now.strftime("%Y-%m-%d")
            backup_filename = f"backup_gps_{today_str}.json"
            backup_filepath = self.backups_dir / backup_filename
            backup_data = {
                "backup_date": now.isoformat(),
                "retention_policy": "7_days_rolling",
                "cutoff_timestamp": cutoff.isoformat(),
                "routes": self.get_all_routes(),
                "buses": self.get_all_buses(),
                "history_points": len(pruned_history),
                "journeys_count": len(pruned_journeys),
                "history": pruned_history,
                "journeys": pruned_journeys
            }
            self._write_json(backup_filepath, backup_data)

            # 5. Automatically delete backup snapshots older than 7 days
            deleted_backups = []
            for bf in self.backups_dir.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(bf.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        bf.unlink()
                        deleted_backups.append(bf.name)
                except Exception:
                    pass

            self._last_retention_check = now

            return {
                "status": "success",
                "retention_days": 7,
                "cutoff_timestamp": cutoff.isoformat(),
                "pruned_history_records": pruned_hist_count,
                "active_history_records": len(pruned_history),
                "active_journeys": len(pruned_journeys),
                "latest_backup_file": backup_filename,
                "deleted_old_backups": deleted_backups,
                "timestamp": now.isoformat()
            }

    # -------------------------------------------------------------------------
    # UTILITIES / CLEANUP
    # -------------------------------------------------------------------------
    def clear_all_data(self):
        """Clear all dynamic data for test teardown or hard reset."""
        global _ACTIVE_TRIPS
        with _LOCK:
            _ACTIVE_TRIPS.clear()
            self._write_json(self.buses_file, [])
            self._write_json(self.locations_file, {})
            self._write_json(self.history_file, [])
            self._write_json(self.deviations_file, [])
            self._write_json(self.journeys_file, [])
            self._write_json(self.stop_events_file, [])
            self._write_json(self.device_health_file, {})
            self._write_json(self.users_file, [])
            # Also purge backup files
            if self.backups_dir.exists():
                for bf in self.backups_dir.glob("*.json"):
                    try:
                        bf.unlink()
                    except Exception:
                        pass
            self._last_retention_check = None


# Singleton instance
db_instance = JsonDB()
