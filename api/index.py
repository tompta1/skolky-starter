import os
import sys

# Add repo root to path so `backend` is importable as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app  # noqa: E402 — app is the ASGI entry point Vercel serves

__all__ = ["app"]
