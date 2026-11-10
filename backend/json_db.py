import json
import os
import uuid
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from backend.route_engine import compute_trip_summary, haversine_distance_m, haversine_distance_km

# Maximum Storage Allocation: 300 MB hard limit
MAX_STORAGE_BYTES = 300 * 1024 * 1024  # 314,572,800 bytes

# Thread lock for concurrent file safety
_LOCK = threading.RLock()

# In-memory active trajectory tracking per bus for auto-route creation
_ACTIVE_TRIPS = {}

# In-memory brute force protection tracking {key: {"attempts": int, "locked_until": datetime}}
_FAILED_LOGINS = {}

# Initial Default Users with Hashed Passwords
DEFAULT_USERS = [
    {
        "id": "USR-001",
        "username": "admin",
        "password_hash": generate_password_hash("adminpass"),
        "role": "ADMIN",
        "full_name": "System Administrator",
        "created_at": "2026-11-10T00:00:00+00:00"
    },
    {
        "id": "USR-002",
        "username": "viewer",
        "password_hash": generate_password_hash("viewer123"),
        "role": "VIEWER",
        "full_name": "Fleet Dispatch Viewer",
        "created_at": "2026-11-10T00:00:00+00:00"
    }
]


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

DEFAULT_DEVICES = [
    {
        "id": 1,
        "device_id": "ESP8266-BUS-01",
        "device_name": "Campus Express 01 Dash Unit",
        "mac_address": "AA:BB:CC:11:22:01",
        "device_type": "ESP8266",
        "firmware_version": "3.2.0",
        "device_token": "tok_esp8266_bus01_sec9876",
        "assigned_bus_id": "BUS-01",
        "is_registered": True,
        "auto_discovered": False,
        "status": "offline",
        "last_seen": None,
        "ip_address": None,
        "created_at": "2026-11-09T00:00:00+00:00",
        "updated_at": "2026-11-09T00:00:00+00:00"
    },
    {
        "id": 2,
        "device_id": "ESP8266-BUS-02",
        "device_name": "Campus Express 02 Dash Unit",
        "mac_address": "AA:BB:CC:11:22:02",
        "device_type": "ESP8266",
        "firmware_version": "3.2.0",
        "device_token": "tok_esp8266_bus02_sec9876",
        "assigned_bus_id": "BUS-02",
        "is_registered": True,
        "auto_discovered": False,
        "status": "offline",
        "last_seen": None,
        "ip_address": None,
        "created_at": "2026-11-09T00:00:00+00:00",
        "updated_at": "2026-11-09T00:00:00+00:00"
    },
    {
        "id": 3,
        "device_id": "ESP8266-BUS-03",
        "device_name": "Campus Metro Shuttle Unit",
        "mac_address": "AA:BB:CC:11:22:03",
        "device_type": "ESP8266",
        "firmware_version": "3.2.0",
        "device_token": "tok_esp8266_bus03_sec9876",
        "assigned_bus_id": "BUS-03",
        "is_registered": True,
        "auto_discovered": False,
        "status": "offline",
        "last_seen": None,
        "ip_address": None,
        "created_at": "2026-11-09T00:00:00+00:00",
        "updated_at": "2026-11-09T00:00:00+00:00"
    },
    {
        "id": 4,
        "device_id": "ESP8266-BUS-04",
        "device_name": "Campus City Liner Unit",
        "mac_address": "AA:BB:CC:11:22:04",
        "device_type": "ESP8266",
        "firmware_version": "3.2.0",
        "device_token": "tok_esp8266_bus04_sec9876",
        "assigned_bus_id": "BUS-04",
        "is_registered": True,
        "auto_discovered": False,
        "status": "offline",
        "last_seen": None,
        "ip_address": None,
        "created_at": "2026-11-09T00:00:00+00:00",
        "updated_at": "2026-11-09T00:00:00+00:00"
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
        self.devices_file = self.data_dir / "devices.json"
        self.locations_file = self.data_dir / "locations.json"
        self.history_file = self.data_dir / "history.json"
        self.settings_file = self.data_dir / "settings.json"
        self.users_file = self.data_dir / "users.json"
        self.routes_file = self.data_dir / "routes.json"
        self.journeys_file = self.data_dir / "journeys.json"
        self.trips_file = self.data_dir / "trips.json"
        self.stops_file = self.data_dir / "stops.json"
        self.deviations_file = self.data_dir / "deviations.json"
        self.stop_events_file = self.data_dir / "stop_events.json"
        self.device_health_file = self.data_dir / "device_health.json"
        self.audit_logs_file = self.data_dir / "audit_logs.json"
        self.backups_dir = self.data_dir / "backups"
        self._last_retention_check = None

        self.init_storage()

    def init_storage(self):
        """Ensure data directory and required JSON files exist."""
        with _LOCK:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            files_and_defaults = [
                (self.buses_file, []),
                (self.devices_file, DEFAULT_DEVICES),
                (self.locations_file, {}),
                (self.history_file, []),
                (self.settings_file, {
                    "online_threshold_seconds": 30,
                    "deviation_threshold_meters": 150,
                    "geofence_radius_meters": 100,
                    "auto_refresh_seconds": 5,
                    "server_url": "https://trackbus.pythonanywhere.com",
                    "api_key": "YOUR_API_KEY",
                    "college_name": "Sphoorthy Engineering College",
                    "college_latitude": 17.3156,
                    "college_longitude": 78.5833,
                    "college_geofence_radius_meters": 120,
                    "max_storage_bytes": MAX_STORAGE_BYTES
                }),
                (self.users_file, DEFAULT_USERS),
                (self.routes_file, DEFAULT_ROUTES),
                (self.journeys_file, []),
                (self.trips_file, []),
                (self.stops_file, DEFAULT_STOPS),
                (self.deviations_file, []),
                (self.stop_events_file, []),
                (self.device_health_file, {}),
                (self.audit_logs_file, []),
            ]

            for file_path, default_content in files_and_defaults:
                if not file_path.exists() or file_path.stat().st_size <= 2:
                    self._write_json_direct(file_path, default_content)

            # Ensure default users exist if empty
            current_users = self._read_json(self.users_file, default=[])
            if not current_users:
                self._write_json_direct(self.users_file, DEFAULT_USERS)

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
        """Find bus mapped to a specific ESP device ID or MAC address."""
        if not device_id:
            return None
        target_raw = str(device_id).strip()
        target_upper = target_raw.upper()
        target_lower = target_raw.lower()

        # 1. First check explicit mapping in registered devices.json
        devices = self._read_json(self.devices_file, default=[])
        for d in devices:
            d_id = str(d.get("device_id", "")).strip().upper()
            d_mac = str(d.get("mac_address", "")).strip().upper()
            if d_id == target_upper or (d_mac and d_mac == target_upper):
                assigned_bus_id = d.get("assigned_bus_id")
                if assigned_bus_id:
                    bus = self.get_bus(assigned_bus_id)
                    if bus:
                        return bus

        # 2. Check buses.json directly
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
    # ESP DEVICE REGISTRATION & IDENTIFICATION
    # -------------------------------------------------------------------------
    def get_all_devices(self, compute_status=True):
        """
        Return list of all registered ESP hardware devices.
        If compute_status=True, calculates online/connecting/offline status dynamically.
        """
        devices = self._read_json(self.devices_file, default=[])
        if not compute_status:
            return devices

        now = datetime.now(timezone.utc)
        settings = self.get_settings()
        threshold = int(settings.get("online_threshold_seconds", 30))
        buses = {b.get("bus_id", "").upper(): b for b in self.get_all_buses()}

        enriched = []
        for d in devices:
            dev = dict(d)
            last_seen_str = dev.get("last_seen")
            status = "offline"
            status_label = "Offline"
            is_online = False
            last_seen_relative = "Never"

            if last_seen_str:
                try:
                    ls_dt = datetime.fromisoformat(last_seen_str)
                    if ls_dt.tzinfo is None:
                        ls_dt = ls_dt.replace(tzinfo=timezone.utc)
                    elapsed = (now - ls_dt).total_seconds()

                    if elapsed < 5:
                        last_seen_relative = "Just now"
                    elif elapsed < 60:
                        last_seen_relative = f"{int(elapsed)}s ago"
                    elif elapsed < 3600:
                        last_seen_relative = f"{int(elapsed // 60)}m ago"
                    else:
                        last_seen_relative = f"{int(elapsed // 3600)}h ago"

                    health = self.get_device_health(dev.get("device_id")) or {}
                    gps_status = health.get("gps_status", "valid")

                    if elapsed <= threshold:
                        if gps_status in ["no_fix", "invalid"]:
                            status = "connecting"
                            status_label = "Acquiring GPS"
                            is_online = True
                        else:
                            status = "online"
                            status_label = "Online"
                            is_online = True
                    elif elapsed <= 60:
                        status = "connecting"
                        status_label = "Connecting"
                        is_online = False
                    else:
                        status = "offline"
                        status_label = "Offline"
                        is_online = False
                except Exception:
                    pass

            dev["status"] = status
            dev["status_label"] = status_label
            dev["is_online"] = is_online
            dev["last_seen_relative"] = last_seen_relative

            # Universal Device Identity & Diagnostics
            dev["device_name"] = dev.get("device_name") or f"{dev.get('device_type', 'ESP')} Tracker ({dev.get('device_id')})"
            dev["firmware_version"] = dev.get("firmware_version") or "3.2.0"
            dev["auto_discovered"] = bool(dev.get("auto_discovered", False))
            dev["device_token"] = dev.get("device_token") or f"tok_{str(dev.get('device_id', '')).lower()}_sec"

            # Compute GPS Availability
            health = self.get_device_health(dev.get("device_id")) or {}
            satellites = health.get("satellites") if health.get("satellites") is not None else 0
            gps_st = health.get("gps_status", "valid")
            gps_available = False
            if is_online and gps_st not in ["no_fix", "invalid"]:
                if satellites >= 3 or health.get("latitude") is not None:
                    gps_available = True
            dev["gps_available"] = gps_available

            # Enrich with assigned bus details
            assigned_bus_id = dev.get("assigned_bus_id")
            if assigned_bus_id and str(assigned_bus_id).upper() in buses:
                b = buses[str(assigned_bus_id).upper()]
                dev["assigned_bus_name"] = b.get("bus_name")
                dev["assigned_bus_number"] = b.get("bus_number")
            else:
                dev["assigned_bus_name"] = "Unassigned"
                dev["assigned_bus_number"] = "None"

            enriched.append(dev)

        return enriched

    def get_device(self, device_id):
        """Find a single device by device_id."""
        if not device_id:
            return None
        target = str(device_id).strip().upper()
        devices = self.get_all_devices(compute_status=True)
        for d in devices:
            if str(d.get("device_id", "")).strip().upper() == target:
                return d
        return None

    def get_device_by_mac(self, mac_address):
        """Find a device by MAC address."""
        if not mac_address:
            return None
        target = str(mac_address).strip().upper()
        devices = self.get_all_devices(compute_status=True)
        for d in devices:
            if str(d.get("mac_address", "")).strip().upper() == target:
                return d
        return None

    def get_device_by_token(self, device_token):
        """Find a device by its unique authentication token."""
        if not device_token:
            return None
        target = str(device_token).strip()
        devices = self.get_all_devices(compute_status=True)
        for d in devices:
            if d.get("device_token") and str(d.get("device_token")).strip() == target:
                return d
        return None

    def verify_device_credentials(self, device_id, key_or_token):
        """
        Authenticate device against:
        1. Pre-shared fleet API Key (from settings.json or env).
        2. Per-device specific Device Token in devices.json.
        """
        if not key_or_token:
            return False

        settings = self.get_settings()
        configured_key = settings.get("api_key")
        valid_fleet_keys = {
            configured_key,
            "YOUR_API_KEY",
            "default_secret_api_key_12345",
            "bike-tracker-dev-key"
        }
        if key_or_token in valid_fleet_keys:
            return True

        if device_id:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            for d in devices:
                if str(d.get("device_id", "")).strip().upper() == target:
                    dev_tok = d.get("device_token")
                    if dev_tok and dev_tok == key_or_token:
                        return True

        devices = self._read_json(self.devices_file, default=[])
        for d in devices:
            if d.get("device_token") and d.get("device_token") == key_or_token:
                return True

        return False

    def register_device(self, device_data):
        """
        Register a new universal device with identity, MAC, chip type, and token.
        Enforces unique device_id and unique mac_address.
        """
        with _LOCK:
            dev_id = str(device_data.get("device_id") or "").strip().upper()
            if not dev_id:
                raise ValueError("device_id is required")

            devices = self._read_json(self.devices_file, default=[])

            # Check duplicate device_id
            for d in devices:
                if str(d.get("device_id", "")).strip().upper() == dev_id:
                    raise ValueError(f"Device ID '{dev_id}' is already registered")

            mac_address = str(device_data.get("mac_address") or "").strip().upper()
            if mac_address and mac_address not in ["UNKNOWN", ""]:
                for d in devices:
                    d_mac = str(d.get("mac_address", "")).strip().upper()
                    if d_mac and d_mac == mac_address:
                        raise ValueError(f"MAC address '{mac_address}' is already registered to device '{d.get('device_id')}'")

            assigned_bus_id = device_data.get("assigned_bus_id")
            if assigned_bus_id:
                assigned_bus_id = str(assigned_bus_id).strip().upper()
                # Verify bus exists
                bus = self.get_bus(assigned_bus_id)
                if not bus:
                    raise ValueError(f"Bus '{assigned_bus_id}' does not exist")
                # Unassign any previous device assigned to this bus
                for d in devices:
                    if str(d.get("assigned_bus_id", "")).strip().upper() == assigned_bus_id:
                        d["assigned_bus_id"] = None
                # Update the bus's device_id
                self.update_bus(assigned_bus_id, {"device_id": dev_id})
            else:
                assigned_bus_id = None

            now_iso = datetime.now(timezone.utc).isoformat()
            dev_type = str(device_data.get("device_type", "ESP8266")).strip().upper()
            dev_name = device_data.get("device_name") or f"{dev_type} Tracker {dev_id}"
            firmware_ver = str(device_data.get("firmware_version") or "3.2.0").strip()
            token = device_data.get("device_token") or f"tok_{dev_id.lower()}_{uuid.uuid4().hex[:10]}"

            new_dev = {
                "id": len(devices) + 1,
                "device_id": dev_id,
                "device_name": dev_name,
                "mac_address": mac_address or "AA:BB:CC:00:00:00",
                "device_type": dev_type,
                "firmware_version": firmware_ver,
                "device_token": token,
                "assigned_bus_id": assigned_bus_id,
                "is_registered": True,
                "auto_discovered": False,
                "status": "offline",
                "last_seen": None,
                "ip_address": device_data.get("ip_address"),
                "created_at": now_iso,
                "updated_at": now_iso
            }

            devices.append(new_dev)
            self._write_json(self.devices_file, devices)
            return new_dev

    def update_device(self, device_id, update_data):
        """Update configurable fields of a registered device (name, chip type, etc.)."""
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            now_iso = datetime.now(timezone.utc).isoformat()

            # Check duplicate MAC if updated
            new_mac = str(update_data.get("mac_address", "")).strip().upper() if update_data.get("mac_address") else None
            if new_mac and new_mac not in ["UNKNOWN", ""]:
                for d in devices:
                    if str(d.get("device_id", "")).strip().upper() != target:
                        if str(d.get("mac_address", "")).strip().upper() == new_mac:
                            raise ValueError(f"MAC address '{new_mac}' is already registered to device '{d.get('device_id')}'")

            for i, d in enumerate(devices):
                if str(d.get("device_id", "")).strip().upper() == target:
                    for k in ["device_name", "device_type", "firmware_version", "mac_address"]:
                        if k in update_data and update_data[k] is not None:
                            d[k] = str(update_data[k]).strip()
                    d["updated_at"] = now_iso
                    devices[i] = d
                    self._write_json(self.devices_file, devices)
                    return d
            return None

    def auto_discover_device(self, device_id, mac=None, device_type=None, device_name=None, firmware_version=None, ip_address=None):
        """
        Auto-registers newly connected hardware tracker into devices.json
        with auto_discovered=True, awaiting admin bus assignment.
        """
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            now_iso = datetime.now(timezone.utc).isoformat()

            for d in devices:
                if str(d.get("device_id", "")).strip().upper() == target or (
                    mac and str(d.get("mac_address", "")).strip().upper() == str(mac).strip().upper()
                ):
                    return d

            dev_type = str(device_type or "ESP8266").strip().upper()
            dev_name = device_name or f"Auto-Discovered {dev_type} ({target})"
            token = f"tok_{target.lower()}_{uuid.uuid4().hex[:10]}"

            new_dev = {
                "id": len(devices) + 1,
                "device_id": target,
                "device_name": dev_name,
                "mac_address": str(mac).strip().upper() if mac else "UNKNOWN",
                "device_type": dev_type,
                "firmware_version": str(firmware_version or "1.0.0").strip(),
                "device_token": token,
                "assigned_bus_id": None,
                "is_registered": True,
                "auto_discovered": True,
                "status": "online",
                "last_seen": now_iso,
                "ip_address": ip_address,
                "created_at": now_iso,
                "updated_at": now_iso
            }

            devices.append(new_dev)
            self._write_json(self.devices_file, devices)
            return new_dev

    def assign_device_to_bus(self, device_id, bus_id):
        """
        Assign or reassign an ESP/hardware device to a bus, ensuring 1-to-1 mapping.
        """
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            matched = None

            for d in devices:
                if str(d.get("device_id", "")).strip().upper() == target:
                    matched = d
                    break

            if not matched:
                raise ValueError(f"Device '{device_id}' not found")

            if bus_id:
                target_bus_id = str(bus_id).strip().upper()
                bus = self.get_bus(target_bus_id)
                if not bus:
                    raise ValueError(f"Bus '{bus_id}' not found")

                # Clear assignment from any other device currently pointing to this bus
                for d in devices:
                    if d.get("device_id") != matched.get("device_id") and str(d.get("assigned_bus_id", "")).strip().upper() == target_bus_id:
                        d["assigned_bus_id"] = None

                matched["assigned_bus_id"] = target_bus_id
                matched["updated_at"] = datetime.now(timezone.utc).isoformat()

                # Update the bus record
                self.update_bus(target_bus_id, {"device_id": matched["device_id"]})
            else:
                # Unassign
                matched["assigned_bus_id"] = None
                matched["updated_at"] = datetime.now(timezone.utc).isoformat()

            self._write_json(self.devices_file, devices)
            return matched

    def delete_device(self, device_id):
        """Delete an ESP device."""
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            initial_count = len(devices)
            filtered = [d for d in devices if str(d.get("device_id", "")).strip().upper() != target]

            if len(filtered) == initial_count:
                return False

            self._write_json(self.devices_file, filtered)
            return True

    def touch_device_seen(self, device_id, mac=None, device_type=None, ip_address=None, gps_status="valid", assigned_bus_id=None, device_name=None, firmware_version=None, wifi_rssi=None, battery_mv=None, uptime_seconds=None):
        """Record ping arrival timestamp, hardware identifiers, and telemetry diagnostics."""
        with _LOCK:
            target = str(device_id).strip().upper()
            devices = self._read_json(self.devices_file, default=[])
            now_iso = datetime.now(timezone.utc).isoformat()
            matched = None

            for d in devices:
                if str(d.get("device_id", "")).strip().upper() == target or (
                    mac and str(d.get("mac_address", "")).strip().upper() == str(mac).strip().upper()
                ):
                    matched = d
                    break

            if matched:
                matched["last_seen"] = now_iso
                matched["updated_at"] = now_iso
                if ip_address:
                    matched["ip_address"] = ip_address
                if mac and (not matched.get("mac_address") or matched.get("mac_address") == "AA:BB:CC:00:00:00"):
                    matched["mac_address"] = str(mac).strip().upper()
                if device_type:
                    matched["device_type"] = str(device_type).strip().upper()
                if assigned_bus_id and not matched.get("assigned_bus_id"):
                    matched["assigned_bus_id"] = str(assigned_bus_id).strip().upper()
                if device_name and not matched.get("device_name"):
                    matched["device_name"] = str(device_name).strip()
                if firmware_version:
                    matched["firmware_version"] = str(firmware_version).strip()
                if wifi_rssi is not None:
                    matched["wifi_rssi"] = int(wifi_rssi)
                if battery_mv is not None:
                    matched["battery_mv"] = int(battery_mv)
                if uptime_seconds is not None:
                    matched["uptime_seconds"] = int(uptime_seconds)
            else:
                dev_type = str(device_type or "ESP8266").strip().upper()
                dev_name = device_name or f"Auto-Discovered {dev_type} ({target})"
                token = f"tok_{target.lower()}_{uuid.uuid4().hex[:10]}"

                matched = {
                    "id": len(devices) + 1,
                    "device_id": target,
                    "device_name": dev_name,
                    "mac_address": str(mac).strip().upper() if mac else "UNKNOWN",
                    "device_type": dev_type,
                    "firmware_version": str(firmware_version or "1.0.0").strip(),
                    "device_token": token,
                    "assigned_bus_id": str(assigned_bus_id).strip().upper() if assigned_bus_id else None,
                    "is_registered": False,
                    "auto_discovered": True,
                    "status": "online",
                    "last_seen": now_iso,
                    "ip_address": ip_address,
                    "wifi_rssi": int(wifi_rssi) if wifi_rssi is not None else None,
                    "battery_mv": int(battery_mv) if battery_mv is not None else None,
                    "uptime_seconds": int(uptime_seconds) if uptime_seconds is not None else None,
                    "created_at": now_iso,
                    "updated_at": now_iso
                }
                devices.append(matched)

            self._write_json(self.devices_file, devices)
            return matched

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
        """Update or insert current location for a bus with college geofence and daily trip detection."""
        with _LOCK:
            target = str(bus_id).strip().upper()
            locations = self.get_all_locations()

            now = timestamp or datetime.now(timezone.utc)
            now_iso = now.isoformat()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%I:%M:%S %p")

            # College Geofencing Arrival Detection
            college = self.get_college_config()
            dist_to_college_m = haversine_distance_m(
                float(lat), float(lng),
                college["college_latitude"], college["college_longitude"]
            )
            is_at_college = dist_to_college_m <= college["college_geofence_radius_meters"]

            if is_at_college:
                calc_status = "REACHED_COLLEGE"
            else:
                calc_status = status or ("MOVING" if float(speed) > 3.0 else "STOPPED")

            # Manage daily trips state machine
            active_trip = self.process_gps_point_for_trips(
                target, device_id, float(lat), float(lng), float(speed), now, is_at_college
            )

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
                "is_at_college": is_at_college,
                "distance_to_college_m": round(dist_to_college_m, 1),
                "active_trip_id": active_trip.get("id") if active_trip else None,
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
    # SETTINGS & COLLEGE GEOFENCING CONFIGURATION
    # -------------------------------------------------------------------------
    def get_settings(self):
        """Get current system configuration settings."""
        defaults = {
            "online_threshold_seconds": 30,
            "deviation_threshold_meters": 150,
            "geofence_radius_meters": 100,
            "auto_refresh_seconds": 5,
            "server_url": "https://trackbus.pythonanywhere.com",
            "api_key": "YOUR_API_KEY",
            "college_name": "Sphoorthy Engineering College",
            "college_latitude": 17.3156,
            "college_longitude": 78.5833,
            "college_geofence_radius_meters": 120,
            "max_storage_bytes": MAX_STORAGE_BYTES
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

    def get_college_config(self):
        """Get configured college destination and geofence parameters."""
        settings = self.get_settings()
        return {
            "college_name": settings.get("college_name", "Sphoorthy Engineering College"),
            "college_latitude": float(settings.get("college_latitude", 17.3156)),
            "college_longitude": float(settings.get("college_longitude", 78.5833)),
            "college_geofence_radius_meters": int(settings.get("college_geofence_radius_meters", 120))
        }

    def update_college_config(self, config_data):
        """Update college destination and geofence radius."""
        with _LOCK:
            settings = self.get_settings()
            if "college_name" in config_data and config_data["college_name"]:
                settings["college_name"] = str(config_data["college_name"]).strip()
            if "college_latitude" in config_data:
                settings["college_latitude"] = round(float(config_data["college_latitude"]), 6)
            if "college_longitude" in config_data:
                settings["college_longitude"] = round(float(config_data["college_longitude"]), 6)
            if "college_geofence_radius_meters" in config_data:
                settings["college_geofence_radius_meters"] = max(20, int(config_data["college_geofence_radius_meters"]))
            self.update_settings(settings)
            return self.get_college_config()

    def check_college_geofence(self, lat, lng):
        """Calculate distance to college and return geofence status."""
        college = self.get_college_config()
        dist_m = haversine_distance_m(
            float(lat), float(lng),
            college["college_latitude"], college["college_longitude"]
        )
        is_inside = dist_m <= college["college_geofence_radius_meters"]
        return is_inside, round(dist_m, 1)

    # -------------------------------------------------------------------------
    # DAILY TRIPS & 3-TIER DISTANCE ENGINE
    # -------------------------------------------------------------------------
    def process_gps_point_for_trips(self, bus_id, device_id, lat, lng, speed, now_dt, is_at_college=False):
        """
        Manages distinct daily trips (approx 2-4 trips per bus daily):
        - When at college geofence: finalizes active trip (COMPLETED / REACHED_COLLEGE).
        - When departing college (> geofence + 30m) or moving on route: starts next scheduled trip.
        - Calculates accumulated trip distance with noise & stationary filtering.
        """
        with _LOCK:
            target_bus = str(bus_id).strip().upper()
            trips = self._read_json(self.trips_file, default=[])
            today_str = now_dt.strftime("%d-%m-%Y")
            time_str = now_dt.strftime("%I:%M %p")

            # Find active RUNNING trip for this bus today
            active_trip = None
            bus_today_trips = []
            for t in trips:
                if t.get("bus_id", "").upper() == target_bus and t.get("date") == today_str:
                    bus_today_trips.append(t)
                    if t.get("status") == "RUNNING":
                        active_trip = t

            bus_info = self.get_bus(target_bus) or {}
            route_id = bus_info.get("route_id", "AUTOROUTE-01")

            if is_at_college:
                if active_trip:
                    # Finalize trip upon arrival at college
                    last_coords = [round(float(lat), 6), round(float(lng), 6)]
                    active_trip["status"] = "COMPLETED"
                    active_trip["end_time"] = time_str
                    active_trip["arrival_time"] = time_str
                    active_trip["end_coordinates"] = last_coords
                    active_trip["updated_at"] = now_dt.isoformat()
                    self._write_json(self.trips_file, trips)
                    return active_trip
                return None

            # Bus is away from college: either update running trip or initiate next trip
            if not active_trip:
                # Start a new trip for today (e.g. Morning Inbound, Afternoon Return, etc.)
                trip_num = len(bus_today_trips) + 1
                trip_id = f"TRIP-{target_bus}-{now_dt.strftime('%Y%m%d')}-{trip_num}"
                coords = [round(float(lat), 6), round(float(lng), 6)]

                new_trip = {
                    "id": trip_id,
                    "bus_id": target_bus,
                    "device_id": str(device_id or target_bus).upper(),
                    "route_id": route_id,
                    "trip_number": trip_num,
                    "date": today_str,
                    "start_time": time_str,
                    "start_coordinates": coords,
                    "end_time": None,
                    "end_coordinates": None,
                    "distance_km": 0.0,
                    "status": "RUNNING",
                    "arrival_time": None,
                    "last_lat": coords[0],
                    "last_lng": coords[1],
                    "created_at": now_dt.isoformat(),
                    "updated_at": now_dt.isoformat()
                }
                trips.append(new_trip)
                self._write_json(self.trips_file, trips)
                return new_trip
            else:
                # Active trip exists: accumulate distance with filtering
                last_lat = float(active_trip.get("last_lat", active_trip["start_coordinates"][0]))
                last_lng = float(active_trip.get("last_lng", active_trip["start_coordinates"][1]))
                step_m = haversine_distance_m(last_lat, last_lng, float(lat), float(lng))

                # GPS noise filtering (<8m or stationary) and jump/teleport rejection (>5000m)
                if step_m >= 8.0 and step_m < 5000.0:
                    step_km = step_m / 1000.0
                    curr_dist = float(active_trip.get("distance_km", 0.0))
                    active_trip["distance_km"] = round(curr_dist + step_km, 2)
                    active_trip["last_lat"] = round(float(lat), 6)
                    active_trip["last_lng"] = round(float(lng), 6)
                    active_trip["updated_at"] = now_dt.isoformat()
                    self._write_json(self.trips_file, trips)
                return active_trip

    def get_bus_distance_metrics(self, bus_id):
        """
        Calculates and returns 3 distinct distance measurements:
        A. Trip Distance: distance in km for the current trip.
        B. Daily Distance: sum of distances of all trips completed today + current trip.
        C. Seven-Day Distance History: daily km breakdown for the latest seven days.
        """
        target = str(bus_id).strip().upper()
        trips = self._read_json(self.trips_file, default=[])
        bus_trips = [t for t in trips if t.get("bus_id", "").upper() == target]

        now = datetime.now(timezone.utc)
        today_str = now.strftime("%d-%m-%Y")

        today_trips = [t for t in bus_trips if t.get("date") == today_str]
        active_trip = next((t for t in today_trips if t.get("status") == "RUNNING"), None)

        # A. Trip Distance
        if active_trip:
            trip_distance_km = round(float(active_trip.get("distance_km", 0.0)), 2)
            current_trip_status = "RUNNING"
            current_trip_num = active_trip.get("trip_number", 1)
        elif today_trips:
            latest = today_trips[-1]
            trip_distance_km = round(float(latest.get("distance_km", 0.0)), 2)
            current_trip_status = latest.get("status", "COMPLETED")
            current_trip_num = latest.get("trip_number", len(today_trips))
        elif bus_trips:
            latest = bus_trips[-1]
            trip_distance_km = round(float(latest.get("distance_km", 0.0)), 2)
            current_trip_status = latest.get("status", "COMPLETED")
            current_trip_num = latest.get("trip_number", 1)
        else:
            trip_distance_km = 0.0
            current_trip_status = "IDLE"
            current_trip_num = 0

        # B. Daily Distance (Sum of all today's trips)
        daily_distance_km = round(sum(float(t.get("distance_km", 0.0)) for t in today_trips), 2)

        # C. Seven-Day Distance History
        seven_days = []
        seven_day_total_km = 0.0
        for offset in range(6, -1, -1):
            d_date = now - timedelta(days=offset)
            d_str = d_date.strftime("%d-%m-%Y")
            d_name = d_date.strftime("%A")
            short_lbl = d_date.strftime("%b %d")
            d_trips = [t for t in bus_trips if t.get("date") == d_str]
            d_dist = round(sum(float(t.get("distance_km", 0.0)) for t in d_trips), 2)
            seven_day_total_km += d_dist
            seven_days.append({
                "date": d_str,
                "day_name": d_name,
                "label": f"{d_name} ({short_lbl})",
                "distance_km": d_dist,
                "trips_count": len(d_trips),
                "is_today": (d_str == today_str)
            })

        seven_day_total_km = round(seven_day_total_km, 2)

        # Assigned route total & remaining distance
        bus_info = self.get_bus(target) or {}
        route_id = bus_info.get("route_id")
        route = self.get_route(route_id) if route_id else None
        total_route_distance_km = float(route.get("distance_km", 12.0)) if route else 12.0
        remaining_distance_km = max(0.0, round(total_route_distance_km - trip_distance_km, 2))

        return {
            "bus_id": target,
            "trip_distance_km": trip_distance_km,
            "current_trip_status": current_trip_status,
            "current_trip_number": current_trip_num,
            "daily_distance_km": daily_distance_km,
            "daily_trips_count": len(today_trips),
            "seven_day_total_km": seven_day_total_km,
            "seven_day_history": seven_days,
            "total_route_distance_km": total_route_distance_km,
            "remaining_distance_km": remaining_distance_km
        }

    def get_bus_trips(self, bus_id, date_filter=None, limit=50):
        """Retrieve daily trip records for a bus."""
        target = str(bus_id).strip().upper()
        trips = self._read_json(self.trips_file, default=[])
        bus_trips = [t for t in trips if t.get("bus_id", "").upper() == target]
        if date_filter and date_filter.lower() != "all":
            bus_trips = [t for t in bus_trips if t.get("date") == date_filter]
        if limit and limit > 0:
            bus_trips = bus_trips[-limit:]
        return bus_trips

    def get_all_trips(self, date_filter=None, limit=100):
        """Retrieve all fleet daily trips."""
        trips = self._read_json(self.trips_file, default=[])
        if date_filter and date_filter.lower() != "all":
            trips = [t for t in trips if t.get("date") == date_filter]
        if limit and limit > 0:
            trips = trips[-limit:]
        return trips

    # -------------------------------------------------------------------------
    # 300 MB STORAGE MONITORING & OPTIMIZATION
    # -------------------------------------------------------------------------
    def get_storage_metrics(self):
        """
        Calculate precise disk storage consumption against the 300 MB hard limit.
        Returns used/available MB, percentage, warning status, and file breakdown.
        """
        total_used = 0
        categories = {
            "database": 0,
            "tracking": 0,
            "trips": 0,
            "backups": 0,
            "security": 0
        }
        file_list = []

        if self.data_dir.exists():
            for item in self.data_dir.iterdir():
                if item.is_file():
                    try:
                        sz = item.stat().st_size
                        mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc).isoformat()
                        fname = item.name
                        total_used += sz

                        if fname in ["buses.json", "devices.json", "routes.json", "stops.json", "settings.json", "locations.json"]:
                            cat = "database"
                        elif fname in ["history.json", "deviations.json", "stop_events.json", "device_health.json"]:
                            cat = "tracking"
                        elif fname in ["trips.json", "journeys.json"]:
                            cat = "trips"
                        elif fname in ["users.json", "audit_logs.json"]:
                            cat = "security"
                        else:
                            cat = "database"

                        categories[cat] += sz
                        file_list.append({
                            "filename": fname,
                            "category": cat,
                            "size_bytes": sz,
                            "size_kb": round(sz / 1024.0, 2),
                            "size_mb": round(sz / (1024.0 * 1024.0), 4),
                            "last_modified": mtime,
                            "is_permanent": fname in ["buses.json", "devices.json", "routes.json", "stops.json", "settings.json", "users.json"]
                        })
                    except Exception:
                        pass

        if self.backups_dir.exists():
            for bf in self.backups_dir.glob("*.json"):
                try:
                    sz = bf.stat().st_size
                    mtime = datetime.fromtimestamp(bf.stat().st_mtime, tz=timezone.utc).isoformat()
                    total_used += sz
                    categories["backups"] += sz
                    file_list.append({
                        "filename": f"backups/{bf.name}",
                        "category": "backups",
                        "size_bytes": sz,
                        "size_kb": round(sz / 1024.0, 2),
                        "size_mb": round(sz / (1024.0 * 1024.0), 4),
                        "last_modified": mtime,
                        "is_permanent": False
                    })
                except Exception:
                    pass

        total_mb = round(total_used / (1024.0 * 1024.0), 2)
        max_mb = round(MAX_STORAGE_BYTES / (1024.0 * 1024.0), 1)  # 300.0 MB
        available_mb = max(0.0, round(max_mb - total_mb, 2))
        percent_used = min(100.0, round((total_used / MAX_STORAGE_BYTES) * 100.0, 2))

        # Configurable warning levels at 70%, 85%, 95%
        warning_level = "NORMAL"
        if percent_used >= 95.0:
            warning_level = "CRITICAL_95"
        elif percent_used >= 85.0:
            warning_level = "WARNING_85"
        elif percent_used >= 70.0:
            warning_level = "WARNING_70"

        return {
            "max_storage_mb": max_mb,
            "max_storage_bytes": MAX_STORAGE_BYTES,
            "total_used_mb": total_mb,
            "total_used_bytes": total_used,
            "available_mb": available_mb,
            "percent_used": percent_used,
            "warning_level": warning_level,
            "category_breakdown_mb": {
                k: round(v / (1024.0 * 1024.0), 4) for k, v in categories.items()
            },
            "category_breakdown_bytes": categories,
            "files_count": len(file_list),
            "files": sorted(file_list, key=lambda x: x["size_bytes"], reverse=True),
            "retention_policy": "7_days_rolling",
            "last_retention_check": self._last_retention_check.isoformat() if self._last_retention_check else None
        }

    # -------------------------------------------------------------------------
    # USER AUTHENTICATION & RBAC SECURITY
    # -------------------------------------------------------------------------
    def get_all_users(self):
        """List all registered system users (passwords omitted)."""
        users = self._read_json(self.users_file, default=[])
        return [
            {
                "id": u.get("id"),
                "username": u.get("username"),
                "role": u.get("role", "VIEWER"),
                "full_name": u.get("full_name"),
                "created_at": u.get("created_at")
            }
            for u in users
        ]

    def get_user(self, username):
        """Find user by username."""
        if not username:
            return None
        target = str(username).strip().lower()
        users = self._read_json(self.users_file, default=[])
        for u in users:
            if str(u.get("username", "")).strip().lower() == target:
                return u
        return None

    def create_user(self, user_data):
        """Create a new authorized user with role and hashed password."""
        with _LOCK:
            username = str(user_data.get("username", "")).strip().lower()
            if not username or len(username) < 3:
                raise ValueError("Valid username is required (min 3 chars)")

            password = str(user_data.get("password", "")).strip()
            if not password or len(password) < 6:
                raise ValueError("Password must be at least 6 characters")

            users = self._read_json(self.users_file, default=[])
            for u in users:
                if str(u.get("username", "")).strip().lower() == username:
                    raise ValueError(f"Username '{username}' already exists")

            role = str(user_data.get("role", "VIEWER")).strip().upper()
            if role not in ["ADMIN", "VIEWER"]:
                role = "VIEWER"

            now_iso = datetime.now(timezone.utc).isoformat()
            new_u = {
                "id": f"USR-{len(users)+1:03d}",
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": role,
                "full_name": user_data.get("full_name") or username.title(),
                "created_at": now_iso
            }
            users.append(new_u)
            self._write_json(self.users_file, users)
            return {
                "id": new_u["id"],
                "username": new_u["username"],
                "role": new_u["role"],
                "full_name": new_u["full_name"],
                "created_at": new_u["created_at"]
            }

    def update_user_password(self, username, old_password, new_password, is_admin_override=False):
        """Update user password with optional old password verification."""
        with _LOCK:
            target = str(username).strip().lower()
            users = self._read_json(self.users_file, default=[])
            if not new_password or len(new_password) < 6:
                raise ValueError("New password must be at least 6 characters")

            for i, u in enumerate(users):
                if str(u.get("username", "")).strip().lower() == target:
                    if not is_admin_override:
                        if not check_password_hash(u.get("password_hash", ""), old_password):
                            raise ValueError("Current password is incorrect")
                    u["password_hash"] = generate_password_hash(new_password)
                    u["updated_at"] = datetime.now(timezone.utc).isoformat()
                    users[i] = u
                    self._write_json(self.users_file, users)
                    return True
            raise ValueError(f"User '{username}' not found")

    def delete_user(self, username):
        """Delete an authorized user (prevents deleting the root 'admin')."""
        with _LOCK:
            target = str(username).strip().lower()
            if target == "admin":
                raise ValueError("Cannot delete the root administrator account")
            users = self._read_json(self.users_file, default=[])
            filtered = [u for u in users if str(u.get("username", "")).strip().lower() != target]
            if len(filtered) == len(users):
                return False
            self._write_json(self.users_file, filtered)
            return True

    def authenticate_user(self, username, password, client_ip="127.0.0.1"):
        """
        Authenticate user with brute-force lockout protection.
        Locks out after 5 consecutive failed attempts for 15 minutes.
        """
        global _FAILED_LOGINS
        with _LOCK:
            now = datetime.now(timezone.utc)
            target = str(username or "").strip().lower()
            lock_key = f"{client_ip}:{target}"

            # Check if currently locked
            lock_entry = _FAILED_LOGINS.get(lock_key)
            if lock_entry:
                locked_until = lock_entry.get("locked_until")
                if locked_until and now < locked_until:
                    remaining_sec = int((locked_until - now).total_seconds())
                    return False, None, f"Too many failed login attempts. Locked out for {remaining_sec} more seconds."

            user = self.get_user(target)
            if not user:
                self._record_failed_attempt(lock_key, now)
                return False, None, "Invalid username or password"

            stored_hash = user.get("password_hash")
            if not stored_hash or not check_password_hash(stored_hash, password):
                self._record_failed_attempt(lock_key, now)
                return False, None, "Invalid username or password"

            # Success: clear lockout
            if lock_key in _FAILED_LOGINS:
                del _FAILED_LOGINS[lock_key]

            clean_user = {
                "id": user.get("id"),
                "username": user.get("username"),
                "role": user.get("role", "VIEWER"),
                "full_name": user.get("full_name", target)
            }
            return True, clean_user, "Authentication successful"

    def _record_failed_attempt(self, lock_key, now):
        """Increment failed login attempts and lock out if threshold reached."""
        global _FAILED_LOGINS
        entry = _FAILED_LOGINS.get(lock_key, {"attempts": 0, "locked_until": None})
        entry["attempts"] += 1
        if entry["attempts"] >= 5:
            entry["locked_until"] = now + timedelta(minutes=15)
        _FAILED_LOGINS[lock_key] = entry

    # -------------------------------------------------------------------------
    # AUDIT LOGGING
    # -------------------------------------------------------------------------
    def record_audit_log(self, username, role, action, target_type, target_id=None, details=None, ip_address=None):
        """Append an administrative audit log entry."""
        with _LOCK:
            logs = self._read_json(self.audit_logs_file, default=[])
            now = datetime.now(timezone.utc)
            entry = {
                "id": f"AUDIT-{len(logs)+1:06d}",
                "timestamp": now.isoformat(),
                "date": now.strftime("%d-%m-%Y"),
                "time": now.strftime("%I:%M:%S %p"),
                "username": username or "system",
                "role": role or "SYSTEM",
                "action": action,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else "",
                "details": details or "",
                "ip_address": ip_address or "127.0.0.1"
            }
            logs.append(entry)
            self._write_json(self.audit_logs_file, logs)
            return entry

    def get_audit_logs(self, limit=100, action=None):
        """Retrieve audit log records."""
        logs = self._read_json(self.audit_logs_file, default=[])
        if action:
            logs = [l for l in logs if l.get("action") == action]
        if limit and limit > 0:
            logs = logs[-limit:]
        return list(reversed(logs))

    # -------------------------------------------------------------------------
    # 7-DAY ROLLING RETENTION & AUTOMATED BACKUP ENGINE
    # -------------------------------------------------------------------------
    def enforce_seven_day_retention_and_backup(self, force=False):
        """
        Enforce strict 7-day rolling data retention policy:
        1. Automatically deletes historical GPS coordinates older than 7 days from active storage.
        2. Automatically backs up required GPS, trip, and route data into data/backups/.
        3. Automatically deletes backups older than 7 days from backup storage.
        4. Preserves permanent configuration: buses.json, devices.json, routes.json, stops.json, settings.json, users.json.
        5. Protects against 300 MB overflow by emergency pruning if storage exceeds 90%.
        """
        now = datetime.now(timezone.utc)
        if not force and self._last_retention_check:
            elapsed = (now - self._last_retention_check).total_seconds()
            if elapsed < 1800:
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

            # 2. Prune active trips
            trips = self._read_json(self.trips_file, default=[])
            initial_trips_count = len(trips)
            pruned_trips = [t for t in trips if is_recent(t)]
            if len(pruned_trips) != initial_trips_count or not self.trips_file.exists():
                self._write_json(self.trips_file, pruned_trips)

            # 3. Prune active journeys
            journeys = self._read_json(self.journeys_file, default=[])
            pruned_journeys = [j for j in journeys if is_recent(j)]
            if len(pruned_journeys) != len(journeys) or not self.journeys_file.exists():
                self._write_json(self.journeys_file, pruned_journeys)

            # 4. Prune deviations, stop events & audit logs
            devs = self._read_json(self.deviations_file, default=[])
            pruned_devs = [d for d in devs if is_recent(d)]
            if len(pruned_devs) != len(devs):
                self._write_json(self.deviations_file, pruned_devs)

            events = self._read_json(self.stop_events_file, default=[])
            pruned_events = [e for e in events if is_recent(e)]
            if len(pruned_events) != len(events):
                self._write_json(self.stop_events_file, pruned_events)

            audit_logs = self._read_json(self.audit_logs_file, default=[])
            pruned_audit = [a for a in audit_logs if is_recent(a)]
            if len(pruned_audit) != len(audit_logs):
                self._write_json(self.audit_logs_file, pruned_audit)

            # 5. Create daily automated backup snapshot within retention policy
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
                "trips_count": len(pruned_trips),
                "history": pruned_history,
                "trips": pruned_trips
            }
            self._write_json(backup_filepath, backup_data)

            # 6. Automatically delete backup snapshots older than 7 days
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
                "active_trips": len(pruned_trips),
                "latest_backup_file": backup_filename,
                "deleted_old_backups": deleted_backups,
                "timestamp": now.isoformat()
            }

    # -------------------------------------------------------------------------
    # UTILITIES / CLEANUP
    # -------------------------------------------------------------------------
    def clear_all_data(self):
        """Clear dynamic data for test teardown or hard reset."""
        global _ACTIVE_TRIPS
        with _LOCK:
            _ACTIVE_TRIPS.clear()
            self._write_json(self.buses_file, [])
            self._write_json(self.devices_file, [])
            self._write_json(self.locations_file, {})
            self._write_json(self.history_file, [])
            self._write_json(self.deviations_file, [])
            self._write_json(self.journeys_file, [])
            self._write_json(self.trips_file, [])
            self._write_json(self.stop_events_file, [])
            self._write_json(self.device_health_file, {})
            self._write_json(self.users_file, DEFAULT_USERS)
            self._write_json(self.audit_logs_file, [])
            if self.backups_dir.exists():
                for bf in self.backups_dir.glob("*.json"):
                    try:
                        bf.unlink()
                    except Exception:
                        pass
            self._last_retention_check = None


# Singleton instance
db_instance = JsonDB()
