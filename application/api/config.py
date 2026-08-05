"""MBD-001 demonstrator configuration."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
APP_ROOT = Path(__file__).resolve().parents[1]

HOST = os.environ.get("MBD_HOST", "0.0.0.0")
PORT = int(os.environ.get("MBD_PORT", "8780"))

# Keep POC databases; demonstrator adds its own thin store
MEMORYBOX_DB = Path(os.environ.get("MBD_MEMORYBOX_DB", ROOT / "database" / "memorybox.db"))
HVRT_DB = Path(os.environ.get("MBD_HVRT_DB", ROOT / "hvrt" / "database" / "hvrt.sqlite"))
DEMONSTRATOR_DB = Path(
    os.environ.get("MBD_DEMONSTRATOR_DB", ROOT / "database" / "mbd_demonstrator.sqlite")
)

# Review iframe / link target (HVRT review_app)
HVRT_ORIGIN = os.environ.get("MBD_HVRT_ORIGIN", "http://127.0.0.1:8788").rstrip("/")

# Optional Ask historian proxy (Desktop POC when running)
ASK_ORIGIN = os.environ.get("MBD_ASK_ORIGIN", "").rstrip("/")

# FlightSim Ollama (Ask path when wired)
OLLAMA_BASE = os.environ.get("MBD_OLLAMA_BASE", "http://192.168.4.39:11434").rstrip("/")

# Immich (optional — also loaded from config/immich.env)
IMMICH_BASE_URL = os.environ.get("IMMICH_BASE_URL", "").rstrip("/")
IMMICH_API_KEY = os.environ.get("IMMICH_API_KEY", "")

UI_DIR = APP_ROOT / "ui" / "static"
