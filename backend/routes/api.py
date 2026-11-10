import io
import csv
import math
import json
import functools
import urllib.request
import urllib.parse
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

# Predefined Hyderabad & Campus Transit Landmark Geocoding Dictionary
LOCAL_LANDMARKS = [
    {"name": "Sphoorthy Engineering College", "display_name": "Sphoorthy Engineering College, Sagar Road, Nadargul, Hyderabad", "latitude": 17.3156, "longitude": 78.5833},
    {"name": "Koti Central Bus Station", "display_name": "Koti Central Bus Terminal, Hyderabad, Telangana", "latitude": 17.385044, "longitude": 78.486671},
    {"name": "Abids GPO Circle", "display_name": "Abids GPO Circle, Hyderabad, Telangana", "latitude": 17.391200, "longitude": 78.474500},
    {"name": "Lakdi-ka-pul Junction", "display_name": "Lakdi-ka-pul Junction & Metro, Hyderabad, Telangana", "latitude": 17.402100, "longitude": 78.461000},
    {"name": "Punjagutta Circle", "display_name": "Punjagutta Circle, Nagarjuna Hills, Hyderabad, Telangana", "latitude": 17.425500, "longitude": 78.451200},
    {"name": "Secunderabad Railway Station", "display_name": "Secunderabad Junction & Bus Stand, Telangana", "latitude": 17.439930, "longitude": 78.498274},
    {"name": "Paradise Circle", "display_name": "Paradise Circle, MG Road, Secunderabad, Telangana", "latitude": 17.443500, "longitude": 78.487000},
    {"name": "Begumpet Airport Road", "display_name": "Begumpet Airport Road, Hyderabad, Telangana", "latitude": 17.441100, "longitude": 78.471200},
    {"name": "LB Nagar Metro Station", "display_name": "LB Nagar Ring Road & Metro Station, Hyderabad, Telangana", "latitude": 17.345719, "longitude": 78.552230},
    {"name": "Dilsukhnagar Bus Complex", "display_name": "Dilsukhnagar Bus Depot & Complex, Hyderabad, Telangana", "latitude": 17.368800, "longitude": 78.524500},
    {"name": "Malakpet Terminal", "display_name": "Malakpet Gunj & Bus Station, Hyderabad, Telangana", "latitude": 17.375500, "longitude": 78.498000},
    {"name": "Uppal Ring Road", "display_name": "Uppal Ring Road & Metro Junction, Hyderabad, Telangana", "latitude": 17.398400, "longitude": 78.558300},
    {"name": "Charminar Monument", "display_name": "Charminar Old City, Hyderabad, Telangana", "latitude": 17.361600, "longitude": 78.474700},
    {"name": "Mehdipatnam Depot", "display_name": "Mehdipatnam Bus Station & Junction, Hyderabad, Telangana", "latitude": 17.391600, "longitude": 78.439800},
    {"name": "Ameerpet Metro Hub", "display_name": "Ameerpet Junction & Interchange Station, Hyderabad, Telangana", "latitude": 17.437500, "longitude": 78.448300},
    {"name": "Kukatpally Y Junction", "display_name": "Kukatpally Housing Board & Y Junction, Hyderabad, Telangana", "latitude": 17.493800, "longitude": 78.399500},
    {"name": "Miyapur Metro Terminal", "display_name": "Miyapur Allwyn Junction & Metro Terminal, Hyderabad", "latitude": 17.496800, "longitude": 78.361400},
    {"name": "Hitec City Cyber Towers", "display_name": "Cyber Towers, Hitec City, Madhapur, Hyderabad", "latitude": 17.450400, "longitude": 78.380800},
    {"name": "Gachibowli Stadium", "display_name": "Gachibowli ORR Junction & Stadium, Hyderabad", "latitude": 17.440100, "longitude": 78.348900},
    {"name": "Main Campus Gate 1", "display_name": "Sphoorthy Main Campus Gate 1, Sagar Highway, Hyderabad", "latitude": 17.316200, "longitude": 78.584100}
]


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
    """Verify admin session, token, or local dashboard operator."""
    user = session.get("user")
    if user and user.get("role") == "ADMIN":
        return True
    if session.get("is_admin"):
        return True

    auth = request.authorization
    if auth and auth.username == current_app.config.get("ADMIN_USERNAME") and auth.password == current_app.config.get("ADMIN_PASSWORD"):
        return True

    admin_header_user = request.headers.get("X-Admin-User")
    admin_header_pass = request.headers.get("X-Admin-Pass")
    if admin_header_user == current_app.config.get("ADMIN_USERNAME") and admin_header_pass == current_app.config.get("ADMIN_PASSWORD"):
        return True

    # Allow local dashboard operator or test client
    if request.remote_addr in ("127.0.0.1", "::1", "localhost", None) or current_app.config.get("TESTING"):
        return True

    return False


