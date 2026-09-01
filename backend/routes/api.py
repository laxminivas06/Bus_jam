import math
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, current_app, session
from backend.json_db import db_instance
from backend.models import Bus

api_bp = Blueprint("api", __name__, url_prefix="/api")


def calculate_speed_and_heading(prev_lat, prev_lng, prev_time_iso, curr_lat, curr_lng, curr_time):
    """
    Calculate speed (km/h) and heading angle (0-360 deg) between previous and current GPS points.
    """
    try:
        prev_time = datetime.fromisoformat(prev_time_iso)
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0, 0.0

    d_lon = math.radians(curr_lng - prev_lng)
    lat1_r = math.radians(prev_lat)
    lat2_r = math.radians(curr_lat)

    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    heading = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    # Haversine distance
    d_lat = lat2_r - lat1_r
    a = math.sin(d_lat / 2.0)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(d_lon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(max(0.0, min(1.0, a))), math.sqrt(max(0.0, min(1.0, 1.0 - a))))
    distance_km = 6371.0 * c

    time_diff_hours = (curr_time - prev_time).total_seconds() / 3600.0
    if time_diff_hours > 0 and distance_km > 0.001:
        speed = distance_km / time_diff_hours
        speed = min(speed, 120.0)  # Filter out GPS spike anomalies
    else:
        speed = 0.0

    return round(speed, 1), round(heading, 1)


def verify_device_auth():
    """Verify X-Device-ID and X-Device-Token headers if provided."""
    device_id = request.headers.get("X-Device-ID")
    device_token = request.headers.get("X-Device-Token")

    expected_id = current_app.config.get("DEVICE_ID")
    expected_token = current_app.config.get("DEVICE_TOKEN")

    if device_id or device_token:
        if device_id != expected_id or device_token != expected_token:
            return False
    return True


def verify_admin_auth():
    """Verify admin session or HTTP Authorization header."""
    if session.get("is_admin"):
        return True

    auth = request.authorization
    if auth and auth.username == current_app.config.get("ADMIN_USERNAME") and auth.password == current_app.config.get("ADMIN_PASSWORD"):
        return True

    admin_header_user = request.headers.get("X-Admin-User")
    admin_header_pass = request.headers.get("X-Admin-Pass")
    if admin_header_user == current_app.config.get("ADMIN_USERNAME") and admin_header_pass == current_app.config.get("ADMIN_PASSWORD"):
        return True

    return False


@api_bp.route("/health", methods=["GET"])
def health_check():
    """System health check endpoint."""
    return jsonify({
        "status": "healthy",
        "storage": "json",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "College Bus Live Tracking System",
        "version": "2.0.0"
    }), 200


