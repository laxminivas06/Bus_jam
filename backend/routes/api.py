import io
import csv
import math
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request, current_app, session, Response
from backend.json_db import db_instance
from backend.models import Bus
from backend.route_engine import (
    haversine_distance_m,
    haversine_distance_km,
    calculate_bearing,
    bearing_to_cardinal,
    distance_to_route_polyline,
    calculate_route_progress_and_eta,
    compute_trip_summary
)

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

    heading = calculate_bearing(prev_lat, prev_lng, curr_lat, curr_lng)
    distance_km = haversine_distance_km(prev_lat, prev_lng, curr_lat, curr_lng)

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
        "service": "Smart Bus Live Tracking & Route Intelligence System",
        "version": "3.2.0"
    }), 200


@api_bp.route("/campuses", methods=["GET"])
def get_campuses():
    """List registered campuses with vehicle fleet summaries."""
    all_buses = Bus.get_all(active_only=True)
    settings = db_instance.get_settings()
    threshold = int(settings.get("online_threshold_seconds", 30))
    all_buses_dict = [b.to_dict(online_threshold_seconds=threshold) for b in all_buses]

    campuses_dict = {}
    for b in all_buses_dict:
        c_name = b.get("campus") or "Sphoorthy Campus Lead"
        if c_name not in campuses_dict:
            campuses_dict[c_name] = {"name": c_name, "total_buses": 0, "active_buses": 0, "offline_buses": 0}
        campuses_dict[c_name]["total_buses"] += 1
        if b.get("is_online"):
            campuses_dict[c_name]["active_buses"] += 1
        else:
            campuses_dict[c_name]["offline_buses"] += 1

    if not campuses_dict:
        campuses_dict["Sphoorthy Campus Lead"] = {
            "name": "Sphoorthy Campus Lead",
            "total_buses": 0,
            "active_buses": 0,
            "offline_buses": 0
        }

    return jsonify({
        "status": "success",
        "count": len(campuses_dict),
        "campuses": list(campuses_dict.values())
    }), 200


@api_bp.route("/retention/status", methods=["GET"])
def get_retention_status():
    """Return status of the 7-day rolling data retention and automatic backup engine."""
    res = db_instance.enforce_seven_day_retention_and_backup(force=False)
    return jsonify(res), 200


@api_bp.route("/retention/cleanup", methods=["POST"])
def trigger_retention_cleanup():
    """Trigger immediate 7-day data retention cleanup and backup snapshot creation."""
    res = db_instance.enforce_seven_day_retention_and_backup(force=True)
    return jsonify(res), 200