def admin_required(fn):
    """Decorator to enforce administrator authentication and role-based access control."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if verify_admin_auth():
            return fn(*args, **kwargs)
        return jsonify({
            "status": "error",
            "message": "Access denied. Administrator privileges required."
        }), 403
    return wrapper


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


@api_bp.route("/devices", methods=["GET"])
def get_devices():
    """List all registered ESP hardware devices with live connection statuses and assigned buses."""
    devices = db_instance.get_all_devices(compute_status=True)
    online_count = sum(1 for d in devices if d.get("is_online"))
    connecting_count = sum(1 for d in devices if d.get("status") == "connecting")
    offline_count = sum(1 for d in devices if d.get("status") == "offline")
    unassigned_count = sum(1 for d in devices if not d.get("assigned_bus_id"))

    return jsonify({
        "status": "success",
        "count": len(devices),
        "metrics": {
            "total_devices": len(devices),
            "online_devices": online_count,
            "connecting_devices": connecting_count,
            "offline_devices": offline_count,
            "unassigned_devices": unassigned_count
        },
        "devices": devices
    }), 200


@api_bp.route("/devices", methods=["POST"])
def register_device():
    """Register a new ESP hardware device."""
    data = request.get_json(silent=True) or {}
    dev_id = (data.get("device_id") or "").strip()
    if not dev_id:
        return jsonify({"status": "error", "message": "device_id is required"}), 400

    try:
        new_dev = db_instance.register_device(data)
        return jsonify({
            "status": "success",
            "message": f"Device '{new_dev['device_id']}' registered successfully",
            "device": new_dev
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/devices/<device_id>/assign", methods=["PUT", "POST"])
def assign_device(device_id):
    """Assign or reassign an ESP device to a specific bus."""
    data = request.get_json(silent=True) or {}
    bus_id = data.get("bus_id")

    try:
        updated_dev = db_instance.assign_device_to_bus(device_id, bus_id)
        return jsonify({
            "status": "success",
            "message": f"Device '{device_id}' assigned to '{bus_id or 'Unassigned'}'",
            "device": updated_dev
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/devices/<device_id>", methods=["DELETE"])
def delete_device(device_id):
    """Delete an ESP device."""
    success = db_instance.delete_device(device_id)
    if not success:
        return jsonify({"status": "error", "message": f"Device '{device_id}' not found"}), 404
    return jsonify({
        "status": "success",
        "message": f"Device '{device_id}' deleted successfully"
    }), 200


@api_bp.route("/devices/<device_id>", methods=["PUT"])
def update_device_info(device_id):
    """Update device metadata (device_name, device_type, mac_address, firmware_version)."""
    data = request.get_json(silent=True) or {}
    try:
        updated = db_instance.update_device(device_id, data)
        if not updated:
            return jsonify({"status": "error", "message": f"Device '{device_id}' not found"}), 404
        return jsonify({
            "status": "success",
            "message": f"Device '{device_id}' updated successfully",
            "device": updated
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


SUPPORTED_DEVICE_TYPES = [
    {
        "type": "ESP8266",
        "name": "ESP8266 NodeMCU / D1 Mini",
        "category": "Wi-Fi Microcontroller",
        "baud_rate": 9600,
        "default_gps_rx": "D2 (GPIO4)",
        "default_gps_tx": "D1 (GPIO5)",
        "protocol": "UDIP v1.0 (HTTP/HTTPS)"
    },
    {
        "type": "ESP32",
        "name": "ESP32 DevKit / WROOM / S3",
        "category": "Dual-Core Wi-Fi / Bluetooth Microcontroller",
        "baud_rate": 9600,
        "default_gps_rx": "GPIO16 (RX2)",
        "default_gps_tx": "GPIO17 (TX2)",
        "protocol": "UDIP v1.0 (HTTP/HTTPS)"
    },
    {
        "type": "ARDUINO_CELLULAR",
        "name": "Arduino + 4G LTE Modem (A7670C / SIM7600)",
        "category": "Cellular IoT",
        "baud_rate": 9600,
        "default_gps_rx": "Pin 10 / AT GNSS",
        "default_gps_tx": "Pin 11 / AT GNSS",
        "protocol": "UDIP v1.0 (HTTP GET/POST)"
    },
    {
        "type": "ARDUINO_AVR",
        "name": "Arduino Uno / Mega / Nano + GPS Shield",
        "category": "AVR Microcontroller",
        "baud_rate": 9600,
        "default_gps_rx": "Pin 4",
        "default_gps_tx": "Pin 3",
        "protocol": "UDIP v1.0 (Lightweight Query String)"
    },
    {
        "type": "STM32",
        "name": "STM32 ARM Cortex-M + Wi-Fi/Cellular",
        "category": "32-Bit ARM Microcontroller",
        "baud_rate": 9600,
        "default_gps_rx": "PA3 (USART2 RX)",
        "default_gps_tx": "PA2 (USART2 TX)",
        "protocol": "UDIP v1.0 (HTTP/HTTPS)"
    },
    {
        "type": "RPI_PICO",
        "name": "Raspberry Pi Pico W",
        "category": "RP2040 Wi-Fi Microcontroller",
        "baud_rate": 9600,
        "default_gps_rx": "GP1 (UART0 RX)",
        "default_gps_tx": "GP0 (UART0 TX)",
        "protocol": "UDIP v1.0 (HTTP/HTTPS)"
    },
    {
        "type": "OTHER",
        "name": "Generic Hardware Tracker / Telemetry Gateway",
        "category": "Custom Telemetry Terminal",
        "baud_rate": 9600,
        "default_gps_rx": "UART RX",
        "default_gps_tx": "UART TX",
        "protocol": "UDIP v1.0"
    }
]


@api_bp.route("/devices/types", methods=["GET"])
def get_supported_device_types():
    """List all supported hardware microcontroller platforms and pinout presets."""
    return jsonify({
        "status": "success",
        "count": len(SUPPORTED_DEVICE_TYPES),
        "types": SUPPORTED_DEVICE_TYPES
    }), 200


@api_bp.route("/devices/provision", methods=["POST"])
def provision_device():
    """
    Universal Device Provisioning & Handshake Endpoint (UDIP v1.0).
    Allows any supported hardware microcontroller to self-announce, authenticate,
    and receive its configuration, device token, and assigned bus mapping.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    dev_id = str(data.get("device_id") or data.get("deviceId") or "").strip().upper()
    mac = str(data.get("mac_address") or data.get("mac") or "").strip().upper()
    dev_type = str(data.get("device_type") or data.get("deviceType") or "ESP8266").strip().upper()
    dev_name = str(data.get("device_name") or data.get("deviceName") or "").strip()
    firmware = str(data.get("firmware_version") or data.get("firmwareVersion") or "3.2.0").strip()

    api_key = (
        data.get("api_key")
        or data.get("apiKey")
        or request.headers.get("X-API-KEY")
        or request.args.get("apiKey")
        or request.args.get("api_key")
    )

    settings = db_instance.get_settings()
    configured_key = current_app.config.get("API_KEY") or settings.get("api_key")

    if not dev_id:
        if mac and mac != "UNKNOWN":
            dev_id = f"{dev_type}-{mac.replace(':', '')[-6:]}"
        else:
            return jsonify({"status": "error", "message": "device_id or mac_address is required"}), 400

    # Authenticate provisioning request against fleet API key
    if api_key and api_key != configured_key:
        return jsonify({"status": "error", "message": "Invalid fleet API key for provisioning"}), 401

    # Check if already registered
    existing = db_instance.get_device(dev_id) or (db_instance.get_device_by_mac(mac) if mac else None)
    if not existing:
        dev = db_instance.auto_discover_device(
            device_id=dev_id,
            mac=mac or None,
            device_type=dev_type,
            device_name=dev_name or f"{dev_type} Tracker ({dev_id})",
            firmware_version=firmware,
            ip_address=request.remote_addr
        )
        status_code = 201
    else:
        dev = existing
        update_data = {}
        if dev_name:
            update_data["device_name"] = dev_name
        if dev_type:
            update_data["device_type"] = dev_type
        if firmware:
            update_data["firmware_version"] = firmware
        if update_data:
            dev = db_instance.update_device(dev.get("device_id"), update_data) or dev
        status_code = 200

    assigned_bus_id = dev.get("assigned_bus_id")
    bus_number_req = str(data.get("bus_number") or data.get("bus_id") or data.get("busNumber") or "").strip().upper()
    if bus_number_req and not assigned_bus_id:
        target_bus = Bus.find_by_id(bus_number_req) or Bus.find_by_device_id(bus_number_req)
        if not target_bus:
            for b in Bus.get_all(active_only=False):
                if b.bus_number.strip().upper() == bus_number_req:
                    target_bus = b
                    break
        if not target_bus:
            target_bus = Bus(
                bus_id=bus_number_req,
                bus_name=f"College Bus {bus_number_req}",
                bus_number=bus_number_req,
                device_id=dev.get("device_id"),
                route_id="ROUTE-01",
                route_name="Route 01: Campus Main",
                driver_name="Unassigned",
                driver_phone="N/A",
                capacity=50,
                campus="Sphoorthy Campus Lead",
                is_active=True
            )
            target_bus.save()

        if target_bus:
            db_instance.assign_device_to_bus(dev.get("device_id"), target_bus.bus_id)
            assigned_bus_id = target_bus.bus_id
            dev["assigned_bus_id"] = assigned_bus_id

    bus_info = None
    if assigned_bus_id:
        b = Bus.find_by_id(assigned_bus_id)
        if b:
            bus_info = {
                "bus_id": b.bus_id,
                "bus_name": b.bus_name,
                "bus_number": b.bus_number,
                "route_name": b.route_name
            }

    return jsonify({
        "status": "success",
        "message": "Device provisioned successfully",
        "device": {
            "device_id": dev.get("device_id"),
            "device_name": dev.get("device_name"),
            "mac_address": dev.get("mac_address"),
            "device_type": dev.get("device_type"),
            "device_token": dev.get("device_token"),
            "firmware_version": dev.get("firmware_version"),
            "assigned_bus_id": assigned_bus_id,
            "auto_discovered": dev.get("auto_discovered", False),
            "assigned_bus": bus_info
        },
        "configuration": {
            "report_interval_seconds": 5,
            "offline_threshold_seconds": int(settings.get("online_threshold_seconds", 30)),
            "geofence_radius_meters": int(settings.get("geofence_radius_meters", 75)),
            "protocol_version": "UDIP/1.0",
            "server_time": datetime.now(timezone.utc).isoformat()
        }
    }), status_code


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

    # Enrich each bus with distance metrics & college arrival status
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%d-%m-%Y")

    for b in all_buses_dict:
        loc = b.get("current_location") or {}
        is_reached = bool(loc.get("is_at_college") or loc.get("status") == "REACHED_COLLEGE")
        b["is_reached_college"] = is_reached
        if is_reached:
            b["current_route_status"] = "Reached College"

        # Attach 3 distinct distance calculations (A. Trip Distance, B. Daily Distance, C. 7-Day History)
        b["distance_metrics"] = db_instance.get_bus_distance_metrics(b["bus_id"])

    # Global metrics
    total_count = len(all_buses_dict)
    active_count = sum(1 for b in all_buses_dict if b.get("is_online"))
    offline_count = total_count - active_count
    moving_count = sum(1 for b in all_buses_dict if b.get("is_moving"))
    stopped_count = sum(1 for b in all_buses_dict if b.get("is_stopped"))
    gps_issue_count = sum(1 for b in all_buses_dict if b.get("connection_status") == "gps_unavailable")
    sending_gps_count = sum(1 for b in all_buses_dict if b.get("is_online") and not b.get("has_gps_issue"))

    running_buses_count = sum(1 for b in all_buses_dict if (b.get("is_moving") or (b.get("is_online") and not b.get("is_reached_college"))))
    reached_college_count = sum(1 for b in all_buses_dict if b.get("is_reached_college"))

    devices_list = db_instance.get_all_devices(compute_status=True)
    offline_devices_count = sum(1 for d in devices_list if not d.get("is_online"))

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
    total_distance_today_km = round(sum(b.get("distance_metrics", {}).get("daily_distance_km", 0.0) for b in all_buses_dict), 2)

    # Today's completed trips across fleet
    today_all_trips = db_instance.get_all_trips(date_filter=today_str)
    completed_trips_today = sum(1 for t in today_all_trips if t.get("status") == "COMPLETED")

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
    elif status_filter == "running":
        bus_list = [b for b in bus_list if b.get("is_moving") or (b.get("is_online") and not b.get("is_reached_college"))]
    elif status_filter in ("reached_college", "college"):
        bus_list = [b for b in bus_list if b.get("is_reached_college")]
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
            "running_buses": running_buses_count,
            "reached_college_buses": reached_college_count,
            "offline_devices": offline_devices_count,
            "total_devices": len(devices_list),
            "completed_trips_today": completed_trips_today,
            "gps_unavailable_buses": gps_issue_count,
            "total_routes_detected": total_routes_detected,
            "avg_fleet_speed": avg_fleet_speed,
            "total_distance_today_km": total_distance_today_km,
            "active_deviations": active_deviations_count,
            "last_update": last_update_ts,
        },
        "routes": unique_routes,
        "count": len(bus_list),
        "buses": bus_list
    }), 200


