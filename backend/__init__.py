from pathlib import Path
from flask import Flask
from flask_cors import CORS

from backend.config import Config
from backend.json_db import db_instance
from backend.routes.api import api_bp
from backend.routes.views import views_bp


def create_app(config_class=Config):
    base_dir = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        template_folder=str(base_dir / "frontend" / "templates"),
        static_folder=str(base_dir / "frontend" / "static"),
    )
    app.config.from_object(config_class)

    # Enable CORS for REST API
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register Blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Ensure JSON data store is initialized in clean state (no seed/mock data)
    with app.app_context():
        db_instance.init_storage()

    return app