@api_bp.route("/buses", methods=["GET"])
def get_buses():
    """
    Get list of all buses with live location details and summary metrics.
    Supports query parameters: search, route, status
    """
    settings = db_instance.get_settings()
    threshold = int(settings.get("online_threshold_seconds", 30))
    all_buses = Bus.get_all(active_only=True)

    search = request.args.get("search", "").strip().lower()
    route_filter = request.args.get("route", "").strip()
    status_filter = request.args.get("status", "").strip().lower()
    campus_filter = request.args.get("campus", "").strip().lower()

    all_buses_dict = [b.to_dict(online_threshold_seconds=threshold) for b in all_buses]

    # Global metrics
    total_count = len(all_buses_dict)
    active_count = sum(1 for b in all_buses_dict if b.get("is_online"))
    offline_count = total_count - active_count
    moving_count = sum(1 for b in all_buses_dict if b.get("is_moving"))
    stopped_count = sum(1 for b in all_buses_dict if b.get("is_stopped"))
    gps_issue_count = sum(1 for b in all_buses_dict if b.get("connection_status") == "gps_unavailable")
    sending_gps_count = sum(1 for b in all_buses_dict if b.get("is_online") and not b.get("has_gps_issue"))
    all_routes = db_instance.get_all_routes()
    total_routes_detected = len(all_routes)

    # Calculate fleet average speed for online buses
    speeds = [
        float(b["current_location"]["speed"])
        for b in all_buses_dict
        if b.get("is_online") and b.get("current_location") and b["current_location"].get("speed") is not None
    ]
    avg_fleet_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0

    # Today's total distance across fleet
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%d-%m-%Y")
    total_distance_today_km = 0.0
    for b in all_buses_dict:
        hist = db_instance.get_bus_history(b["bus_id"], date_filter=today_str, limit=500)
        total_distance_today_km += hist.get("trip_summary", {}).get("total_distance_km", 0.0)

    # Today's total active deviations
    today_deviations = db_instance.get_deviations(date_filter=today_str)
    active_deviations_count = sum(1 for d in today_deviations if d.get("status") == "ACTIVE")

    # Most recent update timestamp
    last_update_ts = None
    for b in all_buses_dict:
        curr = b.get("current_location")
        if curr and curr.get("updated_at"):
            if not last_update_ts or curr["updated_at"] > last_update_ts:
                last_update_ts = curr["updated_at"]

    # Filter buses
    bus_list = all_buses_dict

    if search:
        bus_list = [
            b for b in bus_list
            if search in b.get("bus_id", "").lower()
            or search in b.get("bus_name", "").lower()
            or search in b.get("bus_number", "").lower()
            or search in b.get("device_id", "").lower()
            or search in b.get("route_name", "").lower()
            or search in b.get("driver_name", "").lower()
        ]

    if route_filter and route_filter.lower() != "all":
        bus_list = [b for b in bus_list if b.get("route_name") == route_filter or b.get("route_id") == route_filter]

    if campus_filter and campus_filter != "all":
        bus_list = [b for b in bus_list if campus_filter in b.get("campus", "").lower()]

    if status_filter == "online" or status_filter == "active" or status_filter == "connected":
        bus_list = [b for b in bus_list if b.get("connection_status") == "connected"]
    elif status_filter == "offline":
        bus_list = [b for b in bus_list if b.get("connection_status") in ("offline", "no_data")]
    elif status_filter == "moving":
        bus_list = [b for b in bus_list if b.get("is_moving")]
    elif status_filter == "stopped":
        bus_list = [b for b in bus_list if b.get("is_stopped")]
    elif status_filter in ("gps_issue", "gps_unavailable"):
        bus_list = [b for b in bus_list if b.get("connection_status") == "gps_unavailable"]

    unique_routes = sorted(list({b.route_name for b in all_buses if b.route_name}))

    return jsonify({
        "status": "success",
        "metrics": {
            "total_buses": total_count,
            "active_buses": active_count,
            "online_buses": active_count,
            "offline_buses": offline_count,
            "sending_gps_buses": sending_gps_count,
            "moving_buses": moving_count,
            "stopped_buses": stopped_count,
            "gps_unavailable_buses": gps_issue_count,
            "total_routes_detected": total_routes_detected,
            "avg_fleet_speed": avg_fleet_speed,
            "total_distance_today_km": round(total_distance_today_km, 2),
            "active_deviations": active_deviations_count,
            "last_update": last_update_ts,
        },
        "routes": unique_routes,
        "count": len(bus_list),
        "buses": bus_list
    }), 200


@api_bp.route("/buses", methods=["POST"])
def register_bus():
    """Create and register a new bus with its ESP device ID."""
    data = request.get_json(silent=True) or {}
    raw_bus_id = data.get("bus_id") or data.get("bus_number") or ""
    bus_id = raw_bus_id.strip()
    bus_number = (data.get("bus_number") or bus_id).strip()
    bus_name = (data.get("bus_name") or f"College Bus {bus_number}").strip()
    device_id = (data.get("device_id") or bus_id).strip().lower()

    if not bus_id or not bus_number:
        return jsonify({"status": "error", "message": "Bus ID and Bus Number are required"}), 400

    existing = Bus.find_by_id(bus_id) or Bus.find_by_device_id(device_id)
    if existing:
        return jsonify({"status": "error", "message": f"A bus with ID '{bus_id}' or Device ID '{device_id}' already exists"}), 409

    new_bus = Bus(
        bus_id=bus_id,
        bus_name=bus_name,
        bus_number=bus_number,
        device_id=device_id,
        route_id=data.get("route_id") or "ROUTE-01",
        route_name=data.get("route_name") or f"Auto-Route {bus_id}",
        driver_name=data.get("driver_name") or "Unassigned",
        driver_phone=data.get("driver_phone") or "N/A",
        capacity=int(data.get("capacity") or 50),
        campus=data.get("campus") or "Sphoorthy Campus Lead",
        is_active=True
    )
    saved = new_bus.save()

    return jsonify({
        "status": "success",
        "message": f"Bus {saved.bus_name} registered successfully",
        "bus": saved.to_dict()
    }), 201


