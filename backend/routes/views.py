from flask import Blueprint, render_template, current_app
from backend.json_db import db_instance

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """Render main college bus tracking & route intelligence dashboard."""
    settings = db_instance.get_settings()
    return render_template(
        "index.html",
        admin_user=current_app.config.get("ADMIN_USERNAME"),
        settings=settings
    )