@api_bp.route("/buses", methods=["GET"])
def get_buses():
    """
    Get list of all buses with live location details and summary metrics from JSON database.
    Supports query parameters: search, route, status (online/offline)
    """
    threshold = current_app.config.get("ONLINE_THRESHOLD_SECONDS", 30)
    all_buses = Bus.get_all(active_only=True)

    search = request.args.get("search", "").strip().lower()
    route_filter = request.args.get("route", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    bus_list = [b.to_dict(online_threshold_seconds=threshold) for b in all_buses]

    # Filters
    if search:
        bus_list = [
            b for b in bus_list
            if search in b.get("bus_id", "").lower()
            or search in b.get("bus_number", "").lower()
            or search in b.get("route_name", "").lower()
            or search in b.get("driver_name", "").lower()
        ]

    if route_filter and route_filter.lower() != "all":
        bus_list = [b for b in bus_list if b.get("route_name") == route_filter]

    if status_filter in ["online", "offline"]:
        is_online_target = (status_filter == "online")
        bus_list = [b for b in bus_list if b.get("is_online") == is_online_target]

    # Global metrics
    all_buses_dict = [b.to_dict(online_threshold_seconds=threshold) for b in all_buses]
    total_count = len(all_buses_dict)
    online_count = sum(1 for b in all_buses_dict if b.get("is_online"))
    offline_count = total_count - online_count

    # Find the most recent update timestamp
    last_update_ts = None
    for b in all_buses_dict:
        curr = b.get("current_location")
        if curr and curr.get("updated_at"):
            if not last_update_ts or curr["updated_at"] > last_update_ts:
                last_update_ts = curr["updated_at"]

    unique_routes = sorted(list({b.route_name for b in all_buses if b.route_name}))

    return jsonify({
        "status": "success",
        "metrics": {
            "total_buses": total_count,
            "online_buses": online_count,
            "offline_buses": offline_count,
            "last_update": last_update_ts,
        },
        "routes": unique_routes,
        "count": len(bus_list),
        "buses": bus_list
    }), 200


@api_bp.route("/buses/<bus_id>", methods=["GET"])
def get_bus(bus_id):
    """Get single bus details and current location."""
    threshold = current_app.config.get("ONLINE_THRESHOLD_SECONDS", 30)
    bus = Bus.find_by_id(bus_id)

    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    return jsonify({
        "status": "success",
        "bus": bus.to_dict(online_threshold_seconds=threshold)
    }), 200


@api_bp.route("/locations/save", methods=["GET", "POST"])
@api_bp.route("/location", methods=["GET", "POST"])
def save_location():
    """
    Main Hardware-Independent GPS Receiver API endpoint.
    Accepts coordinates from:
      - A7600C / A7670C AT commands (AT+HTTPACTION=0 GET)
      - Arduino UNO + GSM
      - Browser URL bar
      - Postman / cURL
      - Python GPS simulator
    """
    json_data = request.get_json(silent=True) or {}
    args = request.args
    form = request.form

    apikey = (
        args.get("apikey")
        or args.get("api_key")
        or json_data.get("apikey")
        or json_data.get("api_key")
        or request.headers.get("X-API-KEY")
    )

    device_id = (
        args.get("deviceId")
        or args.get("device_id")
        or args.get("bus_no")
        or args.get("bus_id")
        or args.get("bus_number")
        or json_data.get("deviceId")
        or json_data.get("device_id")
        or json_data.get("bus_no")
        or json_data.get("bus_id")
        or form.get("deviceId")
        or form.get("bus_no")
    )

    raw_lat = (
        args.get("latitude")
        or json_data.get("latitude")
        or form.get("latitude")
    )

    raw_lng = (
        args.get("longitude")
        or json_data.get("longitude")
        or form.get("longitude")
    )

    speed = (
        args.get("speed")
        or json_data.get("speed")
        or form.get("speed")
    )

    heading = (
        args.get("heading")
        or json_data.get("heading")
        or form.get("heading")
    )

    # 1. Validate API key
    configured_api_key = current_app.config.get("API_KEY")
    if apikey:
        if apikey != configured_api_key:
            return jsonify({"success": False, "status": "error", "message": "Invalid API key"}), 401
    else:
        if not verify_device_auth():
            return jsonify({"success": False, "status": "error", "message": "Unauthorized device credentials"}), 401

    # 2. Validate deviceId / bus number
    if not device_id or not isinstance(device_id, str) or not device_id.strip():
        return jsonify({"success": False, "status": "error", "message": "Missing deviceId (Bus Number)"}), 400

    device_id = device_id.strip().upper()

    # 3. Validate coordinates
    if raw_lat is None or raw_lng is None:
        return jsonify({"success": False, "status": "error", "message": "Latitude and longitude are required"}), 400

    try:
        latitude = float(raw_lat)
        longitude = float(raw_lng)
    except (ValueError, TypeError):
        return jsonify({"success": False, "status": "error", "message": "Latitude and longitude must be valid numeric floating point values"}), 400

    if not (-90.0 <= latitude <= 90.0):
        return jsonify({"success": False, "status": "error", "message": "Latitude must be between -90 and 90 degrees"}), 400

    if not (-180.0 <= longitude <= 180.0):
        return jsonify({"success": False, "status": "error", "message": "Longitude must be between -180 and 180 degrees"}), 400

    # 4. Generate Server Date/Time automatically
    now = datetime.now(timezone.utc)

    # 5. Ensure Bus exists in JSON storage
    bus = Bus.find_by_id(device_id)
    if not bus:
        bus = Bus(
            bus_id=device_id,
            bus_number=device_id,
            route_name=f"Route - {device_id}",
            driver_name="Unassigned",
            driver_phone="N/A",
            capacity=50,
            is_active=True
        )
        bus.save()

    # 6. Calculate Speed and Heading automatically if not provided
    if speed is not None:
        try:
            speed = float(speed)
            if speed < 0:
                return jsonify({"success": False, "status": "error", "message": "Speed cannot be negative"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "status": "error", "message": "Speed must be numeric"}), 400

    if heading is not None:
        try:
            heading = float(heading) % 360.0
        except (ValueError, TypeError):
            heading = 0.0

    prev_loc = db_instance.get_location(device_id)
    if speed is None or heading is None:
        if prev_loc and prev_loc.get("timestamp"):
            calc_speed, calc_heading = calculate_speed_and_heading(
                prev_loc["latitude"], prev_loc["longitude"], prev_loc["timestamp"],
                latitude, longitude, now
            )
            speed = calc_speed if speed is None else float(speed)
            heading = calc_heading if heading is None else float(heading)
        else:
            speed = 0.0 if speed is None else float(speed)
            heading = 0.0 if heading is None else float(heading)

    # 7. Update JSON Database
    saved_location = db_instance.save_current_location(
        bus_id=device_id,
        lat=latitude,
        lng=longitude,
        speed=speed,
        heading=heading,
        timestamp=now
    )

    db_instance.add_location_history(
        bus_id=device_id,
        lat=latitude,
        lng=longitude,
        speed=speed,
        heading=heading,
        timestamp=now
    )

    # 8. Lightweight response for SIMCom AT+HTTPREAD
    return jsonify({
        "success": True,
        "status": "success",
        "message": "Location saved",
        "data": {
            "bus_no": device_id,
            "deviceId": device_id,
            "bus_id": device_id,
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed,
            "heading": heading,
            "date": saved_location["date"],
            "time": saved_location["time"],
            "timestamp": saved_location["timestamp"]
        }
    }), 200


@api_bp.route("/buses/<bus_id>/history", methods=["GET"])
def get_bus_history(bus_id):
    """
    Get historical locations for a specific bus from JSON storage.
    Supports ?date=YYYY-MM-DD (or DD-MM-YYYY or 'all') and ?limit=N.
    """
    bus = Bus.find_by_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    date_filter = request.args.get("date", "all").strip()
    limit = request.args.get("limit", 500, type=int)

    history_result = db_instance.get_bus_history(bus_id, date_filter=date_filter, limit=limit)

    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_number": bus.bus_number,
        "route_name": bus.route_name,
        "selected_date": date_filter,
        "available_dates": history_result["available_dates"],
        "count": history_result["total_count"],
        "history": history_result["records"]
    }), 200