@api_bp.route("/buses/<bus_id>", methods=["GET"])
def get_bus(bus_id):
    """Get single bus details and current location."""
    settings = db_instance.get_settings()
    threshold = int(settings.get("online_threshold_seconds", 30))
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)

    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    return jsonify({
        "status": "success",
        "bus": bus.to_dict(online_threshold_seconds=threshold)
    }), 200


@api_bp.route("/buses/<bus_id>/routes", methods=["GET"])
def get_bus_auto_routes(bus_id):
    """Get all auto-detected and learned routes for a specific bus."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    routes = db_instance.get_routes_by_bus(bus.bus_id)
    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_name": bus.bus_name,
        "count": len(routes),
        "routes": routes
    }), 200


@api_bp.route("/buses/<bus_id>/journeys", methods=["GET"])
def get_bus_journeys(bus_id):
    """Get completed distinct historical journeys for a specific bus."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    date_filter = request.args.get("date")
    journeys = db_instance.get_journeys(bus_id=bus.bus_id, date_filter=date_filter)

    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_name": bus.bus_name,
        "count": len(journeys),
        "journeys": journeys
    }), 200


@api_bp.route("/locations/save", methods=["GET", "POST"])
@api_bp.route("/location", methods=["GET", "POST"])
def save_location():
    """
    Main Hardware GPS Receiver API endpoint.
    Receives telemetry from ESP8266 NodeMCU, SIMCom A7670C, or simulator.
    """
    json_data = request.get_json(silent=True) or {}
    args = request.args
    form = request.form

    # Extract API Key
    apikey = (
        args.get("apikey")
        or args.get("apiKey")
        or args.get("api_key")
        or json_data.get("apikey")
        or json_data.get("apiKey")
        or json_data.get("api_key")
        or request.headers.get("X-API-KEY")
    )

    # Extract Device ID / Bus ID
    device_id_raw = (
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

    raw_speed = (
        args.get("speed")
        or json_data.get("speed")
        or form.get("speed")
    )

    raw_heading = (
        args.get("heading")
        or json_data.get("heading")
        or form.get("heading")
    )

    raw_accuracy = (
        args.get("accuracy")
        or args.get("hdop")
        or json_data.get("accuracy")
        or json_data.get("hdop")
    )

    raw_satellites = (
        args.get("satellites")
        or args.get("sats")
        or json_data.get("satellites")
    )

    raw_altitude = (
        args.get("altitude")
        or json_data.get("altitude")
    )

    raw_gps_status = (
        args.get("gps_status")
        or args.get("status")
        or json_data.get("gps_status")
        or json_data.get("status")
    )

    # 1. Validate API key
    settings = db_instance.get_settings()
    configured_api_key = current_app.config.get("API_KEY") or settings.get("api_key")
    if apikey:
        if apikey != configured_api_key:
            return jsonify({"success": False, "status": "error", "message": "Invalid API key"}), 401
    else:
        if not verify_device_auth():
            return jsonify({"success": False, "status": "error", "message": "Unauthorized device credentials"}), 401

    # 2. Validate deviceId / bus number
    if not device_id_raw or not isinstance(device_id_raw, str) or not device_id_raw.strip():
        return jsonify({"success": False, "status": "error", "message": "Missing deviceId (Bus Number)"}), 400

    device_id_clean = device_id_raw.strip()

    # 3. Validate coordinates
    if raw_lat is None or raw_lng is None:
        db_instance.update_device_health(device_id_clean, {"is_invalid": True, "error": "Missing coordinates"})
        return jsonify({"success": False, "status": "error", "message": "Latitude and longitude are required"}), 400

    try:
        latitude = float(raw_lat)
        longitude = float(raw_lng)
    except (ValueError, TypeError):
        db_instance.update_device_health(device_id_clean, {"is_invalid": True, "error": "Non-numeric coordinates"})
        return jsonify({"success": False, "status": "error", "message": "Latitude and longitude must be valid numeric floating point values"}), 400

    # Reject unacquired zero coordinates (0.0, 0.0)
    if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
        db_instance.update_device_health(device_id_clean, {
            "is_invalid": True,
            "gps_status": "no_fix",
            "error": "Zero coordinate GPS fix unacquired"
        })
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Invalid GPS coordinates: Zero latitude and longitude (No GPS Fix)"
        }), 400

    if not (-90.0 <= latitude <= 90.0):
        db_instance.update_device_health(device_id_clean, {"is_invalid": True, "error": "Latitude out of range"})
        return jsonify({"success": False, "status": "error", "message": "Latitude must be between -90 and 90 degrees"}), 400

    if not (-180.0 <= longitude <= 180.0):
        db_instance.update_device_health(device_id_clean, {"is_invalid": True, "error": "Longitude out of range"})
        return jsonify({"success": False, "status": "error", "message": "Longitude must be between -180 and 180 degrees"}), 400

    now = datetime.now(timezone.utc)

    # 4. Find or auto-associate Bus with Device ID
    bus = Bus.find_by_device_id(device_id_clean) or Bus.find_by_id(device_id_clean)
    if not bus:
        bus = Bus(
            bus_id=device_id_clean.upper(),
            bus_name=f"College Bus {device_id_clean.upper()}",
            bus_number=device_id_clean.upper(),
            device_id=device_id_clean.upper(),
            route_name=f"Route 01: Campus Main",
            route_id="ROUTE-01",
            driver_name="Unassigned",
            driver_phone="N/A",
            capacity=50,
            campus="Sphoorthy Campus Lead",
            is_active=True
        )
        bus.save()

    bus_id = bus.bus_id

    # 5. Parse and calculate Speed and Heading
    speed = None
    if raw_speed is not None:
        try:
            speed = float(raw_speed)
            if speed < 0:
                return jsonify({"success": False, "status": "error", "message": "Speed cannot be negative"}), 400
        except (ValueError, TypeError):
            speed = None

    heading = None
    if raw_heading is not None:
        try:
            heading = float(raw_heading) % 360.0
        except (ValueError, TypeError):
            heading = None

    prev_loc = db_instance.get_location(bus_id)
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

    satellites = 8
    if raw_satellites is not None:
        try:
            satellites = int(raw_satellites)
        except (ValueError, TypeError):
            satellites = 8

    accuracy = 1.5
    if raw_accuracy is not None:
        try:
            accuracy = float(raw_accuracy)
        except (ValueError, TypeError):
            accuracy = 1.5

    altitude = 500.0
    if raw_altitude is not None:
        try:
            altitude = float(raw_altitude)
        except (ValueError, TypeError):
            altitude = 500.0

    gps_status = "valid"
    if isinstance(raw_gps_status, str):
        if "invalid" in raw_gps_status.lower() or "nofix" in raw_gps_status.lower() or "no_fix" in raw_gps_status.lower():
            gps_status = "no_fix"

    # 6. Automatic Route Detection Processing
    db_instance.process_incoming_gps_point_for_auto_routes(
        bus_id=bus_id,
        lat=latitude,
        lng=longitude,
        speed=speed,
        now_dt=now
    )

    # 7. Bus Stop Geofencing Evaluation
    stops = db_instance.get_all_stops(route_id=bus.route_id) or db_instance.get_all_stops()
    geofence_status = None
    inside_stop = None

    for stop in stops:
        slat = float(stop.get("latitude", 0))
        slng = float(stop.get("longitude", 0))
        radius_m = float(stop.get("radius_m", settings.get("geofence_radius_meters", 75)))

        dist_m = haversine_distance_m(latitude, longitude, slat, slng)
        if dist_m <= radius_m:
            inside_stop = (stop, dist_m)
            break

    recent_events = db_instance.get_stop_events(bus_id=bus_id, limit=5)
    last_event = recent_events[-1] if recent_events else None

    if inside_stop:
        stop, dist_m = inside_stop
        geofence_status = {
            "in_stop": True,
            "stop_id": stop["id"],
            "stop_name": stop["name"],
            "distance_m": round(dist_m, 1)
        }
        if not last_event or last_event.get("event_type") != "ARRIVED" or last_event.get("stop_id") != stop["id"]:
            db_instance.record_stop_event({
                "bus_id": bus_id,
                "stop_id": stop["id"],
                "stop_name": stop["name"],
                "event_type": "ARRIVED",
                "timestamp": now.isoformat(),
                "dwell_seconds": 0
            })
    else:
        if last_event and last_event.get("event_type") == "ARRIVED":
            prev_stop = db_instance.get_stop(last_event.get("stop_id"))
            if prev_stop:
                prev_slat = float(prev_stop.get("latitude", 0))
                prev_slng = float(prev_stop.get("longitude", 0))
                prev_radius = float(prev_stop.get("radius_m", 75)) + 15.0
                dist_from_prev = haversine_distance_m(latitude, longitude, prev_slat, prev_slng)
                if dist_from_prev > prev_radius:
                    try:
                        arr_time = datetime.fromisoformat(last_event["timestamp"])
                        dwell_sec = max(0, int((now - arr_time).total_seconds()))
                    except Exception:
                        dwell_sec = 0

                    db_instance.record_stop_event({
                        "bus_id": bus_id,
                        "stop_id": prev_stop["id"],
                        "stop_name": prev_stop["name"],
                        "event_type": "DEPARTED",
                        "timestamp": now.isoformat(),
                        "dwell_seconds": dwell_sec
                    })

    # 8. Route Deviation Detection
    all_routes = db_instance.get_all_routes()
    assigned_route = db_instance.get_route(bus.route_id) or (all_routes[0] if all_routes else None)
    deviation_threshold_m = float(settings.get("deviation_threshold_meters", 150))
    is_deviating = False
    dist_from_route_m = 0.0

    if assigned_route and assigned_route.get("waypoints"):
        dist_from_route_m, _, _ = distance_to_route_polyline(latitude, longitude, assigned_route["waypoints"])
        if dist_from_route_m > deviation_threshold_m:
            is_deviating = True
            active_devs = db_instance.get_deviations(bus_id=bus_id, status="ACTIVE")
            if not active_devs:
                db_instance.record_deviation({
                    "bus_id": bus_id,
                    "route_name": assigned_route.get("route_name"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "max_deviation_m": dist_from_route_m,
                    "status": "ACTIVE"
                })
            else:
                for ad in active_devs:
                    if dist_from_route_m > ad.get("max_deviation_m", 0):
                        db_instance.update_deviation(ad["id"], {"max_deviation_m": dist_from_route_m})
        else:
            active_devs = db_instance.get_deviations(bus_id=bus_id, status="ACTIVE")
            for ad in active_devs:
                db_instance.update_deviation(ad["id"], {
                    "status": "RESOLVED",
                    "end_time": now.isoformat()
                })

    # 9. Update Database
    saved_location = db_instance.save_current_location(
        bus_id=bus_id,
        lat=latitude,
        lng=longitude,
        speed=speed,
        heading=heading,
        timestamp=now,
        satellites=satellites,
        accuracy=accuracy,
        altitude=altitude,
        gps_status=gps_status,
        device_id=bus.device_id
    )

    db_instance.add_location_history(
        bus_id=bus_id,
        lat=latitude,
        lng=longitude,
        speed=speed,
        heading=heading,
        timestamp=now,
        satellites=satellites,
        accuracy=accuracy,
        altitude=altitude,
        gps_status=gps_status,
        device_id=bus.device_id
    )

    # 10. Update Device Health Diagnostics
    db_instance.update_device_health(bus.device_id, {
        "bus_id": bus_id,
        "satellites": satellites,
        "accuracy": accuracy,
        "altitude": altitude,
        "gps_status": gps_status,
        "ip_address": request.remote_addr
    })

    return jsonify({
        "success": True,
        "status": "success",
        "message": "Location saved",
        "data": {
            "bus_no": bus_id,
            "deviceId": bus.device_id,
            "bus_id": bus_id,
            "bus_name": bus.bus_name,
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed,
            "heading": heading,
            "cardinal": bearing_to_cardinal(heading),
            "satellites": satellites,
            "accuracy": accuracy,
            "gps_status": gps_status,
            "date": saved_location["date"],
            "time": saved_location["time"],
            "timestamp": saved_location["timestamp"],
            "geofence": geofence_status,
            "deviation": {
                "is_deviating": is_deviating,
                "distance_from_route_m": round(dist_from_route_m, 1)
            }
        }
    }), 200


@api_bp.route("/buses/<bus_id>/history", methods=["GET"])
def get_bus_history(bus_id):
    """Get historical locations for a specific bus."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    date_filter = request.args.get("date", "all").strip()
    limit = request.args.get("limit", 500, type=int)

    history_result = db_instance.get_bus_history(bus.bus_id, date_filter=date_filter, limit=limit)

    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_name": bus.bus_name,
        "bus_number": bus.bus_number,
        "route_name": bus.route_name,
        "selected_date": date_filter,
        "available_dates": history_result["available_dates"],
        "count": history_result["total_count"],
        "trip_summary": history_result.get("trip_summary"),
        "history": history_result["records"]
    }), 200


@api_bp.route("/buses/<bus_id>/route-analysis", methods=["GET"])
def get_bus_route_analysis(bus_id):
    """Intelligent Route Analysis comparing live bus location with planned route geometry."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    curr_loc = db_instance.get_location(bus.bus_id)
    if not curr_loc:
        return jsonify({
            "status": "success",
            "message": "No live GPS coordinates available for this bus yet",
            "bus_id": bus.bus_id,
            "route_analysis": None
        }), 200

    all_routes = db_instance.get_all_routes()
    route = db_instance.get_route(bus.route_id) or (all_routes[0] if all_routes else None)
    route_id = route.get("id") if route else bus.route_id
    stops = db_instance.get_all_stops(route_id=route_id) or db_instance.get_all_stops()
    settings = db_instance.get_settings()
    deviation_threshold_m = float(settings.get("deviation_threshold_meters", 150))

    lat = float(curr_loc["latitude"])
    lng = float(curr_loc["longitude"])
    speed = float(curr_loc.get("speed", 0.0) or 0.0)

    dist_from_route_m, seg_idx, nearest_pt = distance_to_route_polyline(lat, lng, route.get("waypoints", []))
    is_deviating = dist_from_route_m > deviation_threshold_m

    progress = calculate_route_progress_and_eta(lat, lng, speed, route.get("waypoints", []), stops)
    active_deviations = db_instance.get_deviations(bus_id=bus.bus_id, status="ACTIVE")

    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_name": bus.bus_name,
        "bus_number": bus.bus_number,
        "route": {
            "id": route.get("id"),
            "route_name": route.get("route_name"),
            "origin": route.get("origin"),
            "destination": route.get("destination"),
            "waypoints": route.get("waypoints", [])
        },
        "analysis": {
            "current_location": curr_loc,
            "distance_from_route_m": round(dist_from_route_m, 1),
            "deviation_threshold_m": deviation_threshold_m,
            "is_deviating": is_deviating,
            "nearest_point_on_route": nearest_pt,
            "completed_distance_km": progress["completed_distance_km"],
            "remaining_distance_km": progress["remaining_distance_km"],
            "total_route_distance_km": progress["total_route_distance_km"],
            "progress_percent": progress["progress_percent"],
            "upcoming_stops": progress["upcoming_stops"],
            "active_deviations": active_deviations
        }
    }), 200