@api_bp.route("/buses", methods=["POST"])
def register_bus():
    """
    Create and register a new bus with its ESP device ID.
    Requirements:
    - Bus Name (Required)
    - Bus ID (Unique identifier)
    - License Number (Required)
    - ESP Device ID (Unique hardware identifier, validated)
    - Driver Name (Required)
    - Driver Phone Number (Required)
    - Assigned Route (Selectable)
    - College Destination (Defaults to configured college)
    - Campus group is NOT required.
    """
    data = request.get_json(silent=True) or {}
    raw_bus_id = data.get("bus_id") or data.get("bus_number") or ""
    bus_id = str(raw_bus_id).strip().upper()
    bus_number = str(data.get("bus_number") or bus_id).strip().upper()
    bus_name = str(data.get("bus_name") or f"Bus {bus_id}").strip()
    device_id = str(data.get("device_id") or bus_id).strip().upper()
    driver_name = str(data.get("driver_name") or "Unassigned").strip()
    driver_phone = str(data.get("driver_phone") or "N/A").strip()
    route_id = str(data.get("route_id") or "AUTOROUTE-01").strip()
    route_name = data.get("route_name")

    if not bus_id:
        return jsonify({"status": "error", "message": "Bus ID is required"}), 400
    if not bus_number:
        return jsonify({"status": "error", "message": "License Number is required"}), 400
    if not bus_name:
        return jsonify({"status": "error", "message": "Bus Name is required"}), 400
    if not device_id:
        return jsonify({"status": "error", "message": "ESP Device ID is required"}), 400

    existing_bus = Bus.find_by_id(bus_id)
    if existing_bus:
        return jsonify({"status": "error", "message": f"A bus with ID '{bus_id}' already exists"}), 409

    # Prevent duplicate device mapping: check if device is assigned to another bus
    dev = db_instance.get_device(device_id)
    if dev and dev.get("assigned_bus_id") and dev.get("assigned_bus_id").upper() != bus_id:
        return jsonify({
            "status": "error",
            "message": f"Hardware Device ID '{device_id}' is already assigned to bus '{dev.get('assigned_bus_id')}'"
        }), 409

    # Resolve Route Name
    if not route_name:
        route_obj = db_instance.get_route(route_id)
        route_name = route_obj.get("route_name") if route_obj else f"Route {route_id}"

    # College Destination
    college = db_instance.get_college_config()
    college_dest = data.get("college_destination") or college.get("college_name")

    new_bus = Bus(
        bus_id=bus_id,
        bus_name=bus_name,
        bus_number=bus_number,
        device_id=device_id,
        route_id=route_id,
        route_name=route_name,
        driver_name=driver_name,
        driver_phone=driver_phone,
        capacity=int(data.get("capacity") or 50),
        campus=college_dest,
        is_active=True
    )
    saved = new_bus.save()

    # Automatically map device to bus in devices.json
    if dev:
        db_instance.assign_device_to_bus(device_id, bus_id)
    else:
        # Register new universal tracker and assign to this bus
        db_instance.auto_discover_device(
            device_id=device_id,
            device_name=f"{bus_name} Tracker",
            device_type=data.get("device_type", "ESP8266")
        )
        db_instance.assign_device_to_bus(device_id, bus_id)

    # Record Audit Log
    current_username = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=current_username,
        role="ADMIN",
        action="BUS_REGISTER",
        target_type="BUS",
        target_id=bus_id,
        details=f"Registered bus {bus_name} ({bus_number}) mapped to ESP device {device_id} on route {route_name}",
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": f"Bus {saved.bus_name} registered successfully and mapped to device {device_id}",
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


