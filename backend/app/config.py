"""
Configuration for AI TrafficGuard Backend
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VIDEOS_DIR = BASE_DIR / "videos"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
DATA_DIR = BASE_DIR / "data"

for folder in [VIDEOS_DIR, SNAPSHOTS_DIR, DATA_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Database URL: defaults to PostgreSQL if configured, otherwise falls back to SQLite
db_path = (DATA_DIR / "trafficguard.db").as_posix()
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite+aiosqlite:///{db_path}"
)

# Default Video File
DEFAULT_VIDEO = VIDEOS_DIR / "cctv_camera_feed.mp4"

# Check Zone Polygon (Default Road ROI: Quad coordinates [x, y] on a 1350x756 frame)
DEFAULT_ZONE_POLYGON = [
    [40, 480],    # Bottom-left
    [1310, 480],  # Bottom-right
    [1260, 335],  # Top-right
    [80, 335]     # Top-left
]

# Detection & Tracking Configs
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.35"))
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.45"))
MIN_EVAL_FRAMES = int(os.getenv("MIN_EVAL_FRAMES", "3"))
HELMET_CONF_THRESHOLD = 0.50
SEATBELT_CONF_THRESHOLD = 0.50

# Server settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