# -----------------------------------------------------------------------------
# ROUTES & BUS STOPS CRUD
# -----------------------------------------------------------------------------
@api_bp.route("/routes", methods=["GET"])
def get_routes():
    """List all predefined & auto-detected routes."""
    routes = db_instance.get_all_routes()
    return jsonify({"status": "success", "count": len(routes), "routes": routes}), 200


@api_bp.route("/routes/<route_id>", methods=["GET"])
def get_single_route(route_id):
    """Get single route details and geometry."""
    route = db_instance.get_route(route_id)
    if not route:
        return jsonify({"status": "error", "message": f"Route {route_id} not found"}), 404
    return jsonify({"status": "success", "route": route}), 200


@api_bp.route("/routes", methods=["POST"])
def create_route():
    """Create a new route."""
    data = request.get_json(silent=True) or {}
    new_route = db_instance.create_route(data)
    return jsonify({"status": "success", "message": "Route created", "route": new_route}), 201


@api_bp.route("/stops", methods=["GET"])
def get_stops():
    """List registered bus stops with geofence radiuses."""
    route_id = request.args.get("route_id")
    stops = db_instance.get_all_stops(route_id=route_id)
    return jsonify({"status": "success", "count": len(stops), "stops": stops}), 200


@api_bp.route("/stops", methods=["POST"])
def create_stop():
    """Add a new bus stop with geofence."""
    data = request.get_json(silent=True) or {}
    new_stop = db_instance.create_stop(data)
    return jsonify({"status": "success", "message": "Bus stop created", "stop": new_stop}), 201


