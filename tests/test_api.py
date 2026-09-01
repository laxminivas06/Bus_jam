import pytest
from backend import create_app
from backend.config import TestConfig
from backend.json_db import db_instance
from backend.models import Bus


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean JSON database before each test."""
    db_instance.clear_all_data()
    yield
    db_instance.clear_all_data()


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_check(client):
    """Test health endpoint returns healthy JSON."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["storage"] == "json"
    assert "timestamp" in data


def test_clean_initial_state_empty_buses(client):
    """Test that initially there is zero seeded demo data (clean state)."""
    response = client.get("/api/buses")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["metrics"]["total_buses"] == 0
    assert data["metrics"]["online_buses"] == 0
    assert data["metrics"]["offline_buses"] == 0
    assert data["metrics"]["last_update"] is None
    assert data["count"] == 0
    assert data["buses"] == []


def test_get_single_bus_not_found(client):
    """Test get non-existent bus returns 404."""
    response = client.get("/api/buses/BUS999")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"


def test_a7600c_http_get_locations_save(client):
    """
    Test SIMCom A7600C/A7670C HTTP GET API:
    GET /api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY
    """
    url = "/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY"
    res = client.get(url)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["message"] == "Location saved"
    assert data["data"]["bus_no"] == "BUS001"
    assert data["data"]["latitude"] == 17.281409
    assert data["data"]["longitude"] == 78.553712
    assert "date" in data["data"]
    assert "time" in data["data"]

    # Now verify the bus is automatically registered in JSON storage
    bus_res = client.get("/api/buses/BUS001")
    assert bus_res.status_code == 200
    bus_data = bus_res.get_json()["bus"]
    assert bus_data["bus_id"] == "BUS001"
    assert bus_data["current_location"]["latitude"] == 17.281409
    assert bus_data["is_online"] is True


def test_locations_save_validation(client):
    """Test security and validation of location parameters."""
    # 1. Invalid API key
    res_bad_key = client.get("/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=78.553712&apikey=INVALID_KEY")
    assert res_bad_key.status_code == 401
    assert res_bad_key.get_json()["success"] is False

    # 2. Missing deviceId
    res_no_dev = client.get("/api/locations/save?latitude=17.281409&longitude=78.553712&apikey=YOUR_API_KEY")
    assert res_no_dev.status_code == 400
    assert res_no_dev.get_json()["success"] is False

    # 3. Missing coordinates
    res_no_coords = client.get("/api/locations/save?deviceId=BUS001&apikey=YOUR_API_KEY")
    assert res_no_coords.status_code == 400
    assert res_no_coords.get_json()["success"] is False

    # 4. Out-of-range coordinates
    res_bad_lat = client.get("/api/locations/save?deviceId=BUS001&latitude=120.0&longitude=78.553712&apikey=YOUR_API_KEY")
    assert res_bad_lat.status_code == 400

    res_bad_lng = client.get("/api/locations/save?deviceId=BUS001&latitude=17.281409&longitude=200.0&apikey=YOUR_API_KEY")
    assert res_bad_lng.status_code == 400


def test_post_location_compatibility(client, app):
    """Test POST /api/location payload compatibility with headers."""
    headers = {
        "X-Device-ID": app.config["DEVICE_ID"],
        "X-Device-Token": app.config["DEVICE_TOKEN"]
    }
    payload = {
        "bus_no": "BUS002",
        "latitude": 17.439930,
        "longitude": 78.498274
    }
    res = client.post("/api/location", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["bus_no"] == "BUS002"


def test_date_wise_history(client):
    """Test recording and querying date-wise route history."""
    # Send 2 location points
    client.get("/api/locations/save?deviceId=BUS003&latitude=17.345719&longitude=78.552230&apikey=YOUR_API_KEY")
    client.get("/api/locations/save?deviceId=BUS003&latitude=17.348000&longitude=78.555000&apikey=YOUR_API_KEY")

    # Query history
    res = client.get("/api/buses/BUS003/history")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["bus_id"] == "BUS003"
    assert data["count"] == 2
    assert len(data["available_dates"]) >= 1

    # Filter with specific date
    date_str = data["available_dates"][0]
    res_filtered = client.get(f"/api/buses/BUS003/history?date={date_str}")
    assert res_filtered.status_code == 200
    data_filtered = res_filtered.get_json()
    assert data_filtered["count"] == 2
    assert data_filtered["history"][0]["date"] == date_str


def test_admin_crud_lifecycle(client):
    """Test admin authentication, creating, updating, and deleting buses."""
    # 1. Login with bad credentials
    bad_login = client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    # 2. Login with valid credentials
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "adminpass"})
    assert login_res.status_code == 200

    # 3. Create a new bus
    new_bus_data = {
        "bus_id": "BUS050",
        "bus_number": "TS 09 UB 5050",
        "route_name": "Route 50: Campus Express",
        "driver_name": "Rajesh Kumar",
        "driver_phone": "+91 98480 50505",
        "capacity": 52
    }
    create_res = client.post("/api/admin/buses", json=new_bus_data)
    assert create_res.status_code == 201
    assert create_res.get_json()["bus"]["bus_id"] == "BUS050"

    # 4. Update the bus
    update_res = client.put("/api/admin/buses/BUS050", json={"driver_name": "Rajesh K."})
    assert update_res.status_code == 200
    assert update_res.get_json()["bus"]["driver_name"] == "Rajesh K."

    # 5. Delete the bus
    delete_res = client.delete("/api/admin/buses/BUS050")
    assert delete_res.status_code == 200

    # 6. Verify deleted
    get_res = client.get("/api/buses/BUS050")
    assert get_res.status_code == 404
