import argparse
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
UPDATE_INTERVAL = int(os.getenv("SIMULATOR_INTERVAL", "5"))

# Predefined Hyderabad Route Waypoints
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
    c = 2 * math.atan2(math.sqrt(max(0.0, min(1.0, a))), math.sqrt(max(0.0, min(1.0, 1.0 - a))))
    distance_km = 6371 * c

    return heading, distance_km


class BusSimulatorInstance:
    def __init__(self, bus_id, waypoints, mac=None, should_deviate=False):
        self.bus_id = bus_id
        self.mac = mac or f"AA:BB:CC:11:22:{abs(hash(bus_id)) % 250:02X}"
        self.waypoints = waypoints
        self.segment_index = 0
        self.progress = 0.0  # 0.0 to 1.0 along current segment
        self.forward = True
        self.step_size = 0.12  # Interpolation step
        self.should_deviate = should_deviate
        self.cycle_count = 0
        self.stopped_cycles = 0

    def get_next_location(self):
        self.cycle_count += 1
        w1 = self.waypoints[self.segment_index]
        if self.forward:
            next_idx = self.segment_index + 1
            if next_idx >= len(self.waypoints):
                self.forward = False
                next_idx = len(self.waypoints) - 2
        else:
            next_idx = self.segment_index - 1
            if next_idx < 0:
                self.forward = True
                next_idx = 1

        w2 = self.waypoints[next_idx]

        # Simulate stop dwell time at waypoints
        if self.stopped_cycles > 0:
            self.stopped_cycles -= 1
            curr_lat = w1[0]
            curr_lng = w1[1]
            speed = 0.0
            heading, _ = calculate_heading_and_distance(w1[0], w1[1], w2[0], w2[1])
            status = "STOPPED"
        else:
            # Interpolate coordinates
            curr_lat = w1[0] + (w2[0] - w1[0]) * self.progress
            curr_lng = w1[1] + (w2[1] - w1[1]) * self.progress

            # If simulated deviation flag is on, add deliberate off-route offset
            if self.should_deviate and 4 <= self.cycle_count <= 14:
                curr_lat += 0.0080  # ~900m off-route detour
                curr_lng += 0.0060

            heading, _ = calculate_heading_and_distance(w1[0], w1[1], w2[0], w2[1])
            speed = 32.0 + (self.cycle_count % 5) * 2.5
            status = "MOVING"

            self.progress += self.step_size
            if self.progress >= 1.0:
                self.progress = 0.0
                self.segment_index = next_idx
                # Dwell at stop for 1 cycle
                self.stopped_cycles = 1

        return {
            "deviceId": self.bus_id,
            "mac": self.mac,
            "device_type": "ESP8266",
            "latitude": round(curr_lat, 6),
            "longitude": round(curr_lng, 6),
            "apiKey": API_KEY,
            "speed": round(speed, 1),
            "heading": round(heading, 1),
            "accuracy": 1.2,
            "satellites": 9,
            "altitude": 540.0,
            "status": status
        }


DEFAULT_CAMPUS_DEVICES = [
    ("ESP8266-BUS-01", "AA:BB:CC:11:22:01"),
    ("ESP8266-BUS-02", "AA:BB:CC:11:22:02"),
    ("ESP8266-BUS-03", "AA:BB:CC:11:22:03"),
    ("ESP8266-BUS-04", "AA:BB:CC:11:22:04"),
]


def generate_bus_waypoints(count=4):
    """Assign waypoints for N buses based on route templates and mapped ESP devices."""
    bus_configs = []
    for i in range(1, count + 1):
        if i <= len(DEFAULT_CAMPUS_DEVICES):
            dev_id, dev_mac = DEFAULT_CAMPUS_DEVICES[i - 1]
        else:
            dev_id = f"BUS{i:03d}"
            dev_mac = f"AA:BB:CC:11:22:{i:02X}"

        route_template = ROUTES[(i - 1) % len(ROUTES)]
        # Add slight variation per bus so they don't overlap exactly
        offset_lat = ((i * 7) % 15 - 7) * 0.0012
        offset_lng = ((i * 11) % 15 - 7) * 0.0012

        bus_route = [(lat + offset_lat, lng + offset_lng) for lat, lng in route_template]
        bus_configs.append((dev_id, dev_mac, bus_route))
    return bus_configs


def run_simulator(bus_count=4, interval=5, single_bus_id=None, test_deviation=True):
    """
    Main simulator execution loop.
    Emulates physical GNSS tracker transmissions (ESP8266 & SIMCom A7670C) via HTTP GET query parameters.
    """
    print("=" * 75)
    print("  SMART BUS LIVE GPS SIMULATOR & ROUTE INTELLIGENCE TEST HARNESS")
    print(f"  Target Endpoint  : {API_URL}")
    print(f"  Update Frequency : Every {interval} seconds")
    print(f"  Simulated Buses  : {1 if single_bus_id else bus_count}")
    print(f"  Route Deviation  : Enabled on BUS-04" if test_deviation else "  Route Deviation  : Disabled")
    print("=" * 75)

    if single_bus_id:
        simulators = [BusSimulatorInstance(single_bus_id, ROUTES[0], should_deviate=test_deviation)]
    else:
        configs = generate_bus_waypoints(bus_count)
        simulators = [
            BusSimulatorInstance(dev_id, waypoints, mac=dev_mac, should_deviate=("04" in dev_id and test_deviation))
            for dev_id, dev_mac, waypoints in configs
        ]

    cycle = 1
    while True:
        print(f"\n[Cycle #{cycle} - {time.strftime('%H:%M:%S')}] Transmitting GPS updates...")
        success_count = 0

        for sim in simulators:
            params = sim.get_next_location()
            try:
                response = requests.get(API_URL, params=params, timeout=5)
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"  [ERROR] {params['deviceId']} returned {response.status_code}: {response.text}")
            except Exception as e:
                print(f"  [EXCEPT] {params['deviceId']} request failed: {e}")

        print(f"  [DONE] {success_count}/{len(simulators)} buses updated successfully.")
        cycle += 1
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Bus GPS Simulator")
    parser.add_argument("--count", type=int, default=25, help="Number of buses to simulate (default: 25)")
    parser.add_argument("--interval", type=int, default=5, help="Update interval in seconds (default: 5)")
    parser.add_argument("--bus-id", type=str, default=None, help="Simulate a single specific bus (e.g. bus-01)")
    parser.add_argument("--no-deviation", action="store_true", help="Disable simulated route deviation")

    args = parser.parse_args()

    try:
        run_simulator(
            bus_count=args.count,
            interval=args.interval,
            single_bus_id=args.bus_id,
            test_deviation=not args.no_deviation
        )
    except KeyboardInterrupt:
        print("\n[INFO] Simulator terminated by user.")
        sys.exit(0)
