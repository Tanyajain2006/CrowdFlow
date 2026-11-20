import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


HOST = os.getenv("CROWDFLOW_HOST", "127.0.0.1")
PORT = _env_int("CROWDFLOW_PORT", 8000)
MAX_UPLOAD_MB = _env_int("CROWDFLOW_MAX_UPLOAD_MB", 500)
FRAME_INTERVAL = _env_int("CROWDFLOW_FRAME_INTERVAL", 10)
YOLO_MODEL = os.getenv("CROWDFLOW_YOLO_MODEL", "yolov8n.pt")
YOLO_CONFIDENCE = _env_float("CROWDFLOW_YOLO_CONFIDENCE", 0.35)
YOLO_DEVICE = os.getenv("CROWDFLOW_YOLO_DEVICE") or None
OUTPUT_DIR = Path(os.getenv("CROWDFLOW_OUTPUT_DIR", str(ROOT_DIR / "backend" / "storage"))).resolve()
VIDEO_DIR = Path(os.getenv("CROWDFLOW_VIDEO_DIR", str(OUTPUT_DIR / "videos"))).resolve()
DATABASE_PATH = Path(os.getenv(
    "CROWDFLOW_DATABASE",
    str(ROOT_DIR / "backend" / "storage" / "crowdflow.db"),
)).resolve()

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "application/octet-stream",
}

