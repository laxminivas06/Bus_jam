import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-college-bus-tracker-2026")
    
    # JSON Data Storage directory
    DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "data"))

    # Hardware API Key (for A7600C/A7670C GET /api/locations/save?apikey=...)
    API_KEY = os.getenv("API_KEY", "YOUR_API_KEY")

    # Device authentication credentials (matched against X-Device-ID and X-Device-Token headers)
    DEVICE_ID = os.getenv("DEVICE_ID", "A7670C_SIM_001")
    DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "secure_bus_tracker_token_98765")

    # Admin authentication credentials
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")
    
    # Bus online threshold (seconds) - bus considered offline if no updates received within this time
    ONLINE_THRESHOLD_SECONDS = int(os.getenv("ONLINE_THRESHOLD_SECONDS", "30"))


class TestConfig(Config):
    TESTING = True
    DATA_DIR = str(BASE_DIR / "data_test")
    API_KEY = "YOUR_API_KEY"
    DEVICE_ID = "TEST_DEVICE"
    DEVICE_TOKEN = "TEST_TOKEN"
