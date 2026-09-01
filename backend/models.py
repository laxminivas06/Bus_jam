from datetime import datetime, timezone
from backend.json_db import db_instance


class Bus:
    """Pure Python Bus entity backed by JSON storage."""

    def __init__(self, bus_id, bus_number=None, route_name=None, driver_name="Unassigned",
                 driver_phone="N/A", capacity=50, is_active=True, created_at=None, updated_at=None, id=None):
        self.id = id
        self.bus_id = str(bus_id).strip().upper()
        self.bus_number = bus_number or self.bus_id
        self.route_name = route_name or f"Route - {self.bus_id}"
        self.driver_name = driver_name
        self.driver_phone = driver_phone
        self.capacity = int(capacity)
        self.is_active = bool(is_active)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self, online_threshold_seconds=30):
        curr_loc = db_instance.get_location(self.bus_id)
        
        is_online = False
        if curr_loc and curr_loc.get("updated_at"):
            try:
                updated_time = datetime.fromisoformat(curr_loc["updated_at"])
                if updated_time.tzinfo is None:
                    updated_time = updated_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                seconds_since_update = (now - updated_time).total_seconds()
                is_online = seconds_since_update <= online_threshold_seconds
            except Exception:
                is_online = False

        return {
            "id": self.id,
            "bus_id": self.bus_id,
            "bus_number": self.bus_number,
            "route_name": self.route_name,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "capacity": self.capacity,
            "is_active": self.is_active,
            "is_online": is_online,
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
    def get_all(cls, active_only=True):
        buses_data = db_instance.get_all_buses()
        buses = [cls(**b) for b in buses_data]
        if active_only:
            return [b for b in buses if b.is_active]
        return buses

    def save(self):
        bus_dict = {
            "bus_id": self.bus_id,
            "bus_number": self.bus_number,
            "route_name": self.route_name,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "capacity": self.capacity,
            "is_active": self.is_active,
        }
        existing = db_instance.get_bus(self.bus_id)
        if existing:
            updated = db_instance.update_bus(self.bus_id, bus_dict)
            return Bus(**updated) if updated else self
        else:
            created = db_instance.create_bus(bus_dict)
            return Bus(**created)