@api_bp.route("/devices/telemetry", methods=["GET", "POST"])
@api_bp.route("/locations/save", methods=["GET", "POST"])
@api_bp.route("/location", methods=["GET", "POST"])
@api_bp.route("/telemetry/gps", methods=["GET", "POST"])
@api_bp.route("/update", methods=["GET", "POST"])
def save_location():
    """
    Universal Device Telemetry Receiver & GPS Ingestion API endpoint (UDIP v1.0).
    Receives telemetry from ESP8266 NodeMCU, ESP32, SIMCom A7670C, Arduino AVR,
    Raspberry Pi Pico W, STM32, or test simulator.
    """
    json_data = request.get_json(silent=True) or {}
    args = request.args
    form = request.form

    # Extract API Key or Device Token
    apikey = (
        args.get("apikey")
        or args.get("apiKey")
        or args.get("api_key")
        or json_data.get("apikey")
        or json_data.get("apiKey")
        or json_data.get("api_key")
        or request.headers.get("X-API-KEY")
    )

    device_token = (
        args.get("device_token")
        or args.get("deviceToken")
        or args.get("token")
        or json_data.get("device_token")
        or json_data.get("deviceToken")
        or json_data.get("token")
        or request.headers.get("X-Device-Token")
    )

    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else None

    credential = apikey or device_token or bearer_token

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

    # 1. Validate deviceId / bus number
    if not device_id_raw or not isinstance(device_id_raw, str) or not device_id_raw.strip():
        return jsonify({"success": False, "status": "error", "message": "Missing deviceId (Bus Number)"}), 400

    device_id_clean = device_id_raw.strip()

    # 2. Validate Authentication Credentials (Fleet API Key or Per-Device Token)
    settings = db_instance.get_settings()
    configured_api_key = current_app.config.get("API_KEY") or settings.get("api_key")

    is_authorized = False
    if credential:
        if credential == configured_api_key:
            is_authorized = True
        elif db_instance.verify_device_credentials(device_id_clean, credential):
            is_authorized = True
    else:
        dev = db_instance.get_device(device_id_clean)
        bus = db_instance.get_bus(device_id_clean) or db_instance.get_bus_by_device(device_id_clean)
        if dev or bus or verify_device_auth():
            is_authorized = True

    if not is_authorized:
        return jsonify({"success": False, "status": "error", "message": "Invalid or unauthorized device credentials"}), 401

    raw_lat = (
        args.get("latitude")
        or args.get("lat")
        or json_data.get("latitude")
        or json_data.get("lat")
        or form.get("latitude")
    )

    raw_lng = (
        args.get("longitude")
        or args.get("lng")
        or args.get("lon")
        or json_data.get("longitude")
        or json_data.get("lng")
        or json_data.get("lon")
        or form.get("longitude")
    )

    raw_speed = (
        args.get("speed")
        or args.get("speed_kmh")
        or json_data.get("speed")
        or json_data.get("speed_kmh")
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

    raw_mac = (
        args.get("mac")
        or args.get("mac_address")
        or json_data.get("mac")
        or json_data.get("mac_address")
        or form.get("mac")
    )

    raw_device_type = (
        args.get("device_type")
        or args.get("deviceType")
        or json_data.get("device_type")
        or json_data.get("deviceType")
        or form.get("device_type")
        or "ESP8266"
    )

    raw_device_name = (
        args.get("deviceName")
        or args.get("device_name")
        or json_data.get("deviceName")
        or json_data.get("device_name")
    )

    raw_firmware_version = (
        args.get("firmwareVersion")
        or args.get("firmware_version")
        or json_data.get("firmwareVersion")
        or json_data.get("firmware_version")
    )

    raw_wifi_rssi = (
        args.get("wifi_rssi")
        or args.get("rssi")
        or json_data.get("wifi_rssi")
        or json_data.get("rssi")
    )

    raw_battery_mv = (
        args.get("battery_mv")
        or args.get("battery")
        or args.get("vbat")
        or json_data.get("battery_mv")
        or json_data.get("battery")
        or json_data.get("vbat")
    )

    raw_uptime = (
        args.get("uptime_seconds")
        or args.get("uptime")
        or json_data.get("uptime_seconds")
        or json_data.get("uptime")
    )

    wifi_rssi = None
    if raw_wifi_rssi is not None:
        try:
            wifi_rssi = int(raw_wifi_rssi)
        except (ValueError, TypeError):
            wifi_rssi = None

    battery_mv = None
    if raw_battery_mv is not None:
        try:
            battery_mv = int(raw_battery_mv)
        except (ValueError, TypeError):
            battery_mv = None

    uptime_seconds = None
    if raw_uptime is not None:
        try:
            uptime_seconds = int(raw_uptime)
        except (ValueError, TypeError):
            uptime_seconds = None

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
    matched_dev = None
    all_devs = db_instance.get_all_devices(compute_status=False)
    for d in all_devs:
        d_id = str(d.get("device_id", "")).strip().upper()
        d_mac = str(d.get("mac_address", "")).strip().upper()
        if d_id == device_id_clean.upper() or (raw_mac and d_mac == str(raw_mac).strip().upper()):
            matched_dev = d
            break

    # If device was explicitly registered or auto-discovered as unassigned:
    raw_bus_number = (
        args.get("bus_number")
        or args.get("bus_no")
        or args.get("busNumber")
        or json_data.get("bus_number")
        or json_data.get("bus_no")
        or json_data.get("busNumber")
    )
    if matched_dev and matched_dev.get("is_registered") and not matched_dev.get("assigned_bus_id"):
        if raw_bus_number and str(raw_bus_number).strip():
            b_num = str(raw_bus_number).strip().upper()
            target_bus = Bus.find_by_id(b_num) or Bus.find_by_device_id(b_num)
            if not target_bus:
                for b in Bus.get_all(active_only=False):
                    if b.bus_number.strip().upper() == b_num:
                        target_bus = b
                        break
            if not target_bus:
                target_bus = Bus(
                    bus_id=b_num,
                    bus_name=f"College Bus {b_num}",
                    bus_number=b_num,
                    device_id=matched_dev.get("device_id"),
                    route_id="ROUTE-01",
                    route_name="Route 01: Campus Main",
                    driver_name="Unassigned",
                    driver_phone="N/A",
                    capacity=50,
                    campus="Sphoorthy Campus Lead",
                    is_active=True
                )
                target_bus.save()

            db_instance.assign_device_to_bus(matched_dev.get("device_id"), target_bus.bus_id)
            matched_dev["assigned_bus_id"] = target_bus.bus_id
        else:
            db_instance.touch_device_seen(
                device_id=device_id_clean,
                mac=raw_mac,
                device_type=raw_device_type,
                ip_address=request.remote_addr,
                gps_status=raw_gps_status or "valid",
                device_name=raw_device_name,
                firmware_version=raw_firmware_version,
                wifi_rssi=wifi_rssi,
                battery_mv=battery_mv,
                uptime_seconds=uptime_seconds
            )
            db_instance.update_device_health(device_id_clean, {
                "bus_id": None,
                "satellites": int(raw_satellites) if raw_satellites is not None else 8,
                "accuracy": float(raw_accuracy) if raw_accuracy is not None else 1.5,
                "altitude": float(raw_altitude) if raw_altitude is not None else 500.0,
                "gps_status": raw_gps_status or "valid",
                "ip_address": request.remote_addr,
                "latitude": latitude,
                "longitude": longitude
            })
            return jsonify({
                "success": True,
                "status": "unassigned",
                "message": f"Device '{device_id_clean}' is unassigned. Please map it to a bus in Device Management.",
                "data": {
                    "deviceId": device_id_clean,
                    "mac": raw_mac,
                    "status": "unassigned",
                    "gps_status": raw_gps_status or "valid"
                }
            }), 200

    # Look up bus: 1) from matched device's assigned_bus_id, 2) by device_id or mac, 3) by bus_id
    bus = None
    if matched_dev and matched_dev.get("assigned_bus_id"):
        bus = Bus.find_by_id(matched_dev["assigned_bus_id"])

    if not bus:
        bus = Bus.find_by_device_id(device_id_clean) or Bus.find_by_id(device_id_clean)
        if not bus and raw_mac:
            bus = Bus.find_by_device_id(raw_mac)

    if not bus:
        # Check if request came to /devices/telemetry or requested auto-discovery
        is_telemetry_endpoint = request.path.endswith("/telemetry")
        auto_disc_param = args.get("auto_discover") or json_data.get("auto_discover")

        if is_telemetry_endpoint or auto_disc_param:
            new_dev = db_instance.auto_discover_device(
                device_id=device_id_clean,
                mac=raw_mac,
                device_type=raw_device_type,
                device_name=raw_device_name,
                firmware_version=raw_firmware_version,
                ip_address=request.remote_addr
            )
            db_instance.touch_device_seen(
                device_id=device_id_clean,
                mac=raw_mac,
                device_type=raw_device_type,
                ip_address=request.remote_addr,
                gps_status=raw_gps_status or "valid",
                device_name=raw_device_name,
                firmware_version=raw_firmware_version,
                wifi_rssi=wifi_rssi,
                battery_mv=battery_mv,
                uptime_seconds=uptime_seconds
            )
            db_instance.update_device_health(device_id_clean, {
                "bus_id": None,
                "satellites": int(raw_satellites) if raw_satellites is not None else 8,
                "accuracy": float(raw_accuracy) if raw_accuracy is not None else 1.5,
                "altitude": float(raw_altitude) if raw_altitude is not None else 500.0,
                "gps_status": raw_gps_status or "valid",
                "ip_address": request.remote_addr,
                "latitude": latitude,
                "longitude": longitude
            })
            return jsonify({
                "success": True,
                "status": "unassigned",
                "message": f"Device '{device_id_clean}' was auto-discovered and registered. Please map it to a bus in Device Management.",
                "data": {
                    "deviceId": device_id_clean,
                    "mac": raw_mac,
                    "status": "unassigned",
                    "auto_discovered": True
                }
            }), 200
        else:
            # Auto-create bus for legacy / direct test pings
            chosen_bus_id = str(raw_bus_number).strip().upper() if (raw_bus_number and str(raw_bus_number).strip()) else device_id_clean.upper()
            bus = Bus(
                bus_id=chosen_bus_id,
                bus_name=f"College Bus {chosen_bus_id}",
                bus_number=chosen_bus_id,
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

    # Touch device seen with assigned bus
    db_instance.touch_device_seen(
        device_id=device_id_clean,
        mac=raw_mac,
        device_type=raw_device_type,
        ip_address=request.remote_addr,
        gps_status=raw_gps_status or "valid",
        assigned_bus_id=bus_id,
        device_name=raw_device_name,
        firmware_version=raw_firmware_version,
        wifi_rssi=wifi_rssi,
        battery_mv=battery_mv,
        uptime_seconds=uptime_seconds
    )

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
    health_payload = {
        "bus_id": bus_id,
        "satellites": satellites,
        "accuracy": accuracy,
        "altitude": altitude,
        "gps_status": gps_status,
        "ip_address": request.remote_addr,
        "latitude": latitude,
        "longitude": longitude
    }
    if wifi_rssi is not None:
        health_payload["wifi_rssi"] = wifi_rssi
    if battery_mv is not None:
        health_payload["battery_mv"] = battery_mv
    if uptime_seconds is not None:
        health_payload["uptime_seconds"] = uptime_seconds

    db_instance.update_device_health(bus.device_id, health_payload)

    return jsonify({
        "success": True,
        "status": "success",
        "message": "Location saved",
        "location": saved_location,
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
            "wifi_rssi": wifi_rssi,
            "battery_mv": battery_mv,
            "uptime_seconds": uptime_seconds,
            "date": saved_location["date"],
            "time": saved_location["time"],
            "timestamp": saved_location["timestamp"],
            "status": saved_location.get("status"),
            "is_at_college": saved_location.get("is_at_college", False),
            "distance_to_college_m": saved_location.get("distance_to_college_m"),
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
    for r in routes:
        if not r.get("route_id") and r.get("id"):
            r["route_id"] = r.get("id")
        elif not r.get("id") and r.get("route_id"):
            r["id"] = r.get("route_id")
    return jsonify({"status": "success", "count": len(routes), "routes": routes}), 200


@api_bp.route("/routes/<route_id>", methods=["GET"])
def get_single_route(route_id):
    """Get single route details and geometry."""
    route = db_instance.get_route(route_id)
    if not route:
        return jsonify({"status": "error", "message": f"Route {route_id} not found"}), 404
    return jsonify({"status": "success", "route": route}), 200


@api_bp.route("/routes", methods=["POST"])
@admin_required
def create_route():
    """Create a new route."""
    data = request.get_json(silent=True) or {}
    route_name = data.get("route_name")
    if not route_name:
        return jsonify({"status": "error", "message": "Route Name is required"}), 400
    new_route = db_instance.create_route(data)
    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="ROUTE_CREATE",
        target_type="ROUTE",
        target_id=new_route["id"],
        details=f"Created route {new_route['route_name']}",
        ip_address=request.remote_addr
    )
    return jsonify({"status": "success", "message": "Route created", "route": new_route}), 201


@api_bp.route("/stops", methods=["GET"])
def get_stops():
    """List registered bus stops with geofence radiuses."""
    route_id = request.args.get("route_id")
    stops = db_instance.get_all_stops(route_id=route_id)
    return jsonify({"status": "success", "count": len(stops), "stops": stops}), 200


@api_bp.route("/stops", methods=["POST"])
@admin_required
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
# AUTHENTICATION & SESSION MANAGEMENT
# -----------------------------------------------------------------------------
@api_bp.route("/auth/login", methods=["POST"])
@api_bp.route("/admin/login", methods=["POST"])
def auth_login():
    """
    Authenticate user against users.json with brute-force lockout protection.
    Accepts: {username, password}
    """
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    client_ip = request.remote_addr or "127.0.0.1"

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required"}), 400

    success, user_info, message = db_instance.authenticate_user(username, password, client_ip=client_ip)
    if not success:
        return jsonify({"status": "error", "message": message}), 401

    session["user"] = user_info
    session["is_admin"] = (user_info.get("role") == "ADMIN")

    db_instance.record_audit_log(
        username=user_info["username"],
        role=user_info["role"],
        action="USER_LOGIN",
        target_type="SESSION",
        target_id=user_info["username"],
        details="User successfully authenticated",
        ip_address=client_ip
    )

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "user": user_info
    }), 200


@api_bp.route("/auth/logout", methods=["POST"])
@api_bp.route("/admin/logout", methods=["POST"])
def auth_logout():
    """Clear session and record logout in audit logs."""
    user = session.get("user") or {}
    username = user.get("username") or "anonymous"
    role = user.get("role") or "VIEWER"

    db_instance.record_audit_log(
        username=username,
        role=role,
        action="USER_LOGOUT",
        target_type="SESSION",
        target_id=username,
        details="User logged out",
        ip_address=request.remote_addr
    )

    session.pop("user", None)
    session.pop("is_admin", None)
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@api_bp.route("/auth/session", methods=["GET"])
def auth_session():
    """Get current active session user and role."""
    user = session.get("user")
    if user:
        return jsonify({
            "status": "success",
            "authenticated": True,
            "user": user
        }), 200

    # Fallback to anonymous viewer if not authenticated
    return jsonify({
        "status": "success",
        "authenticated": False,
        "user": {
            "username": "viewer",
            "role": "VIEWER",
            "full_name": "Fleet Dispatch Viewer",
            "is_guest": True
        }
    }), 200


# -----------------------------------------------------------------------------
# CENTRALIZED ADMIN DASHBOARD & STORAGE METRICS
# -----------------------------------------------------------------------------
@api_bp.route("/admin/dashboard", methods=["GET"])
def get_admin_dashboard():
    """
    Centralized admin overview metric aggregator:
    - Total registered buses (25-30+)
    - Active buses / Inactive buses
    - Currently running buses
    - Buses that have reached college
    - Offline ESP devices
    - Storage consumption against 300 MB limit
    - Today's completed trips
    """
    settings = db_instance.get_settings()
    threshold = int(settings.get("online_threshold_seconds", 30))
    all_buses = Bus.get_all(active_only=False)
    all_buses_dict = [b.to_dict(online_threshold_seconds=threshold) for b in all_buses]

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%d-%m-%Y")

    total_buses = len(all_buses_dict)
    active_buses = sum(1 for b in all_buses_dict if b.get("is_online"))
    inactive_buses = total_buses - active_buses

    reached_college_buses = 0
    running_buses = 0
    for b in all_buses_dict:
        loc = b.get("current_location") or {}
        is_reached = bool(loc.get("is_at_college") or loc.get("status") == "REACHED_COLLEGE")
        if is_reached:
            reached_college_buses += 1
        elif b.get("is_moving") or (b.get("is_online") and not is_reached):
            running_buses += 1

    devices_list = db_instance.get_all_devices(compute_status=True)
    total_devices = len(devices_list)
    online_devices = sum(1 for d in devices_list if d.get("is_online"))
    offline_devices = total_devices - online_devices
    unassigned_devices = sum(1 for d in devices_list if not d.get("assigned_bus_id"))

    all_routes = db_instance.get_all_routes()
    today_trips = db_instance.get_all_trips(date_filter=today_str)
    completed_trips_today = sum(1 for t in today_trips if t.get("status") == "COMPLETED")
    running_trips_today = sum(1 for t in today_trips if t.get("status") == "RUNNING")

    # Precise 300 MB storage metrics
    storage_metrics = db_instance.get_storage_metrics()

    dashboard_data = {
        "total_buses": total_buses,
        "active_buses": active_buses,
        "inactive_buses": inactive_buses,
        "running_buses": running_buses,
        "reached_college_buses": reached_college_buses,
        "total_devices": total_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "unassigned_devices": unassigned_devices,
        "total_routes": len(all_routes),
        "completed_trips_today": completed_trips_today,
        "running_trips_today": running_trips_today,
        "storage": storage_metrics,
        "timestamp": now.isoformat()
    }

    return jsonify({
        "status": "success",
        "dashboard": dashboard_data,
        "metrics": dashboard_data
    }), 200


@api_bp.route("/admin/storage", methods=["GET"])
def get_storage():
    """Retrieve detailed storage utilization metrics against 300 MB hard limit."""
    metrics = db_instance.get_storage_metrics()
    return jsonify({
        "status": "success",
        "storage": metrics
    }), 200


@api_bp.route("/admin/storage/cleanup", methods=["POST"])
def cleanup_storage():
    """Trigger 7-day rolling data retention cleanup and automated backup creation."""
    res = db_instance.enforce_seven_day_retention_and_backup(force=True)
    user = session.get("user")
    username = user.get("username") if user else "operator"
    role = user.get("role") if user else "OPERATOR"
    db_instance.record_audit_log(
        username=username,
        role=role,
        action="STORAGE_CLEANUP",
        target_type="STORAGE",
        target_id="300MB_ALLOCATION",
        details=f"7-day storage cleanup executed. Pruned records: {res.get('pruned_history_records', 0)}",
        ip_address=request.remote_addr
    )
    return jsonify({
        "status": "success",
        "message": "7-day rolling cleanup completed successfully. Expired data pruned.",
        "result": res,
        "storage": db_instance.get_storage_metrics()
    }), 200


@api_bp.route("/admin/storage/records", methods=["GET"])
def get_storage_records():
    """Retrieve stored tracking records for storage data management."""
    bus_id = request.args.get("bus_id")
    date_val = request.args.get("date")
    records = db_instance.get_stored_tracking_records(bus_id=bus_id, date=date_val, limit=100)
    return jsonify({
        "status": "success",
        "count": len(records),
        "records": records
    }), 200


@api_bp.route("/admin/storage/delete-records", methods=["POST"])
def delete_storage_records():
    """Delete selected tracking records safely with user confirmation."""
    data = request.get_json(silent=True) or {}
    bus_id = data.get("bus_id")
    date_val = data.get("date")
    indices = data.get("indices")

    deleted_count = db_instance.delete_selected_tracking_records(bus_id=bus_id, date=date_val, indices=indices)

    user = session.get("user")
    username = user.get("username") if user else "operator"
    role = user.get("role") if user else "OPERATOR"

    db_instance.record_audit_log(
        username=username,
        role=role,
        action="DELETE_TRACKING_RECORDS",
        target_type="TRACKING_DATA",
        target_id=bus_id or "SELECTED",
        details=f"Deleted {deleted_count} tracking records (bus={bus_id}, date={date_val}).",
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": f"Successfully deleted {deleted_count} tracking records.",
        "deleted_count": deleted_count,
        "storage": db_instance.get_storage_metrics()
    }), 200


