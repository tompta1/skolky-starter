import sys
import os

# Make the repo root importable so `from backend.app.main import app` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.main import app  # noqa: F401, E402 — re-exported as the Vercel ASGI handler
