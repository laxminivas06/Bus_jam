import os
from backend import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_ENV") == "development" or os.environ.get("DEBUG", "True") == "True"
    print(f"Starting College Bus Live Tracking Server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