@api_bp.route("/stops/events", methods=["GET"])
def get_stop_events():
    """List recorded bus stop arrival & departure logs."""
    bus_id = request.args.get("bus_id")
    date_filter = request.args.get("date")
    events = db_instance.get_stop_events(bus_id=bus_id, date_filter=date_filter)
    return jsonify({"status": "success", "count": len(events), "events": events}), 200


@api_bp.route("/deviations", methods=["GET"])
def get_deviations():
    """List route deviation records."""
    bus_id = request.args.get("bus_id")
    status = request.args.get("status")
    date_filter = request.args.get("date")
    devs = db_instance.get_deviations(bus_id=bus_id, status=status, date_filter=date_filter)
    return jsonify({"status": "success", "count": len(devs), "deviations": devs}), 200


# -----------------------------------------------------------------------------
# DEVICE HEALTH MONITORING
# -----------------------------------------------------------------------------
@api_bp.route("/devices/health", methods=["GET"])
def get_devices_health():
    """Return health diagnostic metrics for all GPS tracking devices."""
    devices = db_instance.get_device_health()
    settings = db_instance.get_settings()
    threshold = int(settings.get("online_threshold_seconds", 30))
    now = datetime.now(timezone.utc)

    health_list = []
    for dev_id, dev_data in devices.items():
        is_online = False
        last_seen = dev_data.get("last_seen")
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen)
                if (now - dt).total_seconds() <= threshold:
                    is_online = True
            except Exception:
                is_online = False

        dev_data_copy = dict(dev_data)
        dev_data_copy["is_online"] = is_online
        health_list.append(dev_data_copy)

    return jsonify({
        "status": "success",
        "count": len(health_list),
        "devices": health_list
    }), 200