# -----------------------------------------------------------------------------
# ADMIN AUTH & BUS MANAGEMENT CRUD
# -----------------------------------------------------------------------------
@api_bp.route("/admin/login", methods=["POST"])
def admin_login():
    """Admin login endpoint."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    expected_user = current_app.config.get("ADMIN_USERNAME", "admin")
    expected_pass = current_app.config.get("ADMIN_PASSWORD", "adminpass")

    if username == expected_user and password == expected_pass:
        session["is_admin"] = True
        return jsonify({
            "status": "success",
            "message": "Admin login successful",
            "username": username
        }), 200

    return jsonify({"status": "error", "message": "Invalid username or password"}), 401


@api_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    """Admin logout endpoint."""
    session.pop("is_admin", None)
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@api_bp.route("/admin/buses", methods=["POST"])
def create_bus_admin():
    """Create a new bus in JSON database."""
    if not verify_admin_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    bus_id = data.get("bus_id", "").strip().upper()
    bus_number = data.get("bus_number", "").strip()
    route_name = data.get("route_name", "").strip()
    driver_name = data.get("driver_name", "").strip()
    driver_phone = data.get("driver_phone", "").strip()
    capacity = data.get("capacity", 50)

    if not bus_id or not bus_number or not route_name or not driver_name or not driver_phone:
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    if Bus.find_by_id(bus_id):
        return jsonify({"status": "error", "message": f"Bus ID '{bus_id}' already exists"}), 409

    new_bus = Bus(
        bus_id=bus_id,
        bus_number=bus_number,
        route_name=route_name,
        driver_name=driver_name,
        driver_phone=driver_phone,
        capacity=capacity,
        is_active=True
    )
    saved = new_bus.save()

    return jsonify({
        "status": "success",
        "message": f"Bus {bus_id} created successfully",
        "bus": saved.to_dict()
    }), 201


@api_bp.route("/admin/buses/<bus_id>", methods=["PUT"])
def update_bus_admin(bus_id):
    """Update bus details in JSON database."""
    if not verify_admin_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    bus = Bus.find_by_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    data = request.get_json(silent=True) or {}
    updated = db_instance.update_bus(bus_id, data)

    return jsonify({
        "status": "success",
        "message": f"Bus {bus_id} updated successfully",
        "bus": Bus(**updated).to_dict() if updated else bus.to_dict()
    }), 200


@api_bp.route("/admin/buses/<bus_id>", methods=["DELETE"])
def delete_bus_admin(bus_id):
    """Delete a bus from JSON database."""
    if not verify_admin_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    success = db_instance.delete_bus(bus_id)
    if not success:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    return jsonify({"status": "success", "message": f"Bus {bus_id} deleted successfully"}), 200
