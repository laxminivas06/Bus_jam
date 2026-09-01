from flask import Blueprint, render_template, current_app

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """Render main college bus tracking dashboard."""
    return render_template(
        "index.html",
        admin_user=current_app.config.get("ADMIN_USERNAME"),
    )