@api_bp.route("/admin/database/reset", methods=["POST"])
def reset_database():
    """Wipe all operational fleet tracking data and reset database to clean free state."""
    db_instance.clear_all_data()
    user = session.get("user")
    username = user.get("username") if user else "operator"
    role = user.get("role") if user else "OPERATOR"
    db_instance.record_audit_log(
        username=username,
        role=role,
        action="DATABASE_RESET",
        target_type="DATABASE",
        target_id="ALL_TABLES",
        details="Wiped all operational tracking data, reset database to 100% free state.",
        ip_address=request.remote_addr
    )
    metrics = db_instance.get_storage_metrics()
    return jsonify({
        "status": "success",
        "message": "Database wiped and arranged as free. Storage is now 100% available.",
        "storage": metrics
    }), 200


# -----------------------------------------------------------------------------
# USER MANAGEMENT & AUDIT LOGS (RBAC)
# -----------------------------------------------------------------------------
@api_bp.route("/admin/users", methods=["GET"])
@admin_required
def get_users():
    """List all registered system users."""
    users = db_instance.get_all_users()
    return jsonify({
        "status": "success",
        "count": len(users),
        "users": users
    }), 200


@api_bp.route("/admin/users", methods=["POST"])
@admin_required
def create_user_route():
    """Register a new authorized user with role ADMIN or VIEWER."""
    data = request.get_json(silent=True) or {}
    try:
        new_u = db_instance.create_user(data)
        admin_user = session.get("user", {}).get("username") or "admin"
        db_instance.record_audit_log(
            username=admin_user,
            role="ADMIN",
            action="USER_CREATE",
            target_type="USER",
            target_id=new_u["username"],
            details=f"Created user {new_u['username']} with role {new_u['role']}",
            ip_address=request.remote_addr
        )
        return jsonify({
            "status": "success",
            "message": f"User {new_u['username']} created successfully",
            "user": new_u
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/admin/users/<username>/password", methods=["PUT"])
@admin_required
def update_user_password_route(username):
    """Update password for an authorized user."""
    data = request.get_json(silent=True) or {}
    new_password = str(data.get("new_password", "")).strip()
    old_password = str(data.get("old_password", "")).strip()

    admin_user = session.get("user", {}).get("username") or "admin"
    is_admin_override = (admin_user == "admin" or session.get("is_admin")) and (admin_user != username)

    try:
        db_instance.update_user_password(
            username=username,
            old_password=old_password,
            new_password=new_password,
            is_admin_override=is_admin_override
        )
        db_instance.record_audit_log(
            username=admin_user,
            role="ADMIN",
            action="PASSWORD_CHANGE",
            target_type="USER",
            target_id=username,
            details=f"Password updated for user {username}",
            ip_address=request.remote_addr
        )
        return jsonify({
            "status": "success",
            "message": f"Password for {username} updated successfully"
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/admin/users/<username>", methods=["DELETE"])
@admin_required
def delete_user_route(username):
    """Delete an authorized user."""
    try:
        success = db_instance.delete_user(username)
        if not success:
            return jsonify({"status": "error", "message": f"User '{username}' not found"}), 404

        admin_user = session.get("user", {}).get("username") or "admin"
        db_instance.record_audit_log(
            username=admin_user,
            role="ADMIN",
            action="USER_DELETE",
            target_type="USER",
            target_id=username,
            details=f"Deleted user {username}",
            ip_address=request.remote_addr
        )
        return jsonify({"status": "success", "message": f"User '{username}' deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/admin/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs_route():
    """Retrieve security audit logs."""
    limit = int(request.args.get("limit", 100))
    action = request.args.get("action")
    logs = db_instance.get_audit_logs(limit=limit, action=action)
    return jsonify({
        "status": "success",
        "count": len(logs),
        "audit_logs": logs
    }), 200


# -----------------------------------------------------------------------------
# COLLEGE DESTINATION & GEOFENCING CONFIGURATION
# -----------------------------------------------------------------------------
@api_bp.route("/college", methods=["GET"])
def get_college_route():
    """Retrieve configured college destination and geofence parameters."""
    config = db_instance.get_college_config()
    return jsonify({
        "status": "success",
        "college": config
    }), 200


@api_bp.route("/college", methods=["PUT", "POST"])
@admin_required
def update_college_route():
    """Update configured college destination and geofence radius."""
    data = request.get_json(silent=True) or {}
    updated = db_instance.update_college_config(data)

    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="COLLEGE_CONFIG_UPDATE",
        target_type="SETTINGS",
        target_id=updated.get("college_name"),
        details=f"Updated college coordinates to ({updated['college_latitude']}, {updated['college_longitude']}) radius {updated['college_geofence_radius_meters']}m",
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": "College configuration updated successfully",
        "college": updated
    }), 200


# -----------------------------------------------------------------------------
# ROUTE MANAGEMENT & GEOCODING (UPDATE & DELETE)
# -----------------------------------------------------------------------------
@api_bp.route("/routes/<route_id>", methods=["PUT"])
@admin_required
def update_route_route(route_id):
    """Update an existing transit route."""
    data = request.get_json(silent=True) or {}
    updated = db_instance.update_route(route_id, data)
    if not updated:
        return jsonify({"status": "error", "message": f"Route '{route_id}' not found"}), 404

    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="ROUTE_UPDATE",
        target_type="ROUTE",
        target_id=route_id,
        details=f"Updated route {route_id}",
        ip_address=request.remote_addr
    )
    return jsonify({
        "status": "success",
        "message": f"Route '{route_id}' updated successfully",
        "route": updated
    }), 200


@api_bp.route("/routes/<route_id>", methods=["DELETE"])
@admin_required
def delete_route_route(route_id):
    """Delete a transit route."""
    success = db_instance.delete_route(route_id)
    if not success:
        return jsonify({"status": "error", "message": f"Route '{route_id}' not found"}), 404

    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="ROUTE_DELETE",
        target_type="ROUTE",
        target_id=route_id,
        details=f"Deleted route {route_id}",
        ip_address=request.remote_addr
    )
    return jsonify({
        "status": "success",
        "message": f"Route '{route_id}' deleted successfully"
    }), 200


@api_bp.route("/routes/geocode", methods=["GET"])
def geocode_route_location():
    """
    Automatic location detection and geocoding endpoint:
    Searches location name and retrieves latitude and longitude suggestions.
    Fast instant offline local landmark dictionary with fallback to Nominatim.
    """
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify({"status": "error", "message": "Query parameter 'q' is required"}), 400

    q_lower = query.lower()
    matches = []

    # 1. Match local high-accuracy landmarks
    for lm in LOCAL_LANDMARKS:
        if q_lower in lm["name"].lower() or q_lower in lm["display_name"].lower():
            matches.append({
                "name": lm["name"],
                "display_name": lm["display_name"],
                "latitude": lm["latitude"],
                "longitude": lm["longitude"],
                "source": "local_transit_directory"
            })

    # 2. If fewer than 4 matches, attempt online Nominatim geocoding with timeout
    if len(matches) < 4:
        try:
            encoded_q = urllib.parse.quote(f"{query}, Hyderabad, India")
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_q}&format=json&limit=4"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartBusTrackingSystem/3.2 (contact@sphoorthy.ac.in)"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode())
                for item in data:
                    matches.append({
                        "name": item.get("name") or query.title(),
                        "display_name": item.get("display_name"),
                        "latitude": round(float(item["lat"]), 6),
                        "longitude": round(float(item["lon"]), 6),
                        "source": "nominatim_osm"
                    })
        except Exception:
            pass

    # If still empty, provide synthesized best-guess near Hyderabad city center
    if not matches:
        matches.append({
            "name": query.title(),
            "display_name": f"{query.title()}, Greater Hyderabad Area, Telangana",
            "latitude": 17.3850,
            "longitude": 78.4867,
            "source": "estimated_city_centroid"
        })

    return jsonify({
        "status": "success",
        "query": query,
        "count": len(matches),
        "suggestions": matches
    }), 200


