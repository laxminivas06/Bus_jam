import math
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

API_URL = os.getenv("SERVER_URL", "http://127.0.0.1:5001/api/locations/save")
API_KEY = os.getenv("API_KEY", "YOUR_API_KEY")
UPDATE_INTERVAL = int(os.getenv("SIMULATOR_INTERVAL", "10"))

# Predefined Hyderabad Route Waypoints for 25 Buses
ROUTES = [
    # Route 1: Koti -> Abids -> Punjagutta -> Campus
    [
        (17.385044, 78.486671), (17.391200, 78.474500), (17.402100, 78.461000),
        (17.425500, 78.451200), (17.442000, 78.448000), (17.458000, 78.441000)
    ],
    # Route 2: Secunderabad -> Paradise -> Begumpet
    [
        (17.439930, 78.498274), (17.443500, 78.487000), (17.441100, 78.471200),
        (17.438000, 78.459000), (17.435000, 78.446000)
    ],
    # Route 3: LB Nagar -> Dilsukhnagar -> Malakpet
    [
        (17.345719, 78.552230), (17.368800, 78.524500), (17.375500, 78.498000),
        (17.382000, 78.482000)
    ],
    # Route 4: Kukatpally -> KPHB -> Miyapur
    [
        (17.494793, 78.399644), (17.491000, 78.388000), (17.485000, 78.375000),
        (17.492000, 78.361000)
    ],
    # Route 5: Gachibowli -> Hitec City -> Madhapur
    [
        (17.440081, 78.348915), (17.445500, 78.362000), (17.451000, 78.378000),
        (17.442000, 78.391000)
    ],
]

def generate_bus_waypoints():
    """Assign waypoints for 25 buses based on base route templates."""
    bus_waypoints = {}
    for i in range(1, 26):
        bus_id = f"BUS{i:03d}"
        route_template = ROUTES[(i - 1) % len(ROUTES)]
        # Add slight variation per bus so they don't overlap exactly
        offset_lat = ((i * 7) % 15 - 7) * 0.0012
        offset_lng = ((i * 11) % 15 - 7) * 0.0012
        
        bus_route = [(lat + offset_lat, lng + offset_lng) for lat, lng in route_template]
        bus_waypoints[bus_id] = bus_route
    return bus_waypoints


def calculate_heading_and_distance(lat1, lon1, lat2, lon2):
    """Calculate heading angle (0-360 deg) and approximate distance (km) between two points."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)

    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)

    heading = (math.degrees(math.atan2(y, x)) + 360) % 360
    
    # Haversine distance
    d_lat = lat2_r - lat1_r
    a = math.sin(d_lat / 2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(d_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = 6371 * c

    return heading, distance_km


class BusSimulatorInstance:
    def __init__(self, bus_id, waypoints):
        self.bus_id = bus_id
        self.waypoints = waypoints
        self.segment_index = 0
        self.progress = 0.0  # 0.0 to 1.0 along current segment
        self.forward = True
        self.step_size = 0.15  # Interpolation step

    def get_next_location(self):
        w1 = self.waypoints[self.segment_index]
        if self.forward:
            next_idx = (self.segment_index + 1)
            if next_idx >= len(self.waypoints):
                self.forward = False
                next_idx = len(self.waypoints) - 2
        else:
            next_idx = (self.segment_index - 1)
            if next_idx < 0:
                self.forward = True
                next_idx = 1

        w2 = self.waypoints[next_idx]

        # Calculate current interpolated coordinates
        curr_lat = w1[0] + (w2[0] - w1[0]) * self.progress
        curr_lng = w1[1] + (w2[1] - w1[1]) * self.progress

        heading, _ = calculate_heading_and_distance(w1[0], w1[1], w2[0], w2[1])

        self.progress += self.step_size
        if self.progress >= 1.0:
            self.progress = 0.0
            self.segment_index = next_idx

        return {
            "deviceId": self.bus_id,
            "latitude": round(curr_lat, 6),
            "longitude": round(curr_lng, 6),
            "apikey": API_KEY
        }


def run_simulator():
    """
    Main simulator execution loop.
    Emulates the SIMCom A7600C/A7670C AT+HTTP GET communication:
    GET /api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY
    """
    print("=" * 70)
    print("  HARDWARE-INDEPENDENT COLLEGE BUS GPS SIMULATOR (25 BUSES)")
    print(f"  Target Endpoint: {API_URL}")
    print(f"  Update Frequency: Every {UPDATE_INTERVAL} seconds")
    print(f"  A7600C / AT-Command Emulation Mode (GET query parameters)")
    print("=" * 70)

    bus_routes = generate_bus_waypoints()
    simulators = [BusSimulatorInstance(bus_id, waypoints) for bus_id, waypoints in bus_routes.items()]

    cycle = 1
    while True:
        print(f"\n[Cycle #{cycle}] Transmitting GPS updates for 25 buses...")
        success_count = 0

        for sim in simulators:
            params = sim.get_next_location()
            try:
                # Send HTTP GET request with query params matching A7600C AT-command syntax
                response = requests.get(API_URL, params=params, timeout=5)
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"  [ERROR] {params['deviceId']} failed with HTTP {response.status_code}: {response.text}")
            except Exception as e:
                print(f"  [EXCEPT] {params['deviceId']} request failed: {e}")

        print(f"[{time.strftime('%H:%M:%S')}] Cycle #{cycle} completed: {success_count}/25 buses updated successfully.")
        cycle += 1
        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    try:
        run_simulator()
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
        sys.exit(0)
