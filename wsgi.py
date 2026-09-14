"""
WSGI Entry Point for PS26231 Deployment (Render / Gunicorn / Production).
"""
import os
from src.web.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
