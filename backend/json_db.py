import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

# Thread lock for concurrent file safety
_LOCK = threading.RLock()


class JsonDB:
    """
    Robust, thread-safe JSON-only database layer.
    Persists data in structured JSON files with zero external database dependencies.
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

        self.init_storage()

    def init_storage(self):
        """Ensure data directory and required empty JSON files exist."""
        with _LOCK:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            files_and_defaults = [
                (self.buses_file, []),
                (self.locations_file, {}),
                (self.history_file, []),
                (self.settings_file, {"online_threshold_seconds": 30}),
                (self.users_file, []),
            ]

            for file_path, default_content in files_and_defaults:
                if not file_path.exists() or file_path.stat().st_size == 0:
                    self._write_json_direct(file_path, default_content)

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
    # BUSES CRUD
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
            if b.get("bus_id", "").upper() == target or b.get("bus_number", "").upper() == target:
                return b
        return None

    def create_bus(self, bus_data):
        """Create and store a new bus."""
        with _LOCK:
            buses = self.get_all_buses()
            bus_id = str(bus_data.get("bus_id") or bus_data.get("bus_number") or "").strip().upper()
            if not bus_id:
                raise ValueError("bus_id is required")

            # Check if bus already exists
            for b in buses:
                if b.get("bus_id", "").upper() == bus_id:
                    return b

            now_iso = datetime.now(timezone.utc).isoformat()
            new_bus = {
                "id": len(buses) + 1,
                "bus_id": bus_id,
                "bus_number": bus_data.get("bus_number") or bus_id,
                "route_name": bus_data.get("route_name") or f"Route - {bus_id}",
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
                    for k in ["bus_number", "route_name", "driver_name", "driver_phone", "capacity", "is_active"]:
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

    def save_current_location(self, bus_id, lat, lng, speed=0.0, heading=0.0, timestamp=None):
        """Update or insert current location for a bus."""
        with _LOCK:
            target = str(bus_id).strip().upper()
            locations = self.get_all_locations()

            now = timestamp or datetime.now(timezone.utc)
            now_iso = now.isoformat()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%I:%M:%S %p")

            loc_entry = {
                "id": len(locations) + 1,
                "bus_id": target,
                "bus_no": target,
                "latitude": float(lat),
                "longitude": float(lng),
                "speed": float(speed),
                "heading": float(heading),
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
    def add_location_history(self, bus_id, lat, lng, speed=0.0, heading=0.0, timestamp=None):
        """Append a location history ping."""
        with _LOCK:
            target = str(bus_id).strip().upper()
            history = self._read_json(self.history_file, default=[])

            now = timestamp or datetime.now(timezone.utc)
            now_iso = now.isoformat()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%I:%M:%S %p")

            entry = {
                "id": len(history) + 1,
                "bus_id": target,
                "bus_no": target,
                "latitude": float(lat),
                "longitude": float(lng),
                "speed": float(speed),
                "heading": float(heading),
                "timestamp": now_iso,
                "date": date_str,
                "time": time_str,
            }

            history.append(entry)
            self._write_json(self.history_file, history)
            return entry

    def get_bus_history(self, bus_id, date_filter=None, limit=500):
        """
        Query location history for a bus, optionally filtered by date.
        date_filter can be 'YYYY-MM-DD', 'DD-MM-YYYY', or 'all'.
        """
        target = str(bus_id).strip().upper()
        history = self._read_json(self.history_file, default=[])

        # Filter by bus
        bus_records = [h for h in history if h.get("bus_id", "").upper() == target]

        # Extract available dates
        all_dates = []
        for r in bus_records:
            d = r.get("date")
            if d and d not in all_dates:
                all_dates.append(d)

        # Apply date filtering
        if date_filter and date_filter.lower() != "all":
            formatted_filter = date_filter.strip()
            # If incoming is YYYY-MM-DD, convert to DD-MM-YYYY
            if len(formatted_filter) == 10 and formatted_filter[4] == "-" and formatted_filter[7] == "-":
                parts = formatted_filter.split("-")
                formatted_filter = f"{parts[2]}-{parts[1]}-{parts[0]}"

            filtered_records = [
                r for r in bus_records
                if r.get("date") == formatted_filter
            ]
        else:
            filtered_records = bus_records

        if limit and limit > 0:
            filtered_records = filtered_records[-limit:]

        return {
            "records": filtered_records,
            "available_dates": all_dates,
            "total_count": len(filtered_records),
        }

    # -------------------------------------------------------------------------
    # UTILITIES / CLEANUP
    # -------------------------------------------------------------------------
    def clear_all_data(self):
        """Clear all data for test teardown or hard reset."""
        with _LOCK:
            self._write_json(self.buses_file, [])
            self._write_json(self.locations_file, {})
            self._write_json(self.history_file, [])
            self._write_json(self.users_file, [])


# Singleton instance
db_instance = JsonDB()