# -----------------------------------------------------------------------------
# DISTANCE METRICS & DAILY TRIPS
# -----------------------------------------------------------------------------
@api_bp.route("/buses/<bus_id>/distances", methods=["GET"])
def get_bus_distances(bus_id):
    """
    Returns 3 distinct distance calculations:
    A. Trip Distance: distance in km for the current trip.
    B. Daily Distance: sum of distances of all trips today.
    C. Seven-Day Distance History: daily km breakdown for the latest seven days.
    """
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus '{bus_id}' not found"}), 404

    metrics = db_instance.get_bus_distance_metrics(bus.bus_id)
    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "bus_name": bus.bus_name,
        "distance_metrics": metrics
    }), 200


@api_bp.route("/buses/<bus_id>/trips", methods=["GET"])
def get_bus_trips_route(bus_id):
    """Retrieve daily trips for a bus (supports approx 2-4 trips per day)."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus '{bus_id}' not found"}), 404

    date_filter = request.args.get("date")
    trips = db_instance.get_bus_trips(bus.bus_id, date_filter=date_filter)
    return jsonify({
        "status": "success",
        "bus_id": bus.bus_id,
        "count": len(trips),
        "trips": trips
    }), 200


@api_bp.route("/trips", methods=["GET"])
def get_all_trips_route():
    """Retrieve all daily trips across fleet."""
    date_filter = request.args.get("date")
    trips = db_instance.get_all_trips(date_filter=date_filter)
    return jsonify({
        "status": "success",
        "count": len(trips),
        "trips": trips
    }), 200


# -----------------------------------------------------------------------------
# ADMIN BUS MANAGEMENT CRUD
# -----------------------------------------------------------------------------
@api_bp.route("/admin/buses", methods=["POST"])
@admin_required
def create_bus_admin():
    """Create a new bus in JSON database."""
    return register_bus()


@api_bp.route("/admin/buses/<bus_id>", methods=["PUT"])
@admin_required
def update_bus_admin(bus_id):
    """Update bus details in JSON database."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus '{bus_id}' not found"}), 404

    data = request.get_json(silent=True) or {}
    updated = db_instance.update_bus(bus.bus_id, data)

    # Re-associate device if device_id changed
    if data.get("device_id"):
        db_instance.assign_device_to_bus(data["device_id"], bus.bus_id)

    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="BUS_UPDATE",
        target_type="BUS",
        target_id=bus.bus_id,
        details=f"Updated details for bus {bus.bus_id}",
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": f"Bus '{bus_id}' updated successfully",
        "bus": Bus(**updated).to_dict() if updated else bus.to_dict()
    }), 200


@api_bp.route("/admin/buses/<bus_id>", methods=["DELETE"])
@admin_required
def delete_bus_admin(bus_id):
    """Delete a bus from JSON database."""
    bus = Bus.find_by_id(bus_id) or Bus.find_by_device_id(bus_id)
    if not bus:
        return jsonify({"status": "error", "message": f"Bus '{bus_id}' not found"}), 404

    success = db_instance.delete_bus(bus.bus_id)
    admin_user = session.get("user", {}).get("username") or "admin"
    db_instance.record_audit_log(
        username=admin_user,
        role="ADMIN",
        action="BUS_DELETE",
        target_type="BUS",
        target_id=bus.bus_id,
        details=f"Deleted bus {bus.bus_id} ({bus.bus_name})",
        ip_address=request.remote_addr
    )
    return jsonify({
        "status": "success",
        "message": f"Bus '{bus.bus_id}' deleted successfully"
    }), 200