@api_bp.route("/devices/health/<device_id>", methods=["GET"])
def get_single_device_health(device_id):
    """Return health diagnostic metrics for a single GPS device."""
    device = db_instance.get_device_health(device_id)
    if not device:
        return jsonify({"status": "error", "message": f"Device {device_id} not found"}), 404
    return jsonify(device), 200


# -----------------------------------------------------------------------------
# SETTINGS API
# -----------------------------------------------------------------------------
@api_bp.route("/settings", methods=["GET"])
def get_settings():
    """Get system configuration settings."""
    settings = db_instance.get_settings()
    return jsonify({"status": "success", "settings": settings}), 200


@api_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Update system configuration settings."""
    data = request.get_json(silent=True) or {}
    updated = db_instance.update_settings(data)
    return jsonify({"status": "success", "message": "Settings updated", "settings": updated}), 200


# -----------------------------------------------------------------------------
# REPORTS & DATA EXPORT
# -----------------------------------------------------------------------------
@api_bp.route("/reports/summary", methods=["GET"])
def get_reports_summary():
    """Fleet journey summary metrics for a date range."""
    date_filter = request.args.get("date", "today").strip()
    bus_id = request.args.get("bus_id")

    buses = Bus.get_all(active_only=True)
    if bus_id:
        buses = [b for b in buses if b.bus_id.upper() == bus_id.upper() or b.device_id.lower() == bus_id.lower()]

    report_items = []
    for b in buses:
        hist = db_instance.get_bus_history(b.bus_id, date_filter=date_filter, limit=1000)
        summary = hist.get("trip_summary", {})
        devs = db_instance.get_deviations(bus_id=b.bus_id)

        report_items.append({
            "bus_id": b.bus_id,
            "bus_name": b.bus_name,
            "bus_number": b.bus_number,
            "device_id": b.device_id,
            "route_name": b.route_name,
            "date": date_filter,
            "total_distance_km": summary.get("total_distance_km", 0.0),
            "average_speed_kmh": summary.get("average_speed", 0.0),
            "max_speed_kmh": summary.get("max_speed", 0.0),
            "stoppage_time_minutes": summary.get("stoppage_time_minutes", 0),
            "stops_count": summary.get("stops_count", 0),
            "deviations_count": len(devs),
            "start_time": summary.get("start_time"),
            "end_time": summary.get("end_time"),
            "records_count": summary.get("records_count", 0)
        })

    return jsonify({
        "status": "success",
        "date": date_filter,
        "count": len(report_items),
        "reports": report_items
    }), 200


@api_bp.route("/reports/export", methods=["GET"])
def export_reports_csv():
    """Generate and download journey report in CSV format."""
    bus_id = request.args.get("bus_id", "").strip().upper()
    date_filter = request.args.get("date", "all").strip()

    if not bus_id:
        buses = Bus.get_all(active_only=True)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Bus ID", "Bus Number", "Route Name", "Date",
            "Bus Name", "ESP Device ID",
            "Total Distance (km)", "Avg Speed (km/h)", "Max Speed (km/h)",
            "Stoppage Time (min)", "Stops Count", "Deviations"
        ])

        for b in buses:
            hist = db_instance.get_bus_history(b.bus_id, date_filter=date_filter, limit=1000)
            summary = hist.get("trip_summary", {})
            devs = db_instance.get_deviations(bus_id=b.bus_id)
            writer.writerow([
                b.bus_id, b.bus_number, b.route_name, date_filter,
                b.bus_name, b.device_id,
                summary.get("total_distance_km", 0.0),
                summary.get("average_speed", 0.0),
                summary.get("max_speed", 0.0),
                summary.get("stoppage_time_minutes", 0),
                summary.get("stops_count", 0),
                len(devs)
            ])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=campusfleet_report_{date_filter}.csv"}
        )

    # Detailed export for a single bus
    hist = db_instance.get_bus_history(bus_id, date_filter=date_filter, limit=5000)
    records = hist.get("records", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "Bus ID", "Date", "Time", "Timestamp",
        "Latitude", "Longitude", "ESP Device ID", "Speed (km/h)", "Heading (deg)",
        "Satellites", "Accuracy (m)", "Altitude (m)", "Status"
    ])

    for r in records:
        writer.writerow([
            r.get("id"),
            r.get("bus_id"),
            r.get("date"),
            r.get("time"),
            r.get("timestamp"),
            r.get("latitude"),
            r.get("longitude"),
            r.get("device_id", bus_id),
            r.get("speed"),
            r.get("heading"),
            r.get("satellites", 8),
            r.get("accuracy", 1.5),
            r.get("altitude", 500),
            r.get("gps_status", "valid")
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=bus_{bus_id}_{date_filter}_gps_logs.csv"}
    )


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
    return register_bus()


@api_bp.route("/admin/buses/<bus_id>", methods=["PUT"])
def update_bus_admin(bus_id):
    """Update bus details in JSON database."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    data = request.get_json(silent=True) or {}
    updated = db_instance.update_bus(bus.bus_id, data)

    return jsonify({
        "status": "success",
        "message": f"Bus {bus_id} updated successfully",
        "bus": Bus(**updated).to_dict() if updated else bus.to_dict()
    }), 200


@api_bp.route("/admin/buses/<bus_id>", methods=["DELETE"])
def delete_bus_admin(bus_id):
    """Delete a bus from JSON database."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus {bus_id} not found"}), 404

    success = db_instance.delete_bus(bus.bus_id)
    return jsonify({"status": "success", "message": f"Bus {bus.bus_id} deleted successfully"}), 200
