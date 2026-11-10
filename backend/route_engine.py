import math
from datetime import datetime, timezone


def haversine_distance_m(lat1, lon1, lat2, lon2):
    """
    Calculate Haversine great-circle distance between two GPS coordinates in METERS.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(max(0.0, min(1.0, a))), math.sqrt(max(0.0, min(1.0, 1.0 - a))))
    return R * c


def haversine_distance_km(lat1, lon1, lat2, lon2):
    """Distance in Kilometers."""
    return haversine_distance_m(lat1, lon1, lat2, lon2) / 1000.0


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the initial bearing / heading (0-360 degrees) from point 1 to point 2.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(bearing, 1)


def bearing_to_cardinal(heading):
    """Convert heading angle (0-360 deg) to cardinal direction (N, NE, E, etc.)."""
    if heading is None:
        return "N/A"
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((heading + 11.25) / 22.5) % 16
    return directions[idx]


def point_to_segment_distance(plat, plng, alat, alng, blat, blng):
    """
    Calculate minimum distance in METERS from point P(plat, plng) to line segment A(alat, alng) - B(blat, blng).
    Uses equirectangular flat-earth approximation appropriate for local urban segments (<100km).
    Also returns the projected nearest point (lat, lng) on segment AB.
    """
    # Use average latitude for longitude scaling
    mean_lat_rad = math.radians((plat + alat + blat) / 3.0)
    kx = 111320.0 * math.cos(mean_lat_rad)  # meters per degree lon
    ky = 110540.0                          # meters per degree lat

    # Convert coordinates to local Cartesian coordinates (meters) relative to A
    px = (plng - alng) * kx
    py = (plat - alat) * ky
    bx = (blng - alng) * kx
    by = (blat - alat) * ky

    # Segment length squared
    seg_len_sq = bx * bx + by * by

    if seg_len_sq == 0:
        # A and B are identical
        dist = math.sqrt(px * px + py * py)
        return dist, alat, alng

    # Project point P onto segment AB, clamped to [0, 1]
    t = max(0.0, min(1.0, (px * bx + py * by) / seg_len_sq))

    # Nearest point on segment in local coordinates
    nx = t * bx
    ny = t * by

    # Distance
    dx = px - nx
    dy = py - ny
    dist = math.sqrt(dx * dx + dy * dy)

    # Convert nearest point back to lat/lng
    nearest_lat = alat + (ny / ky)
    nearest_lng = alng + (nx / kx)

    return dist, nearest_lat, nearest_lng


def _extract_coord(wp):
    """Safely extract (lat, lng) as floats from dict or list/tuple."""
    if isinstance(wp, (list, tuple)):
        return float(wp[0]), float(wp[1])
    if isinstance(wp, dict):
        lat = wp.get("lat") if "lat" in wp else wp.get("latitude", 0.0)
        lng = wp.get("lng") if "lng" in wp else (wp.get("longitude", 0.0) if "longitude" in wp else wp.get("lon", 0.0))
        return float(lat), float(lng)
    return 0.0, 0.0


def distance_to_route_polyline(plat, plng, waypoints):
    """
    Find minimum distance in METERS from point P(plat, plng) to a polyline defined by a list of waypoints.
    Returns (min_distance_m, nearest_segment_index, (nearest_lat, nearest_lng)).
    """
    if not waypoints or len(waypoints) < 1:
        return 0.0, -1, (plat, plng)

    p0 = _extract_coord(waypoints[0])
    if len(waypoints) == 1:
        d = haversine_distance_m(plat, plng, p0[0], p0[1])
        return d, 0, p0

    min_dist = float("inf")
    best_seg = 0
    best_point = p0

    for i in range(len(waypoints) - 1):
        alat, alng = _extract_coord(waypoints[i])
        blat, blng = _extract_coord(waypoints[i + 1])

        d, nlat, nlng = point_to_segment_distance(plat, plng, alat, alng, blat, blng)
        if d < min_dist:
            min_dist = d
            best_seg = i
            best_point = (nlat, nlng)

    return min_dist, best_seg, best_point


def calculate_polyline_length_km(waypoints):
    """Calculate total length of a polyline in kilometers."""
    if not waypoints or len(waypoints) < 2:
        return 0.0

    total_km = 0.0
    for i in range(len(waypoints) - 1):
        alat, alng = _extract_coord(waypoints[i])
        blat, blng = _extract_coord(waypoints[i + 1])
        total_km += haversine_distance_km(alat, alng, blat, blng)
    return round(total_km, 2)


def calculate_route_progress_and_eta(bus_lat, bus_lng, current_speed, waypoints, stops):
    """
    Compute:
      - Completed distance along route (km)
      - Remaining distance to destination (km)
      - Progress percentage (0 - 100%)
      - Upcoming stops with distance and ETA in minutes
    """
    if not waypoints or len(waypoints) < 2:
        return {
            "completed_distance_km": 0.0,
            "remaining_distance_km": 0.0,
            "total_route_distance_km": 0.0,
            "progress_percent": 0.0,
            "upcoming_stops": []
        }

    total_route_km = calculate_polyline_length_km(waypoints)
    min_dist_m, best_seg, nearest_pt = distance_to_route_polyline(bus_lat, bus_lng, waypoints)

    # Calculate distance along waypoints up to best_seg
    completed_km = 0.0
    for i in range(best_seg):
        alat, alng = _extract_coord(waypoints[i])
        blat, blng = _extract_coord(waypoints[i + 1])
        completed_km += haversine_distance_km(alat, alng, blat, blng)

    # Add partial segment distance from waypoints[best_seg] to nearest_pt
    seg_pt = _extract_coord(waypoints[best_seg])
    completed_km += haversine_distance_km(
        seg_pt[0], seg_pt[1],
        nearest_pt[0], nearest_pt[1]
    )

    completed_km = min(completed_km, total_route_km)
    remaining_km = max(0.0, total_route_km - completed_km)
    progress_percent = round((completed_km / total_route_km) * 100.0, 1) if total_route_km > 0 else 0.0

    # Effective speed for ETA: use current speed if >15 km/h, else fallback to 25 km/h average bus speed
    effective_speed = current_speed if (current_speed and current_speed > 15.0) else 25.0

    upcoming_stops = []
    if stops:
        for stop in stops:
            slat = float(stop.get("latitude", 0))
            slng = float(stop.get("longitude", 0))
            dist_to_stop_m = haversine_distance_m(bus_lat, bus_lng, slat, slng)
            dist_to_stop_km = dist_to_stop_m / 1000.0

            eta_minutes = round((dist_to_stop_km / effective_speed) * 60.0, 1)
            upcoming_stops.append({
                "stop_id": stop.get("id"),
                "name": stop.get("name"),
                "distance_km": round(dist_to_stop_km, 2),
                "distance_m": round(dist_to_stop_m, 1),
                "eta_minutes": max(1, int(round(eta_minutes))),
                "is_near": dist_to_stop_m <= stop.get("radius_m", 75)
            })

        # Sort stops by distance from bus
        upcoming_stops.sort(key=lambda s: s["distance_km"])

    return {
        "completed_distance_km": round(completed_km, 2),
        "remaining_distance_km": round(remaining_km, 2),
        "total_route_distance_km": total_route_km,
        "progress_percent": progress_percent,
        "upcoming_stops": upcoming_stops
    }


def compute_trip_summary(history_records):
    """
    Analyzes historical GPS records and computes journey metrics:
      - Total distance travelled (km)
      - Average speed (km/h)
      - Maximum speed (km/h)
      - Number of stops
      - Total stoppage duration (minutes)
      - Start location & time
      - End location & time
    """
    if not history_records or len(history_records) == 0:
        return {
            "total_distance_km": 0.0,
            "average_speed": 0.0,
            "max_speed": 0.0,
            "stoppage_time_minutes": 0,
            "stops_count": 0,
            "start_time": None,
            "end_time": None,
            "start_point": None,
            "end_point": None,
            "records_count": 0
        }

    total_dist_km = 0.0
    speeds = []
    max_speed = 0.0
    stopped_duration_seconds = 0.0
    stops_count = 0
    in_stop_state = False

    for i in range(len(history_records)):
        rec = history_records[i]
        spd = float(rec.get("speed", 0.0) or 0.0)
        speeds.append(spd)
        if spd > max_speed:
            max_speed = spd

        # Accumulate distance between consecutive valid points
        if i > 0:
            prev = history_records[i - 1]
            plat, plng = float(prev.get("latitude", 0)), float(prev.get("longitude", 0))
            clat, clng = float(rec.get("latitude", 0)), float(rec.get("longitude", 0))
            d = haversine_distance_km(plat, plng, clat, clng)

            # Filter out GPS jump spikes (> 5km in 10s is impossible for a bus)
            if d < 3.0:
                total_dist_km += d

            # Calculate time difference for stoppage detection
            try:
                t1 = datetime.fromisoformat(prev["timestamp"])
                t2 = datetime.fromisoformat(rec["timestamp"])
                dt = (t2 - t1).total_seconds()
            except Exception:
                dt = 10.0

            if spd < 3.0:
                stopped_duration_seconds += max(0, dt)
                if not in_stop_state and dt >= 15:
                    stops_count += 1
                    in_stop_state = True
            else:
                in_stop_state = False

    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0

    first_rec = history_records[0]
    last_rec = history_records[-1]

    return {
        "total_distance_km": round(total_dist_km, 2),
        "average_speed": round(avg_speed, 1),
        "max_speed": round(max_speed, 1),
        "stoppage_time_minutes": int(round(stopped_duration_seconds / 60.0)),
        "stops_count": stops_count,
        "start_time": first_rec.get("time") or first_rec.get("timestamp"),
        "end_time": last_rec.get("time") or last_rec.get("timestamp"),
        "start_point": {
            "latitude": first_rec.get("latitude"),
            "longitude": first_rec.get("longitude")
        },
        "end_point": {
            "latitude": last_rec.get("latitude"),
            "longitude": last_rec.get("longitude")
        },
        "records_count": len(history_records)
    }

