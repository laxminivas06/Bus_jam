from datetime import datetime, timezone
from backend.json_db import db_instance


class Bus:
    """Bus entity backed by JSON storage with multi-device ESP8266 association."""

    def __init__(self, bus_id, bus_name=None, bus_number=None, device_id=None,
                 route_name=None, route_id=None, driver_name="Unassigned",
                 driver_phone="N/A", capacity=50, is_active=True,
                 campus="Sphoorthy Campus Lead",
                 created_at=None, updated_at=None, id=None):
        self.id = id
        self.bus_id = str(bus_id).strip().upper()
        self.bus_name = bus_name or f"Bus {self.bus_id}"
        self.bus_number = bus_number or self.bus_id
        self.device_id = str(device_id or self.bus_id).strip().upper()
        self.route_id = route_id or "AUTOROUTE-01"
        self.route_name = route_name or f"Route - {self.bus_id}"
        self.driver_name = driver_name
        self.driver_phone = driver_phone
        self.capacity = int(capacity)
        self.is_active = bool(is_active)
        self.campus = campus or "Sphoorthy Campus Lead"
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self, online_threshold_seconds=30):
        curr_loc = db_instance.get_location(self.bus_id)
        
        connection_status = "no_data"
        is_online = False
        is_moving = False
        is_stopped = False
        has_gps_issue = False

        if curr_loc and curr_loc.get("updated_at"):
            try:
                updated_time = datetime.fromisoformat(curr_loc["updated_at"])
                if updated_time.tzinfo is None:
                    updated_time = updated_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                seconds_since_update = (now - updated_time).total_seconds()
                
                if seconds_since_update <= online_threshold_seconds:
                    is_online = True
                    satellites = curr_loc.get("satellites")
                    gps_status = curr_loc.get("gps_status", "valid")
                    lat = float(curr_loc.get("latitude", 0.0))
                    lng = float(curr_loc.get("longitude", 0.0))

                    if gps_status == "no_fix" or (satellites is not None and satellites < 3) or (abs(lat) < 0.0001 and abs(lng) < 0.0001):
                        connection_status = "gps_unavailable"
                        has_gps_issue = True
                    else:
                        connection_status = "connected"
                        speed = float(curr_loc.get("speed", 0.0) or 0.0)
                        if speed > 3.0:
                            is_moving = True
                        else:
                            is_stopped = True
                else:
                    connection_status = "offline"
            except Exception:
                connection_status = "offline"

        # Determine current route status description
        current_route_status = "Stationary at Terminal"
        if is_moving:
            current_route_status = f"En Route: {self.route_name}"
        elif is_stopped:
            current_route_status = f"Stopped on: {self.route_name}"
        elif connection_status == "gps_unavailable":
            current_route_status = "GPS Signal Searching"
        elif connection_status == "offline":
            current_route_status = "Parked / Offline"

        device_health = db_instance.get_device_health(self.device_id) or db_instance.get_device_health(self.bus_id)

        # Get count of auto-detected routes for this bus
        bus_routes = db_instance.get_routes_by_bus(self.bus_id)
        total_routes_detected = len(bus_routes)

        return {
            "id": self.id,
            "bus_id": self.bus_id,
            "bus_name": self.bus_name,
            "bus_number": self.bus_number,
            "device_id": self.device_id,
            "route_id": self.route_id,
            "route_name": self.route_name,
            "current_route_status": current_route_status,
            "connection_status": connection_status,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "capacity": self.capacity,
            "campus": self.campus,
            "is_active": self.is_active,
            "is_online": is_online,
            "is_moving": is_moving,
            "is_stopped": is_stopped,
            "has_gps_issue": has_gps_issue,
            "total_routes_detected": total_routes_detected,
            "device_health": device_health,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_location": curr_loc,
        }

    @classmethod
    def find_by_id(cls, bus_id):
        data = db_instance.get_bus(bus_id)
        if data:
            return cls(**data)
        return None

    @classmethod
    def find_by_device_id(cls, device_id):
        data = db_instance.get_bus_by_device_id(device_id)
        if data:
            return cls(**data)
        return None

    @classmethod
    def get_all(cls, active_only=True):
        buses_data = db_instance.get_all_buses()
        buses = [cls(**b) for b in buses_data]
        if active_only:
            return [b for b in buses if b.is_active]
        return buses

    def save(self):
        bus_dict = {
            "bus_id": self.bus_id,
            "bus_name": self.bus_name,
            "bus_number": self.bus_number,
            "device_id": self.device_id,
            "route_id": self.route_id,
            "route_name": self.route_name,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "capacity": self.capacity,
            "campus": self.campus,
            "is_active": self.is_active,
        }
        existing = db_instance.get_bus(self.bus_id)
        if existing:
            updated = db_instance.update_bus(self.bus_id, bus_dict)
            return Bus(**updated) if updated else self
        else:
            created = db_instance.create_bus(bus_dict)
            return Bus(**created)
