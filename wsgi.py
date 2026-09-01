import sys
from pathlib import Path

# Add project root directory to Python path
project_home = Path(__file__).resolve().parent
if str(project_home) not in sys.path:
    sys.path.insert(0, str(project_home))

from backend import create_app

# WSGI application object expected by Gunicorn / PythonAnywhere
application = create_app()

if __name__ == "__main__":
    application.run()
